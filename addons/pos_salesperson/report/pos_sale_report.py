# -*- coding: utf-8 -*-
from odoo import models, api


class ReportSaleDetailsInherit(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    @api.model
    def get_sale_details(self, date_start, date_stop, pos_salesperson_id, salesperson, configs):
        res = super(ReportSaleDetailsInherit, self).get_sale_details(
            date_start, date_stop, configs)

        categ_qty_dict = {}
        if pos_salesperson_id:
            order_ids = self.env['pos.order'].search([
                ('date_order', '>=', date_start),
                ('date_order', '<=', date_stop),
                ('state', 'in', ['paid', 'invoiced', 'done']),
                ('config_id', 'in', configs.ids),
                ('pos_salesperson_id', 'in', pos_salesperson_id)])

            for order_id in order_ids:
                categ_name = order_id.pos_salesperson_id.name
                for line in order_id.lines:
                    if categ_name in categ_qty_dict:
                        categ_qty_dict[categ_name][0] += line.qty
                        categ_qty_dict[categ_name][1] += line.price_subtotal_incl
                    else:
                        categ_qty_dict.update({categ_name: [0, 0]})
                        categ_qty_dict[categ_name][0] += line.qty
                        categ_qty_dict[categ_name][1] += line.price_subtotal_incl
        else:
            seller = self.env['pos.salesperson'].search([])
            order_ids = self.env['pos.order'].search([
                ('date_order', '>=', date_start),
                ('date_order', '<=', date_stop),
                ('state', 'in', ['paid', 'invoiced', 'done']),
                ('config_id', 'in', configs.ids),
                ('pos_salesperson_id', 'in', seller.ids)])

            for order_id in order_ids:
                categ_name = order_id.pos_salesperson_id.name
                for line in order_id.lines:
                    if categ_name in categ_qty_dict:
                        categ_qty_dict[categ_name][0] += line.qty
                        categ_qty_dict[categ_name][1] += line.price_subtotal_incl
                    else:
                        categ_qty_dict.update({categ_name: [0, 0]})
                        categ_qty_dict[categ_name][0] += line.qty
                        categ_qty_dict[categ_name][1] += line.price_subtotal_incl

        res.update({
            'categ_qty_dict': categ_qty_dict,
            'salesperson': salesperson})
        return res

    @api.multi
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        configs = self.env['pos.config'].browse(data['config_ids'])
        data.update(self.get_sale_details(
            data['date_start'], data['date_stop'], data['pos_salesperson_id'], data['salesperson'], configs))
        return data
