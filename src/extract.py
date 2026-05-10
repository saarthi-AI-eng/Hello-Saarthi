from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image
from config.settings import OPENROUTER_API_KEY

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

EXTRACTION_PROMPT = """
You are an expert at reading handwritten engineering notes.

STRICT RULES:
- Extract EXACT content (no guessing)
- Preserve mathematical expressions EXACTLY
- Use LaTeX for equations
- Maintain structure (headings, bullets)
- If unclear → write [ILLEGIBLE]
- If diagram → describe as [DIAGRAM: ...]

DO NOT:
- Add explanations
- Change equations
- Fix meaning

Return clean structured text only.
"""


def image_to_base64(img: Image.Image):
    # 🔥 Resize to reduce cost + improve speed
    img = img.resize((1024, 1024))

    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()


def extract_page(img: Image.Image, page_no: int) -> str:
    try:
        img_base64 = image_to_base64(img)

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": f"data:image/png;base64,{img_base64}"
                        }
                    ]
                }
            ],
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"❌ Error on page {page_no}: {e}")
        return ""