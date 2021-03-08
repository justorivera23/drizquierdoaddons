# -*- coding: utf-8 -*-

from odoo.addons import decimal_precision as dp
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, RedirectWarning, UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_profit_value = fields.Float(string='Utilidad', compute='_compute_product_profit', digits=(16, 2))
    product_profit_percentage = fields.Float(string='% de utilidad', compute='_compute_product_profit', digits=(16, 2))

    def _compute_product_profit(self):

        for rec in self:
            rec.product_profit_value = 0.00

            rec.product_profit_value = round(rec.list_price - rec.standard_price, 2)
            profit_percentage = rec.product_profit_value * 100
            rec.product_profit_percentage = 0
            if rec.standard_price > 0:
                rec.product_profit_percentage = round(profit_percentage / rec.standard_price, 2)
