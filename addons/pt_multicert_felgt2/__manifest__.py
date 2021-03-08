# -*- coding: utf-8 -*-
{
    'name': "Electronic Invoicing - SAT FEL",

    'summary': """
        Odoo module for Guatemalan Electronic Invoice System (SAT FEL).
        """,

    'description': """
        Odoo module for Guatemalan Electronic Invoice System (SAT FEL).
        The following SAT Certificate provider are supoorted by this version: \n
        - DIGIFACT \n
        - InFile \n
    """,

    'author': "Pitaya Tech",
    'website': "https://www.pitaya.tech",
    'maintainer': "Pitaya Tech Development Team",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/11.0/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Invoicing & Payments',
    'version': '12.0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'base_setup', 'account', 'account_cancel'],

    # always loaded
    'data': [
        'security/felgt_security.xml',
        'security/digifact_felgt_security.xml',
        'security/infile_felgt_security.xml',
        'security/ir.model.access.csv',
        'views/account_invoice_view.xml',
        'views/account_journal_view.xml',
        'views/res_company_view.xml',
        'views/res_partner.xml',
        'views/res_config_settings_views.xml',
        'views/account_tax_views.xml'
    ],
    # only loaded in demonstration mode
    'demo': [],
}
