# -*- coding: utf-8 -*-
{
    "name": "POS Salesperson",
    "summary": "Allow POS cashier to work with multiple Salesperson",
    "description": """Allow POS cashier to work with multiple Salesperson""",

    'author': 'iPredict IT Solutions Pvt. Ltd.',
    'website': 'http://ipredictitsolutions.com',
    "support": "ipredictitsolutions@gmail.com",

    "category": "Point of Sale",
    "version": "12.0.0.1.0",
    "depends": ["point_of_sale"],

    "data": [
        "security/ir.model.access.csv",
        "views/assets.xml",
        "views/pos_salesperson_view.xml",
        "views/pos_config_view.xml",
        "views/pos_order_view.xml",
        "views/pos_order_report_view.xml",
        "wizard/generate_pos_sale_report_view.xml",
        "report/pos_sale_report_view.xml",
    ],
    'qweb': [
        "static/src/xml/pos_salesperson.xml",
    ],

    'license': "OPL-1",
    'price': 35,
    'currency': "EUR",

    'auto_install': False,
    'installable': True,

    'images': ['static/description/banner.png'],
}
