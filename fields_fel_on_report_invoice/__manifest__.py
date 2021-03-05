
{
    'name': 'Add fields FEL on PDF Report Invoice',
    'version': '12.0.1.0.0',
    'category': 'Account',
    'license': 'AGPL-3',
    'summary': 'Add fields FEL on Report Invoice',
    'description': """
ADD FIELDS FEL ON INVOICE PDF 
========================

Add fields FEL on Report Invoice FEL.

    """,
    'author': 'J2L',
    'website': 'http://www.j2l.com',
    'depends': ['account','base','pt_multicert_felgt'],
    'data': ['views/account.xml','views/report_invoice.xml'],
    'installable': True,
}
