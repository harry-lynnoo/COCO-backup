# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..models.ocr_parser import OCRParser


class OCRPreviewWizard(models.TransientModel):
    _name = "ocr.preview.wizard"
    _description = "OCR Preview Wizard"

    # Link back to main document
    document_id = fields.Many2one(
        "ocr.document",
        string="Document",
        required=True,
        readonly=True,
    )

    # Basic info (read-only)
    name = fields.Char(
        string="Document Name",
        related="document_id.name",
        readonly=True,
    )
    doc_type = fields.Selection(
        related="document_id.doc_type",
        string="Document Type",
        readonly=True,
    )

    # Extracted fields (user can edit / confirm)
    vendor_name = fields.Char(string="Vendor / Shop Name")
    invoice_date = fields.Date(string="Invoice / Receipt Date")

    total_amount = fields.Float(string="Total Amount")
    vat_amount = fields.Float(string="VAT Amount")
    confidence_score = fields.Float(string="OCR Confidence Score")

    extracted_text = fields.Text(string="Raw OCR Text")
    extraction_log = fields.Text(string="Extraction Log")

    has_run_ocr = fields.Boolean(string="Has Run OCR", default=False)

    @api.model
    def default_get(self, fields_list):
        """
        Prefill wizard with existing values from ocr.document
        in case user opens the wizard again.
        """
        res = super().default_get(fields_list)
        document_id = self.env.context.get("default_document_id")
        if document_id:
            doc = self.env["ocr.document"].browse(document_id)
            if doc:
                res.setdefault("vendor_name", doc.vendor_name)
                res.setdefault("invoice_date", doc.invoice_date)
                res.setdefault("total_amount", doc.total_amount)
                res.setdefault("vat_amount", doc.vat_amount)
                res.setdefault("confidence_score", doc.confidence_score)
                res.setdefault("extracted_text", doc.extracted_text)
                res.setdefault("extraction_log", doc.extraction_log)
        return res

    # ---------------------------------------------------------
    # BUTTON: Run OCR inside wizard
    # ---------------------------------------------------------
    def action_run_ocr(self):
        """
        Real OCR implementation:
        - checks file exists
        - runs Tesseract using OCRParser
        - parses vendor / date / amounts
        """
        for wiz in self:
            doc = wiz.document_id
            if not doc.file:
                raise UserError(_("Please upload a file on the main form first and save."))

            wiz.extraction_log = (wiz.extraction_log or "") + "Starting OCR...\n"

            # 1) run pytesseract on the file
            text = OCRParser.run_tesseract(doc.file)

            if text.startswith("OCR ERROR"):
                wiz.extracted_text = text
                wiz.extraction_log += text + "\n"
                wiz.status = "error"
                wiz.has_run_ocr = True
                continue

            wiz.extracted_text = text

            # 2) extract key fields
            fields_dict = OCRParser.extract_fields(text)

            # Only overwrite if not already filled (user might re-run OCR)
            if not wiz.vendor_name:
                wiz.vendor_name = fields_dict.get("vendor_name", "")
            if not wiz.invoice_date and fields_dict.get("invoice_date"):
                wiz.invoice_date = fields.Date.from_string(fields_dict["invoice_date"])
            if not wiz.total_amount:
                wiz.total_amount = fields_dict.get("total_amount", 0.0)
            if not wiz.vat_amount:
                wiz.vat_amount = fields_dict.get("vat_amount", 0.0)
            if not wiz.confidence_score:
                wiz.confidence_score = fields_dict.get("confidence_score", 0.0)

            wiz.extraction_log += "OCR completed successfully.\n"
            wiz.has_run_ocr = True

        return True

    # ---------------------------------------------------------
    # BUTTON: Confirm & write back to ocr.document
    # ---------------------------------------------------------
    def action_confirm(self):
        """
        Write confirmed values back to the main ocr.document record
        and mark it as completed.
        """
        for wiz in self:
            doc = wiz.document_id

            vals = {
                "vendor_name": wiz.vendor_name,
                "invoice_date": wiz.invoice_date,
                "total_amount": wiz.total_amount,
                "vat_amount": wiz.vat_amount,
                "confidence_score": wiz.confidence_score,
                "extracted_text": wiz.extracted_text,
                "extraction_log": wiz.extraction_log,
                "status": "completed",
                "progress": 100,
            }
            doc.write(vals)

        return {"type": "ir.actions.act_window_close"}
