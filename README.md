# TOOL REUP VIDEO - HƯỚNG DẪN SỬ DỤNG

## 1. Giới thiệu
Tool này giúp tải, xử lý, tạo phụ đề, chuyển giọng nói, và upload video lên các nền tảng như YouTube, Facebook, TikTok. Hỗ trợ reup Douyin, TikTok, Shorts, dịch phụ đề, ghép voice Việt, v.v.

## 2. Yêu cầu hệ thống
- Python >= 3.8 (khuyến nghị Python 3.10 hoặc 3.11)
- Hệ điều hành: Windows 10/11 hoặc Linux
- Đã cài đặt ffmpeg (nếu dùng MoviePy)

## 3. Cài đặt tool từ GitHub
```bash
git clone https://github.com/<tên-tài-khoản>/<tên-repo>.git
cd <tên-repo>
```

## 4. Tạo và kích hoạt môi trường ảo (khuyến nghị)
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# hoặc
source venv/bin/activate  # Linux/Mac
```

## 5. Cài đặt các thư viện cần thiết
```bash
pip install -r requirements.txt
```

## 6. Chạy tool
```bash
python main.py
```

## 7. Hướng dẫn sử dụng cơ bản
- Khi chạy tool, sẽ có menu hướng dẫn từng bước (tải video, xử lý, tạo phụ đề, ghép voice, upload, ...).
- Làm theo hướng dẫn trên màn hình, nhập link video hoặc đường dẫn file khi được hỏi.
- Để reup Douyin sang video tiếng Việt: chọn chức năng số 5 trong menu.
- Để tải video TikTok/Shorts: chọn chức năng số 1.
- Để xử lý video (cắt, hiệu ứng, ghép voice): chọn chức năng số 2.
- Để upload video: chọn chức năng số 4.

## 8. Hướng dẫn nhập API key cho OpenAI (dịch SRT bằng ChatGPT)
- Khi dùng chức năng dịch SRT bằng ChatGPT, lần đầu tool sẽ hỏi API key, bạn nhập vào và tool sẽ tự lưu lại cho lần sau.
- Để lấy API key: Đăng nhập https://platform.openai.com/ > API Keys > Create new secret key.
- Có thể lưu vào file `openai_api_key.txt` trong thư mục tool (1 dòng, không xuống dòng).

## 9. Lưu ý lỗi phổ biến và cách khắc phục
- **Lỗi `ModuleNotFoundError`:** Chạy `pip install <tên_thư_viện>` để cài thêm.
- **Lỗi `AttributeError: module 'httpcore' has no attribute 'SyncHTTPTransport'`:** Đảm bảo đã cài đúng `httpcore==0.15.0` và `googletrans==4.0.0-rc1`.
- **Lỗi `openai.ChatCompletion` không hỗ trợ:** Đảm bảo dùng `openai==0.28` hoặc sửa code theo API mới.
- **Lỗi Permission khi lưu file:** Đảm bảo đường dẫn lưu là file, không phải thư mục.
- **Lỗi không nhận diện được phụ đề/audio:** Kiểm tra lại file đầu vào.

## 10. Đóng góp & Liên hệ
- Nếu có lỗi hoặc góp ý, vui lòng tạo issue trên GitHub hoặc liên hệ trực tiếp.
- Đóng góp code: fork repo, tạo pull request. 