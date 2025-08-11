
import streamlit as st
import os

def main():
    st.set_page_config(page_title="Test đọc SRT bằng Coqui TTS", layout="wide")
    st.title("Test đọc file SRT bằng Coqui TTS (xtts_v2)")
    srt_file = st.file_uploader("Chọn file SRT để đọc thành giọng nói", type=["srt"])
    if srt_file:
        srt_path = os.path.join("downloads", srt_file.name)
        os.makedirs("downloads", exist_ok=True)
        with open(srt_path, "wb") as f:
            f.write(srt_file.read())
        st.success(f"Đã upload file: {srt_path}")
        if st.button("Tạo file mp3 đọc SRT bằng Coqui TTS (xtts_v2)"):
            with st.spinner("Đang tạo file mp3 bằng Coqui TTS..."):
                try:
                    from main import srt_to_voice_coqui
                    output_mp3 = os.path.splitext(srt_path)[0] + "_xttsv2.mp3"
                    model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
                    srt_to_voice_coqui(srt_path, output_mp3=output_mp3, model_name=model_name)
                    st.success(f"Đã tạo file mp3: {output_mp3}")
                    audio_file = open(output_mp3, "rb")
                    st.audio(audio_file.read(), format="audio/mp3")
                    st.download_button("Tải file mp3", open(output_mp3, "rb"), file_name=os.path.basename(output_mp3))
                except Exception as e:
                    st.error(f"Lỗi khi tạo file mp3: {e}")

if __name__ == "__main__":
    main() 