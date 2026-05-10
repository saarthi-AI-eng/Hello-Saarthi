from src.preprocessing import pdf_to_images
from src.ocr import extract_text_tesseract
from src.assemble import enhance_text
from src.structure import structure_page
from src.embed import create_embeddings, build_index

import json

PDF_PATH = r"D:\VS Code\RAG_NOTES_PIPELINE\Data\input_pdfs\Z-Transform.pdf"

print("🚀 Starting PDF processing...")

images = pdf_to_images(PDF_PATH)

print("✅ Conversion done!")

all_pages = []

for i, img in enumerate(images[:2]):  # keep 2 pages
    print(f"\n🤖 Processing page {i+1}...")

    # 🔹 STEP 1: OCR (Tesseract)
    raw_text = extract_text_tesseract(img)

    # 🔹 STEP 2: LLM correction
    enhanced_text = enhance_text(raw_text, i+1)

    # 🔹 STEP 3: Structure
    structured = structure_page(enhanced_text, i+1)

    all_pages.append(structured)

# Save JSON
with open("Data/output_json/output.json", "w") as f:
    json.dump(all_pages, f, indent=4)

print("\n✅ JSON saved successfully!")

# Embeddings
embeddings = create_embeddings(all_pages)
index = build_index(embeddings)

print("✅ Embeddings + FAISS index ready!")