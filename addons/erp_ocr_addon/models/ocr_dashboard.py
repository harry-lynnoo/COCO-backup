# -*- coding: utf-8 -*-
from odoo import models, fields, api

class OCRDashboard(models.Model):
    _name = "ocr.dashboard"
    _description = "OCR Dashboard (Analytics)"

    name = fields.Char(default="Clareo Dashboard")

    invoice_count = fields.Integer(compute="_compute_stats")
    receipt_count = fields.Integer(compute="_compute_stats")
    completed_count = fields.Integer(compute="_compute_stats")
    error_count = fields.Integer(compute="_compute_stats")
    avg_confidence = fields.Float(compute="_compute_stats")
    total_amount = fields.Float(compute="_compute_stats")

    @api.depends()
    def _compute_stats(self):
        Document = self.env["ocr.document"]

        for rec in self:
            invoices = Document.search([("doc_type", "=", "invoice")])
            receipts = Document.search([("doc_type", "=", "receipt")])
            completed = Document.search([("status", "=", "completed")])
            errors = Document.search([("status", "=", "error")])

            rec.invoice_count = len(invoices)
            rec.receipt_count = len(receipts)
            rec.completed_count = len(completed)
            rec.error_count = len(errors)

            all_conf = invoices.mapped("confidence_score") + receipts.mapped("confidence_score")
            rec.avg_confidence = (sum(all_conf) / len(all_conf)) if all_conf else 0.0

            rec.total_amount = sum(invoices.mapped("total_amount"))
