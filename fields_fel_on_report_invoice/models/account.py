# -*- coding: utf-8 -*-
from odoo import api, models, fields, _

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    get_name = fields.Char(string="get name", compute="locate_name", store=False)
    get_name_serie = fields.Char(string="get serie", compute="locate_serie", store=False)

    @api.depends("dte_number", "name")
    def locate_name(self):
            for invoice in self:
                if invoice.dte_number:
                    invoice.update({'get_name': invoice.dte_number})
                else:
                    invoice.update({'get_name': invoice.display_name})

    @api.depends("serie")
    def locate_serie(self):
        for invoice in self:
            if invoice.serie:
                invoice.update({'get_name_serie':invoice.serie})
            else:
                invoice.update({'get_name_serie':''})

