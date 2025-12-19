# -*- coding: utf-8 -*-
import base64
import csv
import io

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .ocr_parser import OCRParser


class OCRDocument(models.Model):
    _name = "ocr.document"
    _description = "OCR Document"
    _order = "create_date desc"

    # =========================
    # BASIC
    # =========================
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
        [
            ("uploaded", "Uploaded"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("error", "Error"),
        ],
        default="uploaded",
    )
    progress = fields.Integer(default=0)

    # =========================
    # HEADER FIELDS
    # =========================
    customer_name = fields.Char()
    supplier_name = fields.Char()
    vendor_name = fields.Char()
    seller_id = fields.Char()
    company_issued = fields.Char()
    tax_id = fields.Char()
    vendor_address = fields.Char()
    vendor_phone = fields.Char()
    reference_number = fields.Char()

    # =========================
    # DATES / NUMBERS
    # =========================
    invoice_date = fields.Date()
    receipt_number = fields.Char()
    receipt_date = fields.Date()

    subtotal_amount = fields.Float()
    discount_amount = fields.Float(default=0.0)
    vat_percent = fields.Float(default=0.0)
    vat_amount = fields.Float()
    total_amount = fields.Float()

    # =========================
    # DEBUG
    # =========================
    confidence_score = fields.Float()
    extracted_text = fields.Text()
    extraction_log = fields.Text()

    # =========================
    # ITEMS
    # =========================
    line_ids = fields.One2many("ocr.document.line", "document_id")

    # =========================
    # STEP 3: LINK TO ACCOUNTING
    # =========================
    invoice_id = fields.Many2one(
        "account.move",
        string="Vendor Bill",
        readonly=True,
    )

    # =========================
    # OCR
    # =========================
    def action_run_ocr(self):
        for doc in self:
            if not doc.file:
                raise UserError(_("Please upload a file before running OCR."))

            doc.write({"status": "processing", "progress": 10})

            # =========================
            # STEP 1: Detect file type
            # =========================
            filename = (doc.file_filename or "").lower()

            if filename.endswith(".pdf"):
                text = OCRParser.run_pdf_ocr(doc.file)
            else:
                text = OCRParser.run_tesseract(doc.file)

            if text.startswith("OCR ERROR"):
                doc.write({"status": "error", "progress": 100})
                return

            data = OCRParser.extract_fields(text)

            # =========================
            # STEP 2: SAVE LINE ITEMS
            # =========================
            doc.line_ids.unlink()

            items = data.get("items") or []

            # ✅ If OCR extracted items → use them
            if items:
                for item in items:
                    self.env["ocr.document.line"].create({
                        "document_id": doc.id,
                        "item_name": item.get("name") or "Item",
                        "quantity": item.get("qty", 1.0),
                        "unit_price": item.get("price", 0.0),
                    })

            # ✅ Fallback: create one line from total (no manual clicking)
            elif data.get("total_amount"):
                self.env["ocr.document.line"].create({
                    "document_id": doc.id,
                    "item_name": "OCR Total",
                    "quantity": 1.0,
                    "unit_price": data.get("total_amount"),
                })

            # =========================
            # SAVE HEADER DATA
            # =========================
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
    # STEP 3: CREATE VENDOR BILL
    # =========================
    def action_create_vendor_bill(self):
        self.ensure_one()

        if self.invoice_id:
            raise UserError(_("A vendor bill has already been created."))

        if not self.vendor_name:
            raise UserError(_("Vendor name is required to create a vendor bill."))

        # Find or create vendor
        partner = self.env["res.partner"].search(
            [("name", "=", self.vendor_name)], limit=1
        )

        if not partner:
            partner = self.env["res.partner"].create({
                "name": self.vendor_name,
                "supplier_rank": 1,
            })

        # Create vendor bill
        bill = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": partner.id,
            "invoice_date": self.invoice_date or fields.Date.today(),
            "ref": self.reference_number or self.name,
        })

        # Create bill lines
        for line in self.line_ids:
            self.env["account.move.line"].create({
                "move_id": bill.id,
                "name": line.item_name,
                "quantity": line.quantity,
                "price_unit": line.unit_price,
            })

        self.invoice_id = bill.id

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": bill.id,
            "view_mode": "form",
        }

    # =========================
    # VIEW IMAGE
    # =========================
    def action_view_image(self):
        self.ensure_one()

        if not self.file:
            raise UserError(_("No image uploaded."))

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self._name}/{self.id}/file?download=0",
            "target": "self",
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

    # =========================
    # RE-RUN OCR
    # =========================
    def action_rerun_ocr(self):
        for doc in self:
            if not doc.file:
                raise UserError(_("No file found to re-run OCR."))

            doc.write({
                "status": "processing",
                "progress": 0,
                "confidence_score": False,
                "extracted_text": False,
                "extraction_log": False,
            })

        return self.action_run_ocr()


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