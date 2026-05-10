import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"D:\Tesseract\tesseract.exe"

def extract_text_tesseract(img):
    return pytesseract.image_to_string(img)