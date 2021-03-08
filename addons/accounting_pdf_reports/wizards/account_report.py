# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountingReport(models.TransientModel):
    _name = "accounting.report"
    _inherit = "account.common.report"
    _description = "Accounting Report"

    @api.model
    def _get_account_report(self):
        reports = []
        if self._context.get('active_id'):
            menu = self.env['ir.ui.menu'].browse(self._context.get('active_id')).name
            reports = self.env['account.financial.report'].search([('name', 'ilike', menu)])
        return reports and reports[0] or False

    enable_filter = fields.Boolean(string='Habilitar comparación')
    account_report_id = fields.Many2one('account.financial.report', string='Reṕortes de cuenta', required=True, default=_get_account_report)
    label_filter = fields.Char(string='Etiqueta de columna', help="Esta etiqueta se mostrará en el reporte para indicar el balance computado para la comparación seleccionada en los filtros.")
    filter_cmp = fields.Selection([('filter_no', 'Sin Filtros'), ('filter_date', 'Fecha')], string='Filtrar por', required=True, default='filter_no')
    date_from_cmp = fields.Date(string='Fecha de inicio')
    date_to_cmp = fields.Date(string='Fecha de finalización')
    debit_credit = fields.Boolean(string='Mostrar columnas de Debe/Haber', help="Esta opción le permite obtener más detalles acerca de la manera en como sus balances son computados. Debido a que ocupa mucho espacio, no se permite mientras se activa la comparación.")

    def _build_comparison_context(self, data):
        result = {}
        result['journal_ids'] = 'journal_ids' in data['form'] and data['form']['journal_ids'] or False
        result['state'] = 'target_move' in data['form'] and data['form']['target_move'] or ''
        if data['form']['filter_cmp'] == 'filter_date':
            result['date_from'] = data['form']['date_from_cmp']
            result['date_to'] = data['form']['date_to_cmp']
            result['strict_range'] = True
        return result

    @api.multi
    def check_report(self):
        res = super(AccountingReport, self).check_report()
        data = {}
        data['form'] = self.read(['account_report_id', 'date_from_cmp', 'date_to_cmp', 'journal_ids', 'filter_cmp', 'target_move'])[0]
        for field in ['account_report_id']:
            if isinstance(data['form'][field], tuple):
                data['form'][field] = data['form'][field][0]
        comparison_context = self._build_comparison_context(data)
        res['data']['form']['comparison_context'] = comparison_context
        return res

    def _print_report(self, data):
        data['form'].update(self.read(['date_from_cmp', 'debit_credit', 'date_to_cmp', 'filter_cmp', 'account_report_id', 'enable_filter', 'label_filter', 'target_move'])[0])
        return self.env.ref('accounting_pdf_reports.action_report_financial').report_action(self, data=data, config=False)
