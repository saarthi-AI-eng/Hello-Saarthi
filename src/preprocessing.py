import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import cv2


def preprocess_page(img: Image.Image) -> Image.Image:
    arr = np.array(img.convert("L"))

    # Denoise
    arr = cv2.fastNlMeansDenoising(arr, h=10)

    # Binarize
    _, arr = cv2.threshold(
        arr, 0, 255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    return Image.fromarray(arr)


def pdf_to_images(pdf_path: str):
    doc = fitz.open(pdf_path)

    images = []

    for page in doc:
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        img = preprocess_page(img)
        images.append(img)

    return images