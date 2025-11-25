# -*- coding: utf-8 -*-
import base64
import io
import re

from PIL import Image
import pytesseract


class OCRParser:
    """
    Small helper class to run Tesseract on a base64 image (Odoo binary field)
    and extract a few useful fields with regex.
    """

    @staticmethod
    def run_tesseract(base64_data):
        """
        Convert base64 → image → OCR text using Tesseract.
        :param base64_data: base64-encoded bytes/str from ocr.document.file
        :return: text (str)
        """
        if not base64_data:
            return ""

        try:
            # Odoo binary fields can be bytes or str; normalize to bytes
            if isinstance(base64_data, str):
                image_data = base64.b64decode(base64_data)
            else:
                image_data = base64.b64decode(base64_data)

            image = Image.open(io.BytesIO(image_data))

            # You can tweak lang / config later if needed
            text = pytesseract.image_to_string(image)
            return text or ""

        except Exception as e:
            # We return the error text; caller will mark status = "error"
            return f"OCR ERROR: {str(e)}"

    @staticmethod
    def extract_fields(text):
        """
        Simple regex-based extraction for demo.
        You can improve these patterns later.
        """
        fields = {}
        if not text:
            fields["vendor_name"] = ""
            fields["total_amount"] = 0.0
            fields["vat_amount"] = 0.0
            fields["confidence"] = 0.0
            return fields

        # --- Vendor name ---
        # Rough heuristic: first long-ish line of letters/numbers
        vendor_match = re.search(r'^([A-Za-z][A-Za-z0-9 &\.\-]{4,})', text, re.MULTILINE)
        fields["vendor_name"] = vendor_match.group(1).strip() if vendor_match else ""

        # --- Total amount ---
        total_match = re.search(
            r'(Total\s*(Amount)?|Amount\s*Due)\s*[:\-]?\s*([0-9.,]+)',
            text,
            re.IGNORECASE,
        )
        if total_match:
            raw_total = total_match.group(3).replace(',', '')
            try:
                fields["total_amount"] = float(raw_total)
            except ValueError:
                fields["total_amount"] = 0.0
        else:
            fields["total_amount"] = 0.0

        # --- VAT / Tax ---
        vat_match = re.search(
            r'(VAT|Tax)\s*[:\-]?\s*([0-9.,]+)',
            text,
            re.IGNORECASE,
        )
        if vat_match:
            raw_vat = vat_match.group(2).replace(',', '')
            try:
                fields["vat_amount"] = float(raw_vat)
            except ValueError:
                fields["vat_amount"] = 0.0
        else:
            fields["vat_amount"] = 0.0

        # (Optional) date extraction – we keep it as text for now
        date_match = re.search(
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            text,
        )
        fields["invoice_date_raw"] = date_match.group(1) if date_match else ""

        # Dummy confidence – later you can compute something real
        fields["confidence"] = 0.85

        return fields
