import os
import cv2
from PIL import Image, ImageDraw, ImageFont

def create_youtube_thumbnail_from_file(input_path, title, output_path=None, frame_time=None):
    ext = os.path.splitext(input_path)[1].lower()
    if ext in ['.mp4', '.avi', '.mov', '.mkv']:
        video = cv2.VideoCapture(input_path)
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = video.get(cv2.CAP_PROP_FPS)
        if fps == 0:
            print("Không thể đọc thông tin FPS từ video. Có thể file bị lỗi hoặc không đúng định dạng.")
            return
        duration = total_frames / fps
        if frame_time is None:
            print(f"\nTổng thời lượng video: {duration:.2f} giây")
            while True:
                try:
                    frame_time = float(input("Nhập thời điểm muốn lấy frame (giây): "))
                    if 0 <= frame_time <= duration:
                        break
                    print(f"Thời điểm phải từ 0 đến {duration:.2f} giây")
                except ValueError:
                    print("Vui lòng nhập số hợp lệ")
        video.set(cv2.CAP_PROP_POS_FRAMES, frame_time * fps)
        ret, frame = video.read()
        if not ret:
            print("Không thể đọc frame từ video")
            return None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        video.release()
    else:
        img = Image.open(input_path)
    width, height = 1280, 720
    img = img.resize((width, height), Image.Resampling.LANCZOS)
    overlay = Image.new('RGBA', (width//2, height), (255, 255, 255, 180))
    img = img.convert('RGBA')
    img.paste(overlay, (0, 0), overlay)
    draw = ImageDraw.Draw(img)
    font_path = r"fonts/arial.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 80)
    except:
        title_font = ImageFont.load_default()
        print("Không tìm thấy font, sử dụng font mặc định")
    words = title.split()
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        test_line = ' '.join(current_line)
        if title_font.getlength(test_line) > width//2 - 40:
            if len(current_line) > 1:
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                lines.append(test_line)
                current_line = []
    if current_line:
        lines.append(' '.join(current_line))
    y = 100
    for line in lines:
        draw.text((40, y), line, font=title_font, fill='black')
        y += title_font.size + 10
    subscribe_path = "tittle/subscribe_button.png"
    if os.path.isfile(subscribe_path):
        subscribe_img = Image.open(subscribe_path)
        subscribe_img = subscribe_img.resize((200, 50), Image.Resampling.LANCZOS)
        img.paste(subscribe_img, (40, height - 100), subscribe_img)
    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + "_thumb.jpg"
    img = img.convert('RGB')
    img.save(output_path, "JPEG", quality=95)
    print(f"Đã tạo thumbnail: {output_path}")
    return output_path

if __name__ == "__main__":
    input_path = input("Nhập đường dẫn file video hoặc ảnh: ").strip()
    title = input("Nhập text tiêu đề cho thumbnail: ").strip()
    create_youtube_thumbnail_from_file(input_path, title)