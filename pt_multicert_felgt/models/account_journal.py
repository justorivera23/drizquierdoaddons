# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    fel_certifier = fields.Selection([
         ('digifact', 'Digifact'),
         ('infile', 'InFile')
    ], string='Certificador a utilizar', compute="get_fel_certifier", store=False)
    is_fel = fields.Selection([
        ('inactive', 'Inactivo'),
        ('development', 'Ambiente de pruebas'),
        ('production', 'Ambiente de producción'),
    ], string='Factura  Electrónica', default='inactive', required=False, help="Indique si este diario utilizara emisión de facturas electrónica y sobre que ambiente")
    infile_fel_active = fields.Boolean(string="Facturación electrónica")

    def get_fel_certifier(self):
        fel_certifier = self.env.user.company_id.fel_certifier
        if fel_certifier == 'digifact':
            self.infile_fel_active = False
        self.fel_certifier = fel_certifier
