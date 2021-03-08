# -*- coding: utf-8 -*-

from odoo.addons import decimal_precision as dp
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, RedirectWarning, UserError


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    def action_invoice_open(self):

        if self.type == "in_invoice":
            product_list = []
            for invoice_line in self.invoice_line_ids:
                product_found = False
                for product in product_list:
                    if product['id'] == invoice_line.product_id.id:
                        product_found = True

                if not product_found:
                    new_product = {
                        "id": invoice_line.product_id.id,
                        "price_total": invoice_line.price_total,
                        "qty": invoice_line.quantity,
                        "cost": 0.00
                    }
                    product_list.append(new_product)
                else:
                    product['price_total'] += invoice_line.price_total
                    product['qty'] += invoice_line.quantity

            for product in product_list:
                new_cost = product['price_total'] / product['qty']
                product_product_data = self.env['product.product'].search([
                    ("id", "=", product['id'])
                ], limit=1)
                if product_product_data:
                    product_product_data.product_tmpl_id.write({"standard_price": new_cost})

        res = super(AccountInvoice, self).action_invoice_open()
        return res
