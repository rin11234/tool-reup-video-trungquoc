import os
import yt_dlp
from moviepy.editor import VideoFileClip, vfx, AudioFileClip, CompositeVideoClip, TextClip, concatenate_audioclips, ImageClip, CompositeAudioClip
import cv2
import numpy as np
import time
import traceback
import whisper
from googletrans import Translator
from gtts import gTTS
import srt
import moviepy.config as mpyconf
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from moviepy.audio.fx.audio_loop import audio_loop
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from PIL import Image, ImageDraw, ImageFont
import torch
import csv
import openai
import glob
from pydub import AudioSegment
import asyncio

DOWNLOAD_DIR = "downloads"
LOG_FILE = "processed_log.txt"
EDIT_DIR = "edit"
FB_CONFIG_FILE = "fb_upload_config.txt"

def ensure_dirs():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            pass

def is_processed(video_url):
    with open(LOG_FILE, "r") as f:
        return video_url.strip() in [line.strip() for line in f.readlines()]

def log_processed(video_url):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(video_url.strip() + "\n")

def download_video(url):
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'format': 'mp4',
        'noplaylist': True,
        'quiet': False,
        'merge_output_format': 'mp4',
        'postprocessors': [],
        'cookiefile': 'cookies.txt'
    }
    # TikTok: remove watermark
    if "tiktok.com" in url:
        ydl_opts['postprocessors'].append({
            'key': 'FFmpegVideoRemuxer',
            'preferedformat': 'mp4'
        })
        ydl_opts['postprocessor_args'] = [
            '-vf', 'crop=iw-0:ih-0:0:0'  # dummy, yt-dlp auto no watermark
        ]
        ydl_opts['extractor_args'] = {'tiktok': ['--no-watermark']}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if not filename.endswith('.mp4'):
                filename = filename.rsplit('.', 1)[0] + '.mp4'
            return filename
    except Exception as e:
        print("\n[!] Không thể tải video. Nguyên nhân có thể:")
        print("- Link không phải là link video trực tiếp (ví dụ: Douyin cần link dạng /video/ hoặc v.douyin.com)")
        print("- Video bị chặn khu vực hoặc bảo vệ bản quyền")
        print("- Dịch vụ yt-dlp chưa hỗ trợ link này hoặc link không hợp lệ")
        print(f"- Thông báo lỗi chi tiết: {e}\n")
        return None

def optimize_video_export(clip, output_path, quality_preset="2"):
    # Cấu hình thông số xuất video theo chất lượng
    export_settings = {
        "1": {  # Chất lượng cao (chậm)
            "preset": "slow",
            "bitrate": "4000k",
            "threads": 4,
            "ffmpeg_params": ["-crf", "18"]
        },
        "2": {  # Cân bằng (khuyến nghị)
            "preset": "medium",
            "bitrate": "2000k",
            "threads": 4,
            "ffmpeg_params": ["-crf", "23"]
        },
        "3": {  # Tốc độ nhanh
            "preset": "veryfast",
            "bitrate": "1500k",
            "threads": 4,
            "ffmpeg_params": ["-crf", "28"]
        },
        "4": {  # Siêu nhanh
            "preset": "ultrafast",
            "bitrate": "1000k",
            "threads": 8,
            "ffmpeg_params": ["-crf", "35", "-tune", "fastdecode"]
        }
    }

    # Lấy cấu hình theo preset
    settings = export_settings[quality_preset]

    # Xuất video với cấu hình đã chọn
    clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        preset=settings["preset"],
        bitrate=settings["bitrate"],
        threads=settings["threads"],
        ffmpeg_params=settings["ffmpeg_params"],
        logger='bar'  # Hiển thị thanh tiến trình
    )

# Đảm bảo frame là RGB (3 chiều)
def ensure_final_rgb(im):
    import cv2
    if im.ndim == 2:
        return cv2.cvtColor(im, cv2.COLOR_GRAY2RGB)
    if im.shape[2] == 4:
        return im[:, :, :3]
    return im

def process_video(input_path):
    # Lưu file mới vào thư mục 'edit'
    import srt as pysrt
    from pydub import AudioSegment
    from moviepy.editor import vfx, CompositeVideoClip, TextClip
    os.makedirs(EDIT_DIR, exist_ok=True)
    clip = VideoFileClip(input_path)
    # --- TỰ ĐỘNG CẮT 1 GIÂY ĐẦU/HOẶC 1 GIÂY CUỐI ---
    if clip.duration > 2:
        start = 1
        end = clip.duration - 1
        if end <= start:
            start = 0
            end = clip.duration
        clip = clip.subclip(start, end)
    # --- LỰA CHỌN KHUNG HÌNH ---
    aspect_ratios = [(16, 9)]  # Mặc định 16:9
    try:
        print("Chọn khung hình xuất video:")
        print("1. 16:9 (ngang)")
        print("2. 9:16 (dọc)")
        print("3. Cả hai (tạo 2 video)")
        aspect_choice = input("Nhập số lựa chọn (1/2/3, mặc định 1): ").strip()
        if aspect_choice not in ["1", "2", "3"]:
            aspect_choice = "1"
        if aspect_choice == "1":
            aspect_ratios = [(16, 9)]
        elif aspect_choice == "2":
            aspect_ratios = [(9, 16)]
        else:
            aspect_ratios = [(16, 9), (9, 16)]
    except Exception:
        pass
  
    # Hỏi tuỳ chọn zoom
    try:
        zoom_percent = float(input("Nhập mức độ zoom (20-30, đơn vị %): ").strip())
        if zoom_percent < 10 or zoom_percent > 30:
            zoom_percent = 10
    except:
        zoom_percent = 20
    # --- THÊM LẠI PHẦN HỎI VÀ ÁP DỤNG HIỆU ỨNG VIDEO ---
    print("Chọn hiệu ứng màu cho video để tránh bản quyền:")
    print("0. Không hiệu ứng")
    print("1. Tăng sáng")
    print("2. Giảm sáng")
    print("3. Trắng đen")
    print("4. Đảo màu")
    print("5. Tăng tương phản")
    print("6. Giảm tương phản")
    print("7. Đảo ngược video (mirror)")
    print("8. Làm mờ video")
    print("9. Làm mờ và đảo ngược")
    print("Có thể nhập nhiều số liên tiếp để áp dụng nhiều hiệu ứng (ví dụ: 123 sẽ áp dụng hiệu ứng 1,2,3)")
    print("Enter để áp dụng tất cả hiệu ứng")
    effect = input("Nhập số hiệu ứng muốn áp dụng (0-9, Enter để áp dụng tất cả): ").strip()
    if effect == "":  # Nếu nhấn Enter
        # Áp dụng tất cả hiệu ứng
        clip = clip.fx(vfx.colorx, 1.2)  # Tăng sáng
        clip = clip.fx(vfx.colorx, 0.8)  # Giảm sáng
        clip = clip.fx(vfx.lum_contrast, 0, 50, 128)  # Tăng tương phản
        clip = clip.fx(vfx.lum_contrast, 0, -50, 128) # Giảm tương phản
        clip = clip.fx(vfx.mirror_x)      # Đảo ngược
        w, h = clip.size
        clip = clip.resize(width=w//4).resize(width=w)  # Làm mờ
    else:
        # Áp dụng các hiệu ứng được chọn
        for num in effect:
            if num == "1":
                clip = clip.fx(vfx.colorx, 1.2)
            elif num == "2":
                clip = clip.fx(vfx.colorx, 0.8)
            elif num == "5":
                clip = clip.fx(vfx.lum_contrast, 0, 50, 128)
            elif num == "6":
                clip = clip.fx(vfx.lum_contrast, 0, -50, 128)
            elif num == "7":
                clip = clip.fx(vfx.mirror_x)
            elif num == "8":
                w, h = clip.size
                clip = clip.resize(width=w//4).resize(width=w)
            elif num == "9":
                w, h = clip.size
                clip = clip.resize(width=w//4).resize(width=w).fx(vfx.mirror_x)
    # Sau khi áp dụng hiệu ứng video
    # --- CROP/ZOOM VIDEO ---
    w, h = clip.size
    crop_x = int(w * (zoom_percent/100))
    crop_y = int(h * (zoom_percent/100))
    clip = clip.fx(vfx.crop, x1=crop_x, y1=crop_y, x2=w-crop_x, y2=h-crop_y)

    # Chỉ ép về 16:9 nếu chọn 16:9, còn 9:16 thì giữ nguyên bản gốc
    if aspect_ratios == [(16, 9)]:
        clip = force_aspect_ratio(clip, target_ratio=(16, 9), method="crop")
    # Nếu chọn 9:16 thì không làm gì, giữ nguyên video gốc

    # Hỏi ghép voice vào video (chèn vào đây, trước khi xuất video)
    add_voice = input("Bạn có muốn ghép voice vào video không? (y/n): ").strip().lower() == 'y'
    final = clip  # Luôn khởi tạo final là clip đã qua xử lý hiệu ứng
    audio_voice = None
    if add_voice:
        voice_path = input("Nhập đường dẫn file mp3 voice (ví dụ: ..._viet_voice.mp3): ").strip()
        if os.path.isfile(voice_path):
            from moviepy.editor import AudioFileClip, CompositeAudioClip
            audio_voice = AudioFileClip(voice_path)
            # Hỏi tốc độ voice
            try:
                speed_voice = float(input("Nhập tốc độ voice (1.0 là bình thường, >1.0 nhanh hơn, <1.0 chậm hơn, Enter để mặc định 1.0): ").strip() or "1.0")
            except:
                speed_voice = 1.0
            if speed_voice != 1.0:
                print(f"Áp dụng tốc độ voice do bạn nhập: {speed_voice}")
                audio_voice = audio_voice.fx(vfx.speedx, speed_voice)
            # --- ĐIỀU CHỈNH TỐC ĐỘ VIDEO ĐỂ KHỚP VỚI THỜI LƯỢNG VOICE ---
            voice_duration = audio_voice.duration
            video_duration = final.duration
            if abs(voice_duration - video_duration) > 0.01:
                speed_video = video_duration / voice_duration
                if speed_video < 1.0:
                    print(f"Voice dài hơn video. Sẽ làm chậm video lại với tốc độ: {speed_video:.4f}")
                else:
                    print(f"Voice ngắn hơn video. Sẽ làm nhanh video với tốc độ: {speed_video:.4f}")
                final = final.fx(vfx.speedx, speed_video)
                print(f"Thời lượng video sau khi điều chỉnh: {final.duration:.2f}s")
            # Hỏi người dùng muốn tắt hoàn toàn tiếng gốc không
            tat_goc = input("Bạn có muốn tắt hoàn toàn tiếng gốc không? (y/n, Enter để mặc định là n): ").strip().lower() == 'y'
            if tat_goc:
                final = final.set_audio(audio_voice)
            else:
                video_audio = final.audio.volumex(0.2) if final.audio else None
                audio_viet = audio_voice.volumex(2.0)
                if video_audio:
                    from moviepy.editor import CompositeAudioClip
                    final_audio = CompositeAudioClip([video_audio, audio_viet])
                else:
                    final_audio = audio_viet
                final = final.set_audio(final_audio)
        else:
            print("File voice không tồn tại!")
   

    # Xuất video
    base = os.path.basename(input_path)
    name, ext = os.path.splitext(base)
    output_path = os.path.join(EDIT_DIR, f"{name}_done{ext}")
    final = final.fl_image(ensure_final_rgb)
    print("\nTùy chọn xuất video:")
    print("1. Chất lượng cao (chậm)")
    print("2. Cân bằng (khuyến nghị)")
    print("3. Tốc độ nhanh")
    print("4. Siêu nhanh")
    export_quality = input("Chọn chế độ xuất (1-4, Enter để chọn mặc định 2): ").strip() or "2"
    optimize_video_export(final, output_path, export_quality)
    final.close()
    return output_path

def extract_audio(input_path, audio_path):
    clip = VideoFileClip(input_path)
    clip.audio.write_audiofile(audio_path)
    clip.close()
    return audio_path

def whisper_transcribe(audio_path):
    model = whisper.load_model("small")
    # Đầu tiên, để Whisper tự nhận diện
    result = model.transcribe(audio_path)
    print("Whisper tự nhận diện ngôn ngữ:", result['language'])
    if result['language'] in ['zh', 'zh-tw', 'yue']:
        return result['text'], result['segments'], result['language']
    # Nếu không phải tiếng Trung, thử ép các mã tiếng Trung
    lang_codes = ['zh', 'zh-tw', 'yue']
    best_result = result
    best_segments = result['segments']
    best_lang = result['language']
    for code in lang_codes:
        if code == result['language']:
            continue
        try:
            res = model.transcribe(audio_path, language=code)
            segments = res['segments']
            print(f"[DEBUG] Whisper thử mã ngôn ngữ {code}: {len(segments)} segments.")
            if len(segments) > len(best_segments):
                best_result = res
                best_segments = segments
                best_lang = code
        except Exception as e:
            print(f"[ERROR] Whisper lỗi với mã ngôn ngữ {code}: {e}")
    print(f"[INFO] Whisper chọn mã ngôn ngữ tốt nhất: {best_lang} với {len(best_segments)} segments.")
    return best_result['text'], best_result['segments'], best_lang

def translate_text(text, src='zh-cn', dest='vi'):
    translator = Translator()
    return translator.translate(text, src=src, dest=dest).text

def tts_vietnamese(text, tts_path):
    tts = gTTS(text, lang='vi')
    tts.save(tts_path)
    return tts_path

def merge_audio_to_video(video_path, audio_path, output_path):
    video = VideoFileClip(video_path)
    audio = AudioFileClip(audio_path)
    final = video.set_audio(audio)
    final.write_videofile(output_path, codec="libx264", audio_codec="aac")
    video.close()
    audio.close()
    return output_path

def create_srt(segments, srt_path, src_lang='zh-cn', dest_lang='vi', speed_voice=1.0, time_delay=0, duration_adjust=1.0):
    translator = Translator()
    subs = []
    src_lang = map_lang_code(src_lang)
    print(f"[DEBUG] Số lượng segments: {len(segments)}, src_lang: {src_lang}, dest_lang: {dest_lang}")
    for i, seg in enumerate(segments):
        # Điều chỉnh thời gian theo speed_voice
        start = seg['start'] / speed_voice
        end = seg['end'] / speed_voice
        text = seg['text']
        vi_text = text
        for attempt in range(3):  # Thử lại tối đa 3 lần nếu dịch lỗi
            try:
                vi_text = translator.translate(text, src=src_lang, dest=dest_lang).text
                break
            except Exception as e:
                print(f"[ERROR] Dịch lỗi ở segment {i}, lần thử {attempt+1}: {e}. Sẽ thử lại...")
                time.sleep(1)
        else:
            print(f"[ERROR] Dịch thất bại hoàn toàn ở segment {i}. Sử dụng nguyên bản tiếng gốc.")
        subs.append(srt.Subtitle(
            index=i+1,
            start=srt.srt_timestamp_to_timedelta(f"{int(start//3600):02}:{int((start%3600)//60):02}:{int(start%60):02},{int((start%1)*1000):03}"),
            end=srt.srt_timestamp_to_timedelta(f"{int(end//3600):02}:{int((end%3600)//60):02}:{int(end%60):02},{int((end%1)*1000):03}"),
            content=vi_text
        ))
    if not subs:
        print("[ERROR] Không có phụ đề nào được tạo. File SRT sẽ không được ghi ra.")
    else:
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt.compose(subs))
        print(f"[INFO] Đã ghi file SRT: {srt_path}")
    return srt_path

def menu():
    print("==== TOOL REUP VIDEO ====")
    print("1. Tải video")
    print("2. Xử lý video")
    print("3. Lưu video")
    print("4. Upload video (nâng cao)")
    print("5. Douyin -> Sub Việt -> Voice Việt -> Video mới")
    print("6. Thoát")
    choice = input("Chọn chức năng (1-6): ")
    return choice

def merge_voice_speedup(video_path, voice_path, output_path, speed=1.5):
    video = VideoFileClip(video_path)
    audio = AudioFileClip(voice_path)
    audio_fast = audio.fx(vfx.speedx, speed)
    # Đảm bảo audio không dài hơn video
    min_duration = min(video.duration, audio_fast.duration)
    audio_fast = audio_fast.subclip(0, min_duration)
    final = video.set_audio(audio_fast)
    final = final.set_duration(min_duration)
    final.write_videofile(output_path, codec="libx264", audio_codec="aac")
    video.close()
    audio.close()
    final.close()
    return output_path

def merge_mp3_files(input_folder, output_path):
    mp3_files = sorted(glob.glob(os.path.join(input_folder, '*.mp3')))
    if not mp3_files:
        print(f"Không tìm thấy file mp3 nào trong {input_folder}")
        return None
    combined = AudioSegment.empty()
    for mp3_file in mp3_files:
        audio = AudioSegment.from_mp3(mp3_file)
        combined += audio
    combined.export(output_path, format="mp3")
    print(f"Đã gộp {len(mp3_files)} file mp3 thành: {output_path}")
    return output_path

async def srt_to_voice_edge_tts(srt_path, output_mp3=None, output_folder=None, voice="vi-VN-NamMinhNeural"):
    import edge_tts
    with open(srt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    texts = []
    current_text = ""
    for line in lines:
        line = line.strip()
        if line.isdigit() or "-->" in line or line == "":
            if current_text:
                texts.append(current_text.strip())
                current_text = ""
        else:
            current_text += " " + line
    if current_text:
        texts.append(current_text.strip())

    if output_mp3:
        full_text = ' '.join(texts)
        communicate = edge_tts.Communicate(full_text, voice)
        await communicate.save(output_mp3)
        print(f"Đã tạo file mp3 tổng (Edge TTS): {output_mp3}")
    elif output_folder:
        import os
        os.makedirs(output_folder, exist_ok=True)
        for idx, text in enumerate(texts):
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(os.path.join(output_folder, f"line_{idx+1}.mp3"))
        print(f"Đã tạo các file mp3 nhỏ (Edge TTS) trong thư mục: {output_folder}")

def douyin_to_viet_video():
    choice = input("Bạn có muốn nhập link Douyin (1) hay đường dẫn file video đã tải (2)? Nhập 1 hoặc 2: ").strip()
    if choice == "1":
        url = input("Nhập URL video Douyin: ").strip()
        print("Đang tải video Douyin...")
        video_path = download_video(url)
        if not video_path:
            print("Vui lòng kiểm tra lại link video Douyin và thử lại!\n")
            return
    else:
        video_path = input("Nhập đường dẫn file video Douyin đã tải về: ").strip()
        if not os.path.isfile(video_path):
            print("File không tồn tại. Vui lòng kiểm tra lại đường dẫn!\n")
            return
    if not video_path.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v")):
        print("Vui lòng nhập đúng đường dẫn file VIDEO (mp4, mov, avi, mkv, webm, flv, wmv, m4v), không phải file phụ đề (.srt)!")
        return
    from moviepy.editor import VideoFileClip
    clip = VideoFileClip(video_path)

    # Hỏi người dùng muốn nhập path SRT hay tạo từ đầu
    print("Bạn muốn:")
    print("1. Nhập path file SRT có sẵn")
    print("2. Tạo phụ đề từ đầu (tách audio, nhận diện, dịch)")
    srt_choice = input("Chọn 1 hoặc 2 (Enter để mặc định là 2): ").strip() or "2"

    if srt_choice == "1":
        srt_path = input("Nhập đường dẫn file SRT: ").strip()
        if not os.path.isfile(srt_path):
            print("File SRT không tồn tại. Vui lòng kiểm tra lại đường dẫn!\n")
            return
        # Nhảy sang bước chuyển SRT thành voice
        srt_path_input = srt_path
        # ... (bỏ qua các bước tách audio, nhận diện, dịch)
        # Tiếp tục các bước chuyển SRT thành voice như bên dưới
    else:
        print(f"Đã tải: {video_path}")
        audio_path = os.path.splitext(video_path)[0] + "_audio.mp3"
        print("Tách audio...")
        extract_audio(video_path, audio_path)
        print("Nhận diện tiếng nói (Whisper)...")
        zh_text, segments, detected_lang = whisper_transcribe(audio_path)
        print(f"[DEBUG] Ngôn ngữ Whisper detect: {detected_lang}, Số segments: {len(segments)}")
        if not segments:
            print("[ERROR] Whisper không nhận diện được phụ đề/audio.")
            return
        detected_lang = map_lang_code(detected_lang)
        print(f"Ngôn ngữ gốc: {detected_lang}")
        print("Dịch phụ đề sang tiếng Việt...")
        vi_text = translate_text(zh_text, src=detected_lang, dest='vi')
        # Tạo file SRT phụ đề tiếng Việt
        srt_path = os.path.splitext(video_path)[0] + "_viet.srt"
        create_srt(segments, srt_path, src_lang=detected_lang, dest_lang='vi', speed_voice=1.5)
        print(f"Đã tạo file phụ đề: {srt_path}")
        srt_path_input = srt_path

    # Sau khi có srt_path_input
    print("Chọn giọng đọc:")
    print("1. Giọng nữ (Google gTTS)")
    print("2. Giọng nam (Edge TTS)")
    print("3. Giọng đọc tiếng Anh (Google gTTS hoặc Edge TTS)")
    print("4. Giọng nữ (Edge TTS)")  # Thêm lựa chọn giọng nữ Edge TTS
    print("5. Giọng đọc Coqui TTS (lỗi không sài được)")
    print("6. Giọng đọc FPT.AI (cần API Key)")
    chon_giong = input("Chọn 1, 2, 3, 4, 5 hoặc 6 (Enter để mặc định là 1): ").strip() or "1"

    print("Bạn muốn tạo:")
    print("1. Một file mp3 tổng duy nhất cho toàn bộ subtitle")
    print("2. Nhiều file mp3 nhỏ cho từng dòng subtitle")
    chon_voice = input("Chọn 1 hoặc 2 (Enter để mặc định là 1): ").strip() or "1"

    if chon_giong == "1":
        # Google gTTS (giọng nữ Việt, mặc định)
        if chon_voice == "2":
            output_voice_folder = os.path.splitext(srt_path_input)[0] + "_viet_voice"
            srt_to_voice(srt_path_input, output_folder=output_voice_folder)
            merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_viet_voice.mp3"
            gop_mp3 = input("Bạn có muốn gộp tất cả file mp3 nhỏ thành 1 file mp3 tổng không? (y/n): ").strip().lower()
            if gop_mp3 == 'y':
                merge_mp3_files(output_voice_folder, merged_mp3_path)
            else:
                print(f"Bạn có thể tự gộp bằng hàm merge_mp3_files hoặc dùng file mp3 tổng: {merged_mp3_path}")
        else:
            merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_viet_voice.mp3"
            srt_to_voice(srt_path_input, output_mp3=merged_mp3_path)
    elif chon_giong == "5":
        # Coqui TTS tích hợp sẵn model đa ngôn ngữ xtts_v2
        model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
        print(f"[INFO] Sử dụng model Coqui TTS: {model_name}")
        if chon_voice == "2":
            output_voice_folder = os.path.splitext(srt_path_input)[0] + "_coqui_voice"
            srt_to_voice_coqui(srt_path_input, output_folder=output_voice_folder, model_name=model_name)
            merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_coqui_voice.mp3"
            gop_mp3 = input("Bạn có muốn gộp tất cả file mp3 nhỏ thành 1 file mp3 tổng không? (y/n): ").strip().lower()
            if gop_mp3 == 'y':
                merge_mp3_files(output_voice_folder, merged_mp3_path)
            else:
                print(f"Bạn có thể tự gộp bằng hàm merge_mp3_files hoặc dùng file mp3 tổng: {merged_mp3_path}")
        else:
            merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_coqui_voice.mp3"
            srt_to_voice_coqui(srt_path_input, output_mp3=merged_mp3_path, model_name=model_name)
    elif chon_giong == "2":
        # Edge TTS (giọng nam Việt)
        import asyncio
        voice_name = "vi-VN-NamMinhNeural"
        if chon_voice == "2":
            output_voice_folder = os.path.splitext(srt_path_input)[0] + "_voice"
            asyncio.run(srt_to_voice_edge_tts(srt_path_input, output_folder=output_voice_folder, voice=voice_name))
            merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_viet_voice.mp3"
            gop_mp3 = input("Bạn có muốn gộp tất cả file mp3 nhỏ thành 1 file mp3 tổng không? (y/n): ").strip().lower()
            if gop_mp3 == 'y':
                merge_mp3_files(output_voice_folder, merged_mp3_path)
            else:
                print(f"Bạn có thể tự gộp bằng hàm merge_mp3_files hoặc dùng file mp3 tổng: {merged_mp3_path}")
        else:
            merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_viet_voice.mp3"
            asyncio.run(srt_to_voice_edge_tts(srt_path_input, output_mp3=merged_mp3_path, voice=voice_name))
    elif chon_giong == "4":
        # Edge TTS (giọng nữ Việt)
        import asyncio
        voice_name = "vi-VN-HoaiMyNeural"
        if chon_voice == "2":
            output_voice_folder = os.path.splitext(srt_path_input)[0] + "_voice_female"
            asyncio.run(srt_to_voice_edge_tts(srt_path_input, output_folder=output_voice_folder, voice=voice_name))
            merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_viet_voice_female.mp3"
            gop_mp3 = input("Bạn có muốn gộp tất cả file mp3 nhỏ thành 1 file mp3 tổng không? (y/n): ").strip().lower()
            if gop_mp3 == 'y':
                merge_mp3_files(output_voice_folder, merged_mp3_path)
            else:
                print(f"Bạn có thể tự gộp bằng hàm merge_mp3_files hoặc dùng file mp3 tổng: {merged_mp3_path}")
        else:
            merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_viet_voice_female.mp3"
            asyncio.run(srt_to_voice_edge_tts(srt_path_input, output_mp3=merged_mp3_path, voice=voice_name))
    elif chon_giong == "3":
        # Giọng đọc tiếng Anh
        print("Chọn engine tiếng Anh:")
        print("1. Google gTTS (giọng nữ)")
        print("2. Edge TTS (giọng nữ Mỹ)")
        chon_engine = input("Chọn 1 hoặc 2 (Enter để mặc định là 1): ").strip() or "1"
        if chon_engine == "2":
            import asyncio
            voice_name = "en-US-AriaNeural"
            if chon_voice == "2":
                output_voice_folder = os.path.splitext(srt_path_input)[0] + "_en_voice"
                asyncio.run(srt_to_voice_edge_tts(srt_path_input, output_folder=output_voice_folder, voice=voice_name))
                merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_en_voice.mp3"
                gop_mp3 = input("Bạn có muốn gộp tất cả file mp3 nhỏ thành 1 file mp3 tổng không? (y/n): ").strip().lower()
                if gop_mp3 == 'y':
                    merge_mp3_files(output_voice_folder, merged_mp3_path)
                else:
                    print(f"Bạn có thể tự gộp bằng hàm merge_mp3_files hoặc dùng file mp3 tổng: {merged_mp3_path}")
            else:
                merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_en_voice.mp3"
                asyncio.run(srt_to_voice_edge_tts(srt_path_input, output_mp3=merged_mp3_path, voice=voice_name))
        else:
            # Google gTTS tiếng Anh
            if chon_voice == "2":
                output_voice_folder = os.path.splitext(srt_path_input)[0] + "_en_voice"
                srt_to_voice(srt_path_input, output_folder=output_voice_folder, lang='en')
                merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_en_voice.mp3"
                gop_mp3 = input("Bạn có muốn gộp tất cả file mp3 nhỏ thành 1 file mp3 tổng không? (y/n): ").strip().lower()
                if gop_mp3 == 'y':
                    merge_mp3_files(output_voice_folder, merged_mp3_path)
                else:
                    print(f"Bạn có thể tự gộp bằng hàm merge_mp3_files hoặc dùng file mp3 tổng: {merged_mp3_path}")
            else:
                merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_en_voice.mp3"
                srt_to_voice(srt_path_input, output_mp3=merged_mp3_path, lang='en')
    elif chon_giong == "6":
        api_key = input("Nhập API Key FPT.AI: ").strip()
        voice = input("Nhập tên voice (ví dụ: banmai, lannhi, leminh): ").strip() or "banmai"
        speed = input("Nhập tốc độ đọc (0 là mặc định, -2 chậm, 2 nhanh): ").strip()
        try:
            speed = int(speed)
        except:
            speed = 0
        if chon_voice == "2":
            output_voice_folder = os.path.splitext(srt_path_input)[0] + "_fpt_voice"
            srt_to_voice_fpt(srt_path_input, api_key, output_folder=output_voice_folder, voice=voice, speed=speed)
            merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_fpt_voice.mp3"
            gop_mp3 = input("Bạn có muốn gộp tất cả file mp3 nhỏ thành 1 file mp3 tổng không? (y/n): ").strip().lower()
            if gop_mp3 == 'y':
                merge_mp3_files(output_voice_folder, merged_mp3_path)
            else:
                print(f"Bạn có thể tự gộp bằng hàm merge_mp3_files hoặc dùng file mp3 tổng: {merged_mp3_path}")
        else:
            merged_mp3_path = os.path.splitext(srt_path_input)[0] + "_fpt_voice.mp3"
            srt_to_voice_fpt(srt_path_input, api_key, output_mp3=merged_mp3_path, voice=voice, speed=speed)

def srt_to_voice(srt_path, output_mp3=None, output_folder=None, lang='vi'):
    """
    Đọc file SRT và chuyển nội dung thành giọng nói (Google gTTS).
    Nếu output_mp3: tạo 1 file mp3 tổng.
    Nếu output_folder: tạo nhiều file mp3 nhỏ cho từng dòng subtitle.
    """
    from gtts import gTTS
    import os
    import re

    with open(srt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    texts = []
    current_text = ""
    for line in lines:
        line = line.strip()
        if line.isdigit() or "-->" in line or line == "":
            if current_text:
                texts.append(current_text.strip())
                current_text = ""
        else:
            current_text += " " + line
    if current_text:
        texts.append(current_text.strip())

    if output_mp3:
        # Gộp tất cả thành 1 file mp3
        full_text = ' '.join(texts)
        if not full_text.strip():
            print(f"[ERROR] File SRT không có nội dung hợp lệ để chuyển thành voice! Kiểm tra lại file: {srt_path}")
            return
        tts = gTTS(full_text, lang=lang)
        tts.save(output_mp3)
        print(f"Đã tạo file mp3 tổng: {output_mp3}")
    elif output_folder:
        os.makedirs(output_folder, exist_ok=True)
        for idx, text in enumerate(texts):
            tts = gTTS(text, lang=lang)
            tts.save(os.path.join(output_folder, f"line_{idx+1}.mp3"))
        print(f"Đã tạo các file mp3 nhỏ trong thư mục: {output_folder}")

def srt_to_voice_coqui(srt_path, output_mp3=None, output_folder=None, model_name=None, speaker=None, speaker_wav=None):
    """
    Đọc file SRT và chuyển nội dung thành giọng nói bằng Coqui TTS.
    Nếu output_mp3: tạo 1 file mp3 tổng.
    Nếu output_folder: tạo nhiều file mp3 nhỏ cho từng dòng subtitle.
    model_name: tên model Coqui TTS (bắt buộc)
    speaker: tên speaker (nếu model hỗ trợ, ví dụ: 'vi_001')
    speaker_wav: file mẫu giọng nói (bắt buộc với xtts_v2)
    """
    if not model_name:
        print("[ERROR] Bạn phải cung cấp tên model Coqui TTS!")
        return
    from TTS.api import TTS
    tts = TTS(model_name)

    is_xtts = 'xtts' in model_name.lower()
    is_multi_speaker = hasattr(tts, 'speakers') and tts.speakers and not is_xtts

    # Xác định language
    if is_xtts:
        supported_xtts_langs = ['en', 'es', 'fr', 'de', 'it', 'pt', 'pl', 'tr', 'ru', 'nl', 'cs', 'ar', 'zh-cn', 'hu', 'ko', 'ja', 'hi']
        print(f"Các ngôn ngữ xtts_v2 hỗ trợ: {supported_xtts_langs}")
        language = input(f"Nhập mã ngôn ngữ muốn synthesize (ví dụ: en, zh-cn) [Enter để mặc định zh-cn]: ").strip() or "zh-cn"
        if language not in supported_xtts_langs:
            print(f"[WARN] Ngôn ngữ không hỗ trợ, sẽ dùng zh-cn.")
            language = "zh-cn"
    else:
        language = "vi"

    # Nếu là xtts_v2 (voice cloning), yêu cầu speaker_wav
    if is_xtts:
        while not speaker_wav or not os.path.isfile(speaker_wav):
            speaker_wav = input("Nhập đường dẫn file mẫu giọng nói (wav, bắt buộc cho xtts_v2): ").strip()
            if not os.path.isfile(speaker_wav):
                print("[ERROR] File mẫu giọng nói không tồn tại. Vui lòng nhập lại!")
    # Nếu là multi-speaker thông thường, yêu cầu speaker
    elif is_multi_speaker:
        print(f"[INFO] Model hỗ trợ các speaker: {tts.speakers}")
        while True:
            nonlocal_speaker = speaker or input(f"Nhập tên speaker muốn dùng (Enter để mặc định {tts.speakers[0]}): ").strip()
            if not nonlocal_speaker:
                nonlocal_speaker = tts.speakers[0]
            if nonlocal_speaker in tts.speakers:
                speaker = nonlocal_speaker
                break
            print("Speaker không hợp lệ, vui lòng chọn lại!")

    with open(srt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    texts = []
    current_text = ""
    for line in lines:
        line = line.strip()
        if line.isdigit() or "-->" in line or line == "":
            if current_text:
                texts.append(current_text.strip())
                current_text = ""
        else:
            current_text += " " + line
    if current_text:
        texts.append(current_text.strip())

    def call_tts_to_file(text, file_path):
        if is_xtts:
            tts.tts_to_file(text=text, speaker_wav=speaker_wav, language=language, file_path=file_path)
        elif is_multi_speaker:
            tts.tts_to_file(text=text, speaker=speaker, language=language, file_path=file_path)
        else:
            tts.tts_to_file(text=text, language=language, file_path=file_path)

    if output_mp3:
        full_text = ' '.join(texts)
        if not full_text.strip():
            print(f"[ERROR] File SRT không có nội dung hợp lệ để chuyển thành voice! Kiểm tra lại file: {srt_path}")
            return
        call_tts_to_file(full_text, output_mp3)
        print(f"Đã tạo file mp3 tổng (Coqui TTS): {output_mp3}")
    elif output_folder:
        os.makedirs(output_folder, exist_ok=True)
        for idx, text in enumerate(texts):
            file_path = os.path.join(output_folder, f"line_{idx+1}.mp3")
            call_tts_to_file(text, file_path)
        print(f"Đã tạo các file mp3 nhỏ (Coqui TTS) trong thư mục: {output_folder}")

def fpt_tts(text, api_key, voice='banmai', speed=0, output_path='output.mp3'):
    """
    Gọi API FPT.AI TTS để chuyển text thành file mp3.
    """
    import requests
    url = "https://api.fpt.ai/hmi/tts/v5"
    headers = {
        "api-key": api_key,
        "speed": str(speed),
        "voice": voice
    }
    response = requests.post(url, data=text.encode('utf-8'), headers=headers)
    if response.status_code == 200:
        # FPT trả về link download file mp3
        audio_url = response.json().get('async')
        if not audio_url:
            print("[ERROR] Không nhận được link audio từ FPT.AI.")
            return None
        # Tải file mp3 về
        import time
        for _ in range(10):  # Thử lại nhiều lần nếu file chưa sẵn sàng
            audio_response = requests.get(audio_url)
            if audio_response.status_code == 200 and audio_response.headers.get('Content-Type', '').startswith('audio'):
                with open(output_path, 'wb') as f:
                    f.write(audio_response.content)
                print(f"Đã tạo file mp3: {output_path}")
                return output_path
            time.sleep(1)
        print("[ERROR] Không thể tải file audio từ FPT.AI sau nhiều lần thử.")
        return None
    else:
        print("Lỗi gọi API FPT.AI:", response.text)
        return None

def srt_to_voice_fpt(srt_path, api_key, output_mp3=None, output_folder=None, voice='banmai', speed=0):
    """
    Đọc file SRT và chuyển nội dung thành giọng nói bằng FPT.AI TTS.
    Nếu output_mp3: tạo 1 file mp3 tổng.
    Nếu output_folder: tạo nhiều file mp3 nhỏ cho từng dòng subtitle.
    api_key: API Key FPT.AI
    voice: tên voice (ví dụ: banmai, lannhi, leminh)
    speed: tốc độ đọc (0 là mặc định, -2 chậm, 2 nhanh)
    """
    with open(srt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    texts = []
    current_text = ""
    for line in lines:
        line = line.strip()
        if line.isdigit() or "-->" in line or line == "":
            if current_text:
                texts.append(current_text.strip())
                current_text = ""
        else:
            current_text += " " + line
    if current_text:
        texts.append(current_text.strip())

    if output_mp3:
        full_text = ' '.join(texts)
        if not full_text.strip():
            print(f"[ERROR] File SRT không có nội dung hợp lệ để chuyển thành voice! Kiểm tra lại file: {srt_path}")
            return
        fpt_tts(full_text, api_key, voice=voice, speed=speed, output_path=output_mp3)
        print(f"Đã tạo file mp3 tổng (FPT.AI): {output_mp3}")
    elif output_folder:
        os.makedirs(output_folder, exist_ok=True)
        for idx, text in enumerate(texts):
            file_path = os.path.join(output_folder, f"line_{idx+1}.mp3")
            fpt_tts(text, api_key, voice=voice, speed=speed, output_path=file_path)
        print(f"Đã tạo các file mp3 nhỏ (FPT.AI) trong thư mục: {output_folder}")

def map_lang_code(code):
    """
    Chuẩn hóa mã ngôn ngữ từ Whisper về dạng Google Translate/gTTS.
    """
    code = code.lower()
    if code in ["zh", "zh-cn", "zh-hans"]:
        return "zh-cn"
    if code in ["zh-tw", "zh-hant"]:
        return "zh-tw"
    if code in ["yue"]:
        return "zh-cn"  # Google không hỗ trợ yue, dùng zh-cn
    if code.startswith("vi"):
        return "vi"
    if code.startswith("en"):
        return "en"
    return code

def force_aspect_ratio(clip, target_ratio=(16, 9), method="pad"):
    """
    Ép video về đúng tỉ lệ target_ratio (mặc định 16:9).
    method: "pad" (thêm viền đen), "crop" (cắt cho vừa)
    """
    w, h = clip.size
    target_w, target_h = target_ratio
    target_aspect = target_w / target_h
    current_aspect = w / h

    if abs(current_aspect - target_aspect) < 0.01:
        return clip  # Đã đúng tỉ lệ

    if method == "pad":
        # Thêm viền đen
        if current_aspect > target_aspect:
            # Video quá ngang, thêm viền trên/dưới
            new_h = int(w / target_aspect)
            pad = (new_h - h) // 2
            return clip.margin(top=pad, bottom=pad, color=(0,0,0)).resize((w, new_h))
        else:
            # Video quá dọc, thêm viền trái/phải
            new_w = int(h * target_aspect)
            pad = (new_w - w) // 2
            return clip.margin(left=pad, right=pad, color=(0,0,0)).resize((new_w, h))
    elif method == "crop":
        # Crop cho vừa
        if current_aspect > target_aspect:
            # Crop chiều ngang
            new_w = int(h * target_aspect)
            x1 = (w - new_w) // 2
            return clip.crop(x1=x1, y1=0, x2=x1+new_w, y2=h)
        else:
            # Crop chiều dọc
            new_h = int(w / target_aspect)
            y1 = (h - new_h) // 2
            return clip.crop(x1=0, y1=y1, x2=w, y2=y1+new_h)
    else:
        return clip

def sync_video_to_voice(video_path, voice_path, speed_voice, output_path, export_quality="2"):
    """
    Điều chỉnh tốc độ video để thời lượng video khớp với thời lượng voice đã chỉnh tốc độ.
    - video_path: đường dẫn video gốc
    - voice_path: đường dẫn file voice (mp3)
    - speed_voice: tốc độ mong muốn cho voice (float, ví dụ 1.3)
    - output_path: đường dẫn file video xuất ra
    - export_quality: preset chất lượng ("1" cao, "2" cân bằng, ...)
    """
    from moviepy.editor import VideoFileClip, AudioFileClip, vfx
    import os
    print(f"[INFO] Đọc video: {video_path}")
    video = VideoFileClip(video_path)
    print(f"[INFO] Đọc voice: {voice_path}")
    audio = AudioFileClip(voice_path)
    # Tính thời lượng voice sau khi chỉnh tốc độ
    voice_duration = audio.duration
    voice_duration_new = voice_duration / speed_voice
    video_duration = video.duration
    print(f"[INFO] Thời lượng video gốc: {video_duration:.2f}s, voice gốc: {voice_duration:.2f}s, voice sau speed: {voice_duration_new:.2f}s")
    # Tính hệ số điều chỉnh tốc độ video
    video_speed = video_duration / voice_duration_new
    print(f"[INFO] Hệ số điều chỉnh tốc độ video: {video_speed:.3f}")
    # Chỉnh tốc độ video
    video_new = video.fx(vfx.speedx, video_speed)
    # Đặt lại audio cho video (nếu muốn ghép voice luôn)
    # Nếu muốn giữ tiếng gốc, có thể mix lại
    video_new = video_new.set_audio(audio.fx(vfx.speedx, speed_voice))
    # Xuất video
    print(f"[INFO] Xuất video ra: {output_path}")
    optimize_video_export(video_new, output_path, export_quality)
    video.close()
    audio.close()
    video_new.close()
    print(f"[INFO] Đã xuất video mới với thời lượng ≈ voice!")

def main():
    ensure_dirs()
    mpyconf.change_settings({"IMAGEMAGICK_BINARY": r"C:\\Program Files\\ImageMagick-7.1.1-Q16-HDRI\\magick.exe"})
    print(torch.cuda.is_available())
    while True:
        choice = menu()
        if choice == "1":
            url = input("Nhập URL video TikTok hoặc YouTube Shorts: ").strip()
            if is_processed(url):
                print("Video này đã được xử lý trước đó.")
                continue
            print("Đang tải video...")
            video_path = download_video(url)
            if not video_path:
                print("Vui lòng kiểm tra lại link video và thử lại!\n")
                continue
            print(f"Đã tải: {video_path}")
        elif choice == "2":
            input_path = input("Nhập đường dẫn file video cần xử lý: ").strip()
            processed_path = process_video(input_path)
            print(f"Đã xử lý và lưu tại: {processed_path}")
            log_processed(input_path)
        elif choice == "3":
            print("Video đã được lưu trong thư mục downloads.")
        elif choice == "4":
            print("Chọn nền tảng để upload:")
            print("1. YouTube")
            print("2. Facebook")
            print("3. TikTok")
            print("4. Lên lịch upload YouTube từ file schedule.txt")
            platform = input("Nhập số nền tảng muốn upload (1-4): ").strip()
            if platform == "4":
                schedule_file = input("Nhập đường dẫn file schedule.txt (Enter để mặc định: schedule.txt): ").strip() or "schedule.txt"
                if not os.path.isfile(schedule_file):
                    print(f"Không tìm thấy file {schedule_file}")
                    continue
                schedule = read_schedule_file(schedule_file)
                for item in schedule:
                    video_path = item['video_path']
                    title = item['title']
                    desc = item['desc']
                    tags = item['tags']
                    scheduled_time = item.get('scheduled_time')
                    # Nếu desc là đường dẫn file, đọc nội dung file đó
                    if os.path.isfile(desc):
                        with open(desc, encoding='utf-8') as f:
                            desc_content = f.read()
                    else:
                        desc_content = desc
                    print(f"Đang upload video {video_path} lên YouTube, lịch: {scheduled_time}")
                    upload_youtube(video_path, title, desc_content, tags, scheduled_time=scheduled_time)
                print("Đã hoàn thành upload theo lịch!")
                continue
            video_path = input("Nhập đường dẫn file video muốn upload: ").strip()
            srt_path = input("Nhập đường dẫn file SRT phụ đề (nếu có, Enter để bỏ qua): ").strip()
            default_keywords = ["từ khóa 1", "từ khóa 2", "từ khóa 3"]  # Sửa thành từ khóa của bạn
            custom = input("Bạn có muốn tự nhập tiêu đề và hashtag không? (y/n): ").strip().lower() == 'y'
            if custom:
                title = input("Nhập tiêu đề video: ").strip()
                desc_file = input("Nhập đường dẫn file mô tả (Enter để nhập tay): ").strip()
                if desc_file:
                    with open(desc_file, encoding='utf-8') as f:
                        desc = f.read()
                else:
                    desc = input("Nhập mô tả video: ").strip()
                hashtags = input("Nhập hashtag (cách nhau bởi dấu cách, ví dụ: #abc #xyz): ").strip()
            else:
                title, desc, hashtags = generate_title_and_desc(srt_path, default_keywords) if srt_path else ("Video Reup", "", "")
            if platform == "1":
                print("Đang upload lên YouTube...")
                tags = [tag.strip("#") for tag in hashtags.split() if tag.startswith("#")]
                upload_youtube(video_path, title, desc, tags)
            elif platform == "2":
                print("Đang upload lên Facebook...")
                page_access_token, page_id = load_fb_config()
                if not page_access_token or not page_id:
                    page_access_token = input("Nhập page_access_token: ").strip()
                    page_id = input("Nhập page_id: ").strip()
                    save_fb_config(page_access_token, page_id)
                else:
                    print(f"Đã tự động lấy page_access_token và page_id từ {FB_CONFIG_FILE}")
                    print(f"page_id: {page_id}")
                upload_facebook(video_path, title, desc, hashtags, page_access_token, page_id)
            elif platform == "3":
                print("Đang upload lên TikTok...")
                # upload_tiktok(video_path, title, desc, hashtags)
                print("Chức năng upload TikTok đang phát triển.")
            else:
                print("Lựa chọn không hợp lệ.")
        elif choice == "5":
            douyin_to_viet_video()
        elif choice == "6":
            print("Thoát tool.")
            break
        else:
            print("Lựa chọn không hợp lệ. Vui lòng chọn lại.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Lỗi:", e)
        traceback.print_exc()        
        