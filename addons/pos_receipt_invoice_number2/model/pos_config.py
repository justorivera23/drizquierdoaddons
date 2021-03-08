# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class pos_config(models.Model):
    _inherit = "pos.config"

    pos_auto_invoice = fields.Boolean('POS auto factura', help='POS auto to checked to invoice button',
                                      default=1)
    receipt_invoice_number = fields.Boolean('Mostrar datos FEL', default=1)
    receipt_customer_vat = fields.Boolean('Mostrar NIT de cliente', default=1)