# -*- coding: utf-8 -*-
import base64
import csv
import io
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .ocr_parser import OCRParser


class OCRDocument(models.Model):
    _name = "ocr.document"
    _description = "OCR Document"
    _order = "create_date desc"

    # BASIC
    name = fields.Char(string="Document Name", required=True)
    file = fields.Binary(string="File", attachment=True, required=True)
    file_filename = fields.Char(string="Filename")

    doc_type = fields.Selection(
        [("invoice", "Invoice"), ("receipt", "Receipt")],
        string="Document Type",
        required=True,
        default="invoice",
    )

    upload_date = fields.Datetime(default=lambda self: fields.Datetime.now(), readonly=True)
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)

    status = fields.Selection(
        [("uploaded", "Uploaded"), ("processing", "Processing"), ("completed", "Completed"), ("error", "Error")],
        default="uploaded",
    )
    progress = fields.Integer(default=0)

    # HEADER FIELDS
    customer_name = fields.Char()
    supplier_name = fields.Char()
    vendor_name = fields.Char()
    seller_id = fields.Char()
    company_issued = fields.Char()
    tax_id = fields.Char()
    vendor_address = fields.Char()
    vendor_phone = fields.Char()
    reference_number = fields.Char()

    # DATES / NUMBERS
    invoice_date = fields.Date()
    receipt_number = fields.Char()
    receipt_date = fields.Date()

    subtotal_amount = fields.Float()
    discount_amount = fields.Float(default=0.0)
    vat_percent = fields.Float(default=0.0)
    vat_amount = fields.Float()
    total_amount = fields.Float()

    # DEBUG
    confidence_score = fields.Float()
    extracted_text = fields.Text()
    extraction_log = fields.Text()

    # ITEMS
    line_ids = fields.One2many("ocr.document.line", "document_id")

    # =========================
    # OCR
    # =========================
    def action_run_ocr(self):
        for doc in self:
            if not doc.file:
                raise UserError(_("Please upload a file before running OCR."))

            doc.write({"status": "processing", "progress": 10})
            text = OCRParser.run_tesseract(doc.file)

            if text.startswith("OCR ERROR"):
                doc.write({"status": "error", "progress": 100})
                return

            data = OCRParser.extract_fields(text)

            doc.write({
                "status": "completed",
                "progress": 100,
                "vendor_name": data.get("vendor_name"),
                "total_amount": data.get("total_amount"),
                "vat_amount": data.get("vat_amount"),
                "discount_amount": data.get("discount_amount"),
                "confidence_score": data.get("confidence"),
                "extracted_text": text,
            })

    # =========================
    # ✅ VIEW IMAGE (THIS IS WHAT YOU WANT)
    # =========================
    def action_view_image(self):
        self.ensure_one()

        if not self.file:
            raise UserError(_("No image uploaded."))

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self._name}/{self.id}/file?download=0",
            "target": "self",   # 🔑 THIS IS THE FIX
        }

    # =========================
    # EXPORT CSV
    # =========================
    def action_export_csv(self):
        self.ensure_one()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Name", "Vendor", "Total", "VAT", "Score"])
        writer.writerow([
            self.name,
            self.vendor_name,
            self.total_amount,
            self.vat_amount,
            self.confidence_score,
        ])

        csv_bytes = output.getvalue().encode("utf-8")
        output.close()

        attachment = self.env["ir.attachment"].create({
            "name": f"{self.name}.csv",
            "datas": base64.b64encode(csv_bytes),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "text/csv",
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=1",
            "target": "self",
        }


class OCRDocumentLine(models.Model):
    _name = "ocr.document.line"

    document_id = fields.Many2one("ocr.document", ondelete="cascade")
    item_number = fields.Char()
    item_name = fields.Char()
    description = fields.Char()
    quantity = fields.Float(default=1.0)
    unit_price = fields.Float(default=0.0)
    line_total = fields.Float(compute="_compute_total", store=True)

    @api.depends("quantity", "unit_price")
    def _compute_total(self):
        for r in self:
            r.line_total = (r.quantity or 0.0) * (r.unit_price or 0.0)
