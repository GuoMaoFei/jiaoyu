import base64
import httpx
import json
import pymupdf
import os

IMAGE_PATH = r"C:\Users\茂飞\Downloads\ScreenShot_2026-03-21_202906_072.png"
API_KEY = "f4457a91-7260-49df-b346-9cf771c6e58d"
MODEL = "kimi-k2.5"
BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"

def test_kimi_ocr_on_image():
    with open(IMAGE_PATH, "rb") as f:
        img_data = f.read()
    img_base64 = base64.b64encode(img_data).decode("utf-8")

    message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "你是一个精准的 OCR 专家。请仔细阅读这张图片，提取其中的全部文字。直接输出结果，不要有任何解释。",
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_base64}"},
            },
        ],
    }

    print("[Test] Testing Kimi-2.5 VLM OCR on screenshot...")
    client = httpx.Client(timeout=120.0)
    response = client.post(
        f"{BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": MODEL, "messages": [message], "temperature": 0, "max_tokens": 8192},
    )
    client.close()

    if response.status_code == 200:
        result = response.json()
        extracted_text = result["choices"][0]["message"]["content"]
        tokens = result.get("usage", {}).get("total_tokens", 0)
        print(f"[Test] SUCCESS! Tokens used: {tokens}")
        print(f"[Test] Extracted text preview (800 chars):\n{extracted_text[:800]}")
        return extracted_text
    else:
        print(f"[Test] FAILED! Status: {response.status_code}")
        print(response.text)
        return None

def test_kimi_ocr_on_pdf_page():
    import tempfile

    pdf_path = IMAGE_PATH.replace(".png", ".pdf")
    if not os.path.exists(pdf_path):
        print(f"[Test] PDF not found at {pdf_path}, skipping PDF test")
        return None

    print(f"\n[Test] Testing Kimi-2.5 VLM OCR on PDF page 0...")

    doc = pymupdf.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
    img_data = pix.tobytes("png")
    img_base64 = base64.b64encode(img_data).decode("utf-8")
    doc.close()

    message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "你是一个精准的 OCR 专家。请仔细阅读这张图片，提取其中的全部文字。直接输出结果，不要有任何解释。",
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_base64}"},
            },
        ],
    }

    client = httpx.Client(timeout=120.0)
    response = client.post(
        f"{BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": MODEL, "messages": [message], "temperature": 0, "max_tokens": 8192},
    )
    client.close()

    if response.status_code == 200:
        result = response.json()
        extracted_text = result["choices"][0]["message"]["content"]
        tokens = result.get("usage", {}).get("total_tokens", 0)
        print(f"[Test] SUCCESS! Tokens used: {tokens}")
        print(f"[Test] Extracted text preview (500 chars):\n{extracted_text[:500]}")
        return extracted_text
    else:
        print(f"[Test] FAILED! Status: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    test_kimi_ocr_on_image()