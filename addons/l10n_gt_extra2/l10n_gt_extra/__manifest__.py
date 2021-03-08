# -*- encoding: utf-8 -*-

{
    'name': 'Guatemala - Reportes Requeridos por S.A.T.',
    'version': '1.2',
    'category': 'Localization',
    'description': """ Reportes Requeridos por la S.A.T. : Libros de: Banco, Ventas, Compras, Inventario, Diario, Mayor, Banco Conciliado v12""",
    'author': 'Pitaya Tech',
    'website': 'https://www.pitaya.tech/',
    'depends': ['l10n_gt', 'account_tax_python', 'account_cancel', 'product', 'purchase'],
    'data': [
        'views/res_company_view.xml',
        'views/res_partner_view.xml',
        'security/ir.model.access.csv',
        'data/l10n_gt_extra_base.xml',
        'views/report.xml',
        'views/reporte_banco.xml',
        'views/reporte_partida.xml',
        'views/reporte_compras.xml',
        'views/reporte_ventas.xml',
        'views/reporte_inventario.xml',
        'views/reporte_diario.xml',
        'views/reporte_mayor.xml',
        'views/l10n_gt_extra_view.xml',
        'views/product_views.xml',
        'views/purchase_views.xml',
        'views/account_invoice_view.xml',
        'views/account_view.xml',
        'views/product_category_view.xml',
        'views/res_config_settings_views.xml',
        'views/account_journal_view.xml',
        'views/account_tax_views.xml'
    ],
    'demo': [],
    'installable': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
