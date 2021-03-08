# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountPartnerLedger(models.TransientModel):
    _inherit = "account.common.partner.report"
    _name = "account.report.partner.ledger"
    _description = "Account Partner Ledger"

    amount_currency = fields.Boolean("Con Moneda",
                                     help="Agrega la columna de moneda en el reporte si la "
                                          "moneda difiere de la moneda de la compañía.")
    reconciled = fields.Boolean('Entradas conciliadas')

    def _print_report(self, data):
        data = self.pre_print_report(data)
        data['form'].update({'reconciled': self.reconciled, 'amount_currency': self.amount_currency})
        return self.env.ref('accounting_pdf_reports.action_report_partnerledger').report_action(self, data=data)
