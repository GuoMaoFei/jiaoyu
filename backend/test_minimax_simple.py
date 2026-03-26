import os

def test_minimax_vision_url():
    from anthropic import Anthropic

    client = Anthropic(
        api_key="sk-cp-oqT6nOabucgS2-PRLM8Cu3dp09x4F3oLfeVY7AIzSi3Q4FFS1Z16P7TnTadi6qzorRkOOtbkGlF_wt5GFiVsyPMKQX9Nj5rBInuoEH4onQ3HBmHvN3W1jo0",
        base_url="https://api.minimaxi.com/anthropic",
    )

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
                            "type": "url",
                            "url": "https://picsum.photos/200"
                        }
                    }
                ]
            }
        ]
    )

    print("Response:", response.content)

if __name__ == "__main__":
    test_minimax_vision_url()