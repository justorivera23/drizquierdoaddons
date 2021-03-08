# -*- coding: utf-8 -*-
{
    'name': "Impresion de cheques",

    'summary': """
        Set de formatos para impresión de cheques
    """,

    'description': """
        Set de formatos para impresión de cheques
    """,

    'author': "Pitaya Tech",
    'website': "https://www.pitaya.tech",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/11.0/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [        
        'data/paycheck_print_data.xml',
        'views/report.xml',
        'views/report_paycheck_bank_1.xml',
        'views/report_check_voucher_bi.xml'
    ],
    # only loaded in demonstration mode
    'demo': [],
}