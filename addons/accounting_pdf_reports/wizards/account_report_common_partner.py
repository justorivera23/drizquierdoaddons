# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountingCommonPartnerReport(models.TransientModel):
    _name = 'account.common.partner.report'
    _description = 'Account Common Partner Report'
    _inherit = "account.common.report"

    result_selection = fields.Selection([('customer', 'Cuentas a cobrar'),
                                         ('supplier', 'Cuentas a pagar'),
                                         ('customer_supplier', 'Cuentas a cobrar y pagar')
                                         ], string="Empresas", required=True, default='customer')

    @api.multi
    def pre_print_report(self, data):
        data['form'].update(self.read(['result_selection'])[0])
        return data
