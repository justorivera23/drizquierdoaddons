# -*- coding: utf-8 -*-

from odoo.addons import decimal_precision as dp
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, RedirectWarning, UserError


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    product_profit_value = fields.Float(string='Utilidad', compute='_compute_product_profit', digits=(16, 2))
    product_profit_percentage = fields.Float(string='% de utilidad', compute='_compute_product_profit', digits=(16, 2))

    @api.onchange('price_unit')
    def onchange_price_unit(self):
        self._compute_product_profit()

    def _compute_product_profit(self):

        for rec in self:
            rec.product_profit_value = 0.00

            rec.product_profit_value = round(rec.product_id.list_price - rec.price_unit, 2)
            profit_percentage = rec.product_profit_value * 100
            rec.product_profit_percentage = 0
            if rec.price_unit > 0:
                rec.product_profit_percentage = round(profit_percentage / rec.price_unit, 2)
