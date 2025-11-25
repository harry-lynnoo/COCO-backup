# -*- coding: utf-8 -*-
{
    "name": "Clareo OCR Finance",
    "summary": "Invoice & Receipt OCR Processing for Accounting Automation",
    "version": "1.0",
    "category": "Accounting",
    "author": "Your Team",
    "website": "https://yourwebsite.com",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "installable": True,
    "application": True,

    "data": [
        # 1) Security
        "security/ir.model.access.csv",

        # 2) Sequences
        "data/ocr_sequences.xml",

        # 3) Actions and views
        "views/ocr_actions.xml",
        "views/ocr_home_view.xml",

        # Main document views (tree + search + form)
        "views/ocr_document_tree.xml",
        "views/ocr_document_search.xml",
        "views/ocr_document_form.xml",

        # Dashboard
        "views/ocr_dashboard_views.xml",

        # (Optional) Wizard XML if you still use it and it's valid
        # "wizard/ocr_preview_wizard.xml",

        # Menus (last)
        "views/menus.xml",
    ],
}
