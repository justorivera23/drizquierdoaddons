# -*- coding: utf-8 -*-
{
    'name': "Product-Sale Extra Fields",

    'summary': """
        Adds extra fields to the products for sale purposes
        """,

    'description': """
        Adds extra fields to the products for sale purposes
    """,

    'author': "Pitaya Tech",
    'website': "https://www.pitaya.tech",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Invoicing & Payments',
    'version': '12.0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'base_setup', 'account', 'product', 'purchase'],

    # always loaded
    'data': [
        'views/product_views.xml',
        'views/purchase_order_views.xml'
    ],
    # only loaded in demonstration mode
    'demo': [],
}
