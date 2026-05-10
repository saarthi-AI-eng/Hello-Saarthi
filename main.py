from src.preprocessing import pdf_to_images
from src.extract import extract_page
from src.assemble import enhance_text
from src.structure import structure_page

import json

PDF_PATH = r"D:\VS Code\RAG_NOTES_PIPELINE\Data\input_pdfs\Z-Transform.pdf"

print("🚀 Starting PDF processing...")

images = pdf_to_images(PDF_PATH)

print("✅ Conversion done!")

all_pages = []

for i, img in enumerate(images[:2]):  # keep 2 pages for testing
    print(f"\n🤖 Processing page {i+1}...")

    # 🔹 STEP 1: LLM Vision Extraction (REPLACED TESSERACT)
    raw_text = extract_page(img, i+1)

    # 🔹 STEP 2: Clean text
    enhanced_text = enhance_text(raw_text, i+1)

    # 🔹 STEP 3: Structure JSON
    structured = structure_page(enhanced_text, i+1)

    all_pages.append(structured)

# Save JSON
with open("Data/output_json/output.json", "w") as f:
    json.dump(all_pages, f, indent=4)

print("\n✅ JSON saved successfully!")

#