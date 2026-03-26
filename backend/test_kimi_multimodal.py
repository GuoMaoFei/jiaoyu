import base64
import requests
import json

API_KEY = "f4457a91-7260-49df-b346-9cf771c6e58d"
IMAGE_PATH = r"C:\Users\茂飞\Downloads\ScreenShot_2026-03-21_202906_072.png"
MODEL = "kimi-k2.5"

BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def test_multimodal():
    image_base64 = encode_image_to_base64(IMAGE_PATH)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请仔细描述这张图片的内容，如果有文字请准确提取出来。"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 4096
    }

    print(f"Testing {MODEL} multimodal capability...")
    print(f"Image: {IMAGE_PATH}")
    print("-" * 50)

    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )

        print(f"Status Code: {response.status_code}")
        print("-" * 50)

        if response.status_code == 200:
            result = response.json()
            print("SUCCESS! Response:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("FAILED! Response:")
            print(response.text)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_multimodal()