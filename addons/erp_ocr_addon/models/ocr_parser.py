# -*- coding: utf-8 -*-
import base64
import io
import re

from PIL import Image
import pytesseract


class OCRParser:
    """
    Helper class to run Tesseract on a base64 image (Odoo binary field)
    and extract fields with regex heuristics.
    """

    @staticmethod
    def run_tesseract(base64_data):
        if not base64_data:
            return ""

        try:
            if isinstance(base64_data, str):
                image_data = base64.b64decode(base64_data)
            else:
                image_data = base64.b64decode(base64_data)

            image = Image.open(io.BytesIO(image_data))
            text = pytesseract.image_to_string(image)
            return text or ""

        except Exception as e:
            return f"OCR ERROR: {str(e)}"

    @staticmethod
    def extract_fields(text):
        """
        Regex-based extraction (basic).
        You will improve these patterns later.
        """
        fields = {
            "vendor_name": "",
            "supplier_name": "",
            "customer_name": "",
            "seller_id": "",
            "company_issued": "",
            "tax_id": "",
            "vendor_phone": "",
            "vendor_address": "",
            "reference_number": "",
            "invoice_date_raw": "",
            "receipt_number": "",
            "receipt_date_raw": "",
            "subtotal_amount": 0.0,
            "discount_amount": 0.0,
            "vat_percent": 0.0,
            "vat_amount": 0.0,
            "total_amount": 0.0,
            "confidence": 0.85,
            "items": [],  # later: list of dict lines
        }

        if not text:
            return fields

        # Vendor (heuristic: first long-ish line)
        vendor_match = re.search(r'^([A-Za-z][A-Za-z0-9 &\.\-]{4,})', text, re.MULTILINE)
        if vendor_match:
            fields["vendor_name"] = vendor_match.group(1).strip()

        # Simple date
        date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
        if date_match:
            fields["invoice_date_raw"] = date_match.group(1)

        # Total
        total_match = re.search(
            r'(Total\s*(Amount)?|Amount\s*Due)\s*[:\-]?\s*([0-9.,]+)',
            text,
            re.IGNORECASE,
        )
        if total_match:
            raw_total = total_match.group(3).replace(",", "")
            try:
                fields["total_amount"] = float(raw_total)
            except ValueError:
                fields["total_amount"] = 0.0

        # VAT value (amount)
        vat_match = re.search(
            r'(VAT|Tax)\s*[:\-]?\s*([0-9.,]+)',
            text,
            re.IGNORECASE,
        )
        if vat_match:
            raw_vat = vat_match.group(2).replace(",", "")
            try:
                fields["vat_amount"] = float(raw_vat)
            except ValueError:
                fields["vat_amount"] = 0.0

        # Discount (optional)
        disc_match = re.search(r'(Discount)\s*[:\-]?\s*([0-9.,]+)', text, re.IGNORECASE)
        if disc_match:
            raw_disc = disc_match.group(2).replace(",", "")
            try:
                fields["discount_amount"] = float(raw_disc)
            except ValueError:
                fields["discount_amount"] = 0.0

        return fields
