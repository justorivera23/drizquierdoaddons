# -*- coding: utf-8 -*-
{
    'name': "POS Conversion de productos",

    'summary': """
        Módulo para conversion de productos en punto de venta""",

    'description': """
        Módulo para conversión de productos en punto de venta. Este módulo se apoya en el módulo Product Conversion para realizar la conversión automática de productos desde el punto de venta de Odoo
    """,

    'author': "Pitaya Tech",
    'website': "https://www.pitaya.tech",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'product_conversion'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/assets.xml',
    ],
    # only loaded in demonstration mode
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'demo': [
        'demo/demo.xml',
    ],
}