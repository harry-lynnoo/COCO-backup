# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .ocr_parser import OCRParser


class OCRDocument(models.Model):
    _name = "ocr.document"
    _description = "OCR Document"
    _order = "create_date desc"

    # BASIC FIELDS
    name = fields.Char(string="Document Name", required=True)
    file = fields.Binary(string="File", attachment=True, required=True)
    doc_type = fields.Selection(
        [
            ("invoice", "Invoice"),
            ("receipt", "Receipt"),
        ],
        string="Document Type",
        required=True,
        default="invoice",
    )
    upload_date = fields.Datetime(
        string="Uploaded On",
        default=lambda self: fields.Datetime.now(),
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Uploaded By",
        default=lambda self: self.env.user,
        readonly=True,
    )

    status = fields.Selection(
        [
            ("uploaded", "Uploaded"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("error", "Error"),
        ],
        string="Status",
        default="uploaded",
    )
    progress = fields.Integer(string="Progress (%)", default=0)

    vendor_name = fields.Char(string="Vendor / Shop Name")
    invoice_date = fields.Date(string="Invoice / Receipt Date")

    total_amount = fields.Float(string="Total Amount")
    vat_amount = fields.Float(string="VAT Amount")
    confidence_score = fields.Float(string="OCR Confidence Score")

    extracted_text = fields.Text(string="Raw OCR Text")
    extraction_log = fields.Text(string="Extraction Log")

    is_invoice = fields.Boolean(string="Is Invoice", compute="_compute_type_flags")
    is_receipt = fields.Boolean(string="Is Receipt", compute="_compute_type_flags")

    def _compute_type_flags(self):
        for rec in self:
            rec.is_invoice = rec.doc_type == "invoice"
            rec.is_receipt = rec.doc_type == "receipt"

    @api.model
    def create(self, vals):
        if not vals.get("name"):
            seq = self.env["ir.sequence"].next_by_code("ocr.document") or "OCR-0000"
            vals["name"] = seq
        return super().create(vals)

    def action_run_ocr(self):
        for doc in self:
            if not doc.file:
                raise UserError(_("Please upload a file before running OCR."))

            doc.write({"status": "processing", "progress": 10})

            text = OCRParser.run_tesseract(doc.file)

            if text.startswith("OCR ERROR:"):
                new_log = (doc.extraction_log or "") + "\n" + text
                doc.write({
                    "status": "error",
                    "progress": 100,
                    "extracted_text": text,
                    "extraction_log": new_log.strip(),
                })
                continue

            data = OCRParser.extract_fields(text)

            log_lines = [
                "=== OCR Extraction ===",
                f"Vendor: {data.get('vendor_name', '')}",
                f"Total: {data.get('total_amount', 0.0)}",
                f"VAT: {data.get('vat_amount', 0.0)}",
                f"Confidence: {data.get('confidence', 0.0)}",
            ]
            if data.get("invoice_date_raw"):
                log_lines.append(f"Raw date: {data['invoice_date_raw']}")

            vals = {
                "status": "completed",
                "progress": 100,
                "vendor_name": data.get("vendor_name") or False,
                "total_amount": data.get("total_amount") or 0.0,
                "vat_amount": data.get("vat_amount") or 0.0,
                "confidence_score": data.get("confidence") or 0.0,
                "extracted_text": text,
                "extraction_log": ((doc.extraction_log or "") + "\n" + "\n".join(log_lines)).strip(),
            }

            doc.write(vals)

        return True
