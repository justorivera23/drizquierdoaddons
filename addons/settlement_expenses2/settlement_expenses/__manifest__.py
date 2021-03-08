# -*- coding: utf-8 -*-

{
    'name' : "settlement_expenses",
    'version' : '1.0',
    'category': 'Custom',
    'description': """Manejo de cajas chicas y liquidaciones""",
    'author': 'Pitaya Tech',
    'website': 'https://www.pitaya.tech',
    'depends' : [ 'account',
                   'hr' ],
    'data' : [
        'views/templates.xml',
        'views/views.xml',
        'views/invoice.xml',
        'views/payment.xml',
        'views/settlement_expenses_view.xml',
        'security/ir.model.access.csv',
        'security/settlement_expenses_security.xml',
        
        
    ],
    'installable': True,
    'certificate': '',
}