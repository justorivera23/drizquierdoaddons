# -*- coding: utf-8 -*-

from odoo import api, models, fields, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    buyer_code = fields.Char(string="Código Comprador")
