# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class AccountFinancialReport(models.Model):
    _name = "account.financial.report"
    _description = "Account Report"

    @api.multi
    @api.depends('parent_id', 'parent_id.level')
    def _get_level(self):
        '''Returns a dictionary with key=the ID of a record and value = the level of this
           record in the tree structure.'''
        for report in self:
            level = 0
            if report.parent_id:
                level = report.parent_id.level + 1
            report.level = level

    def _get_children_by_order(self):
        '''returns a recordset of all the children computed recursively, and sorted by sequence. Ready for the printing'''
        res = self
        children = self.search([('parent_id', 'in', self.ids)], order='sequence ASC')
        if children:
            for child in children:
                res += child._get_children_by_order()
        return res

    name = fields.Char('Nombre de reporte', required=True, translate=True)
    parent_id = fields.Many2one('account.financial.report', 'Padre')
    children_ids = fields.One2many('account.financial.report', 'parent_id', 'Reporte de cuenta')
    sequence = fields.Integer('Secuencia')
    level = fields.Integer(compute='_get_level', string='Nivel', store=True)
    type = fields.Selection([
        ('sum', 'Vista'),
        ('accounts', 'Cuentas'),
        ('account_type', 'Tipo de cuenta'),
        ('account_report', 'Valor de reporte'),
        ], 'Type', default='sum')
    account_ids = fields.Many2many('account.account', 'account_account_financial_report', 'report_line_id', 'account_id', 'Cuentas')
    account_report_id = fields.Many2one('account.financial.report', 'Valor de repote')
    account_type_ids = fields.Many2many('account.account.type', 'account_account_financial_report_type', 'report_id', 'account_type_id', 'Tipos de cuentas')
    sign = fields.Selection([(-1, 'Revertir signo de balance'), (1, 'Preservar signo de balance')], 'Firmar en reportes', required=True, default=1,
                            help='For accounts that are typically more debited than credited and that you would like to print as negative amounts in your reports, you should reverse the sign of the balance; e.g.: Expense account. The same applies for accounts that are typically more credited than debited and that you would like to print as positive amounts in your reports; e.g.: Income account.')
    display_detail = fields.Selection([
        ('no_detail', 'Sin detalle'),
        ('detail_flat', 'Mostrar hijos si jerarquía'),
        ('detail_with_hierarchy', 'Mostrar hijos con jerarquía')
        ], 'Mostrar detalles', default='detail_flat')
    style_overwrite = fields.Selection([
        (0, 'Automatic formatting'),
        (1, 'Main Title 1 (bold, underlined)'),
        (2, 'Title 2 (bold)'),
        (3, 'Title 3 (bold, smaller)'),
        (4, 'Normal Text'),
        (5, 'Italic Text (smaller)'),
        (6, 'Smallest Text'),
        ], 'Estilo de reportes financieros', default=0,
        help="You can set up here the format you want this record to be displayed. "
             "If you leave the automatic formatting, it will be computed based on the "
             "financial reports hierarchy (auto-computed field 'level').")
