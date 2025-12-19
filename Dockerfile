FROM odoo:17

USER root

# System dependencies (OCR + PDF support)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-tha \
    tesseract-ocr-osd \
    poppler-utils \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Python OCR libraries
RUN pip3 install --no-cache-dir \
    pytesseract \
    pillow \
    pdf2image

USER odoo