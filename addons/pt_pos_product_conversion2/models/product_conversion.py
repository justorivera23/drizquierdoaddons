# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import time
from odoo.addons import decimal_precision as dp


class ProductConversion(models.Model):
    _inherit = "product.conversion"

    @api.model
    def pos_check_conversion(self, domain):
        product_id = domain.get('product_id')
        stock_location_id = domain.get('stock_location_id')

        product_conversion_main = self.env['product.line'].sudo().search([
            ('convertible_product', '=', product_id)
        ], limit=1)

        stock_location_data = self.env['stock.location'].sudo().search([
            ('id', '=', stock_location_id)
        ], limit=1)

        conversion_ratio = 0
        uom_name = ""
        product_name = ""
        main_product_id = 0
        main_current_qty = 0
        if product_conversion_main:
            main_current_qty = product_conversion_main.prod_id.with_context({'location': stock_location_id}).qty_available
            conversion_ratio = product_conversion_main.conversion_ratio
            main_product_id = product_conversion_main.prod_id.id
            if product_conversion_main.prod_id.product_tmpl_id.uom_id.name:
                uom_name = product_conversion_main.prod_id.product_tmpl_id.uom_id.name
            if product_conversion_main.prod_id.product_tmpl_id.name:
                product_name = product_conversion_main.prod_id.product_tmpl_id.name
            # if product_conversion_main.prod_id.product_tmpl_id.uom_po_id.name:
            #    uom_name = product_conversion_main.prod_id.product_tmpl_id.uom_po_id.name
            # elif product_conversion_main.prod_id.product_tmpl_id.uom_id.name:
            #    uom_name = product_conversion_main.prod_id.product_tmpl_id.uom_id.name

        data_response = {"conversion_ratio": conversion_ratio, "uom_name": uom_name, "product_name": product_name, "main_product_id": main_product_id, "main_current_qty": main_current_qty}
        print('Respuesta', data_response)
        return data_response

    @api.model
    def pos_process_conversion(self, domain):
        product_id = domain.get('product_id')
        stock_location_id = domain.get('stock_location_id')
        units_qty = domain.get('units_qty')

        product_conversion_main = self.env['product.line'].sudo().search([
            ('convertible_product', '=', product_id)
        ], limit=1)

        if product_conversion_main:
            product_data = self.env['product.product'].sudo().browse(product_id)
            converted_qty = product_conversion_main.conversion_ratio * units_qty
            new_conversion = {
                "src_product_id": product_conversion_main.prod_id.id,
                "src_uom": product_conversion_main.prod_id.uom_id.id,
                "from_location": stock_location_id,
                "qty_to_convert": units_qty,
                "conversion_line": [(0, 0, {
                    "conversion_ratio": product_conversion_main.conversion_ratio,
                    "dest_uom": product_data.uom_id.id,
                    "dest_product_id": product_id,
                    "allocate_quantity": units_qty,
                    "to_location": stock_location_id,
                    "converted_qty": converted_qty
                })]
            }
            product_conversion = self.env['product.conversion'].sudo().create(new_conversion)
            if product_conversion:
                product_conversion.validate()

        return True
