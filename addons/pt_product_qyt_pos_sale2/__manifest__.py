# -*- coding: utf-8 -*-
{
    'name': "Cantidades disponibles - Reporte POS Ventas",

    'summary': """
        Agrega la columna de ventas en el reporte de ventas""",

    'description': """
        Agrega la columna de ventas en el reporte de ventas
    """,

    'author': "Pitaya Tech",
    'website': "https://www.pitaya.tech",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'point_of_sale', 'pos_salesperson'],

    # always loaded
    'data': [
        # 'views/report_sale_details.xml',
    ],
}