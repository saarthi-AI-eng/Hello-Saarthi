from openai import OpenAI
from config.settings import OPENROUTER_API_KEY

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

ASSEMBLE_PROMPT = """
You are cleaning OCR-extracted engineering notes.

STRICT RULES:
- DO NOT change equations
- DO NOT change variables
- DO NOT add new content

ONLY:
- Fix grammar
- Fix formatting
- Improve readability

Keep math EXACTLY as is.

Return clean structured notes.
"""


def enhance_text(text: str, page_no: int) -> str:
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": ASSEMBLE_PROMPT + "\n\n" + text
                }
            ],
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"❌ Assemble error on page {page_no}: {e}")
        return text