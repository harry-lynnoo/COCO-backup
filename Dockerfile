FROM odoo:17

USER root

RUN apt-get update && apt-get install -y \
    python3-pip \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-osd \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir pytesseract Pillow

USER odoo
