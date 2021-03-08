# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountCommonAccountReport(models.TransientModel):
    _name = 'account.common.account.report'
    _description = 'Account Common Account Report'
    _inherit = "account.common.report"

    display_account = fields.Selection([('all', 'Todas'), ('movement', 'Con movimientos'),
                                        ('not_zero', 'Con balance diferente a cero'), ],
                                       string='Cuentas a mostrar', required=True, default='movement')

    @api.multi
    def pre_print_report(self, data):
        data['form'].update(self.read(['display_account'])[0])
        return data
