# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Product Conversion',
    'price': 110.0,
    'currency': 'USD',
    'version': '12.0.0.0.0',
    'summary': 'Product Conversion',
    'live_test_url': 'http://165.227.3.14:8071/',
    'author': 'FOSS INFOTECH PVT LTD',
    'license': 'Other proprietary',
    'category': 'Warehouse',
    'website': 'http://www.fossinfotech.com',
    'description': """ You can convert products with different unit of measures very easily with a button 
                    click by setting a ratio for conversion in the product master.""",
    'depends': ['base', 'stock', 'product' ],
    'data': [
        'security/product_conversion_security.xml',
        'security/ir.model.access.csv',
        'data/ir.sequence.xml',
        'views/product_conversion_views.xml',
    ],
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
        'static/description/index.html',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
