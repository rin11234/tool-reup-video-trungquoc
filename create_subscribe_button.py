from PIL import Image, ImageDraw, ImageFont
import os

def create_subscribe_button():
    # Tạo ảnh nút Subscribe
    width, height = 200, 50
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))  # Trong suốt
    draw = ImageDraw.Draw(img)
    
    # Vẽ nền nút màu đỏ YouTube
    draw.rectangle([0, 0, width, height], fill=(255, 0, 0, 255), outline=None)
    
    # Thêm chữ SUBSCRIBE màu trắng
    try:
        font = ImageFont.truetype("fonts/arial.ttf", 30)
    except:
        font = ImageFont.load_default()
    
    text = "SUBSCRIBE"
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    
    # Lưu ảnh
    os.makedirs("tittle", exist_ok=True)
    output_path = "tittle/subscribe_button.png"
    img.save(output_path, "PNG")
    print(f"Đã tạo nút Subscribe: {output_path}")

if __name__ == "__main__":
    create_subscribe_button() 