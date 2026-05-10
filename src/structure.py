import re


def clean_text(text):
    text = text.replace("```", "").strip()

    if text.lower().startswith("plaintext"):
        text = text[len("plaintext"):].strip()

    return text

def extract_title(text):
    lines = text.split("\n")

    for line in lines:
        line = line.strip()

        if not line or len(line) < 5:
            continue

        if line.startswith(("*", "-", "->")):
            continue

        return line

    return "General Notes"


def extract_topics(text):
    topics = set()

    keywords = [
        "Z-Transform",
        "Fourier Transform",
        "DTFT",
        "CTFT",
        "Laplace Transform",
        "Z-plane",
    ]

    for k in keywords:
        if k.lower() in text.lower():
            topics.add(k)

    return list(topics)


def structure_page(text: str, page_no: int):
    text = clean_text(text)

    return {
        "id": str(page_no),
        "text": text,
        "metadata": {
            "page_no": str(page_no),
            "section": extract_title(text),
            "topics": extract_topics(text),
            "confidence": "medium",
        },
    }