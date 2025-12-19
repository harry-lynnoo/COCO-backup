# -*- coding: utf-8 -*-
import base64
import io
import re

from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes


class OCRParser:
    """
    OCR helper for invoices & receipts.
    Supports image + PDF, Thai + English.
    """

    # =========================
    # IMAGE PREPROCESSING
    # =========================
    @staticmethod
    def _preprocess_image(image: Image.Image) -> Image.Image:
        """
        Improve OCR accuracy (especially Thai).
        """
        image = image.convert("L")  # grayscale
        image = image.point(lambda x: 0 if x < 180 else 255, "1")  # threshold
        return image

    # =========================
    # OCR CORE
    # =========================
    @staticmethod
    def _run_ocr_on_image(image: Image.Image) -> str:
        """
        Run Tesseract with Thai + English.
        """
        image = OCRParser._preprocess_image(image)
        config = "--oem 3 --psm 6 -l tha+eng"
        return pytesseract.image_to_string(image, config=config) or ""

    @staticmethod
    def run_tesseract(base64_data):
        """
        OCR for image uploads (PNG/JPG).
        """
        if not base64_data:
            return ""

        try:
            image_bytes = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(image_bytes))
            return OCRParser._run_ocr_on_image(image)

        except Exception as e:
            return f"OCR ERROR: {str(e)}"

    @staticmethod
    def run_pdf_ocr(base64_data):
        """
        OCR for PDF uploads (multi-page).
        """
        if not base64_data:
            return ""

        try:
            pdf_bytes = base64.b64decode(base64_data)
            images = convert_from_bytes(pdf_bytes, dpi=300)

            full_text = ""
            for idx, img in enumerate(images, start=1):
                full_text += f"\n--- PAGE {idx} ---\n"
                full_text += OCRParser._run_ocr_on_image(img)

            return full_text

        except Exception as e:
            return f"OCR ERROR: {str(e)}"

    # =========================
    # TEXT NORMALIZATION
    # =========================
    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\t", " ")
        text = re.sub(r"[ ]{2,}", " ", text)
        text = re.sub(r"\n{2,}", "\n", text)
        return text.strip()

    # =========================
    # FIELD EXTRACTION
    # =========================
    @staticmethod
    def extract_fields(text):
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
            "confidence": 0.70,
            "items": [],
        }

        if not text:
            return fields

        text = OCRParser._normalize_text(text)

        # -------------------------
        # VENDOR NAME (Thai + Eng)
        # -------------------------
        vendor_patterns = [
            r'^(บริษัท\s*[^\n]+)',                 # Thai company
            r'^([A-Z][A-Za-z0-9 &\.,\-]{4,})',     # English company
        ]
        for pat in vendor_patterns:
            m = re.search(pat, text, re.MULTILINE)
            if m:
                fields["vendor_name"] = m.group(1).strip()
                fields["confidence"] += 0.1
                break

        # -------------------------
        # DATE
        # -------------------------
        date_match = re.search(
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            text
        )
        if date_match:
            fields["invoice_date_raw"] = date_match.group(1)

        # -------------------------
        # TOTAL (Thai + English)
        # -------------------------
        total_patterns = [
            r'รวมทั้งสิ้น\s*([0-9,]+\.\d{2})',
            r'ยอดรวม\s*([0-9,]+\.\d{2})',
            r'\bTOTAL\b[^\d]*([0-9,]+\.\d{2})',
            r'Amount\s*Due[^\d]*([0-9,]+\.\d{2})',
        ]
        for pat in total_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                fields["total_amount"] = float(m.group(1).replace(",", ""))
                fields["confidence"] += 0.15
                break

        # -------------------------
        # VAT
        # -------------------------
        vat_patterns = [
            r'ภาษีมูลค่าเพิ่ม\s*([0-9,]+\.\d{2})',
            r'(VAT|Tax)[^\d]*([0-9,]+\.\d{2})',
        ]
        for pat in vat_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                value = m.group(1) if m.lastindex == 1 else m.group(2)
                fields["vat_amount"] = float(value.replace(",", ""))
                fields["confidence"] += 0.05
                break

        # -------------------------
        # DISCOUNT
        # -------------------------
        disc_match = re.search(
            r'(Discount|ส่วนลด)[^\d]*([0-9,]+\.\d{2})',
            text,
            re.IGNORECASE
        )
        if disc_match:
            fields["discount_amount"] = float(disc_match.group(2).replace(",", ""))

        # -------------------------
        # ITEM LINES (basic)
        # -------------------------
        item_matches = re.findall(
            r'(\d+)\s+(.+?)\s+([0-9]+\.\d{2})',
            text
        )

        for qty, desc, unit in item_matches:
            fields["items"].append({
                "name": desc.strip(),
                "qty": float(qty),
                "price": float(unit),
            })

        if fields["items"]:
            fields["confidence"] += 0.1

        fields["confidence"] = min(fields["confidence"], 0.95)
        return fields