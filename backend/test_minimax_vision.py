import base64
import os
import fitz
from pathlib import Path
from io import BytesIO

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimaxi.com/anthropic/v1"

def extract_page_as_image(pdf_path: str, page_num: int) -> bytes:
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=150)
    doc.close()
    return pix.tobytes("png")

def test_minimax_vision():
    from anthropic import Anthropic

    client = Anthropic(
        api_key="sk-cp-oqT6nOabucgS2-PRLM8Cu3dp09x4F3oLfeVY7AIzSi3Q4FFS1Z16P7TnTadi6qzorRkOOtbkGlF_wt5GFiVsyPMKQX9Nj5rBInuoEH4onQ3HBmHvN3W1jo0",
        base_url="https://api.minimaxi.com/anthropic",
    )

    pdf_path = Path(__file__).parent / "uploads/546211fe-9034-4d26-88d4-3c47853c7686_25中级会计-实务官方教材电子书.pdf"
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return

    image_data = extract_page_as_image(str(pdf_path), 6)
    image_b64 = base64.b64encode(image_data).decode("utf-8")

    print(f"Extracted page 7, image size: {len(image_data)} bytes")

    response = client.messages.create(
        model="MiniMax-M2.7",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请描述这张图片的内容。"
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64
                        }
                    }
                ]
            }
        ]
    )

    print("Response type:", type(response))
    print("Response content:", response.content)

if __name__ == "__main__":
    test_minimax_vision()