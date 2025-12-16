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

        # 2) Sequences / initial data
        "data/ocr_sequences.xml",

        # 3) Main document views (tree + search + form) → MUST LOAD FIRST
        "views/ocr_document_tree.xml",
        "views/ocr_document_search.xml",
        "views/ocr_document_form.xml",

        # 4) Dashboard
        "views/ocr_dashboard_views.xml",

        # 5) Actions and special views → MUST LOAD AFTER TREE/SEARCH/FORM
        "views/ocr_actions.xml",
        "views/ocr_home_view.xml",

        # 6) Menus (last)
        "views/menus.xml",
    ],

    # 7) Static assets (JS for charts)
    "assets": {
        "web.assets_backend": [
            "erp_ocr_addon/static/lib/chart.min.js",
            "erp_ocr_addon/static/src/js/ocr_dashboard_charts.js",
        ],
    },
}