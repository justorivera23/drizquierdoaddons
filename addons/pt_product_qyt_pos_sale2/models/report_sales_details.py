# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from datetime import timedelta
import psycopg2
import pytz


class ReportSaleDetails(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    @api.model
    def get_sale_details_extra(self, date_start, date_stop, pos_salesperson_id, salesperson, configs):

        """ Serialise the orders of the day information

        params: date_start, date_stop string representing the datetime of order
        """
        if not configs:
            configs = self.env['pos.config'].search([])

        user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        today = user_tz.localize(fields.Datetime.from_string(fields.Date.context_today(self)))
        today = today.astimezone(pytz.timezone('UTC'))
        if date_start:
            date_start = fields.Datetime.from_string(date_start)
        else:
            # start by default today 00:00:00
            date_start = today

        if date_stop:
            # set time to 23:59:59
            date_stop = fields.Datetime.from_string(date_stop)
        else:
            # stop by default today 23:59:59
            date_stop = today + timedelta(days=1, seconds=-1)

        # avoid a date_stop smaller than date_start
        date_stop = max(date_stop, date_start)

        date_start = fields.Datetime.to_string(date_start)
        date_stop = fields.Datetime.to_string(date_stop)

        orders = self.env['pos.order'].search([
            ('date_order', '>=', date_start),
            ('date_order', '<=', date_stop),
            ('state', 'in', ['paid','invoiced','done']),
            ('config_id', 'in', configs.ids)])

        user_currency = self.env.user.company_id.currency_id

        total = 0.0
        products_sold = {}
        taxes = {}
        configs_locations = []
        for config in configs:
            configs_locations.append(config.stock_location_id.id)
        print('Ubicaciones', configs_locations)
        for order in orders:
            if user_currency != order.pricelist_id.currency_id:
                total += order.pricelist_id.currency_id._convert(
                    order.amount_total, user_currency, order.company_id, order.date_order or fields.Date.today())
            else:
                total += order.amount_total
            currency = order.session_id.currency_id

            for line in order.lines:
                key = (line.product_id, line.price_unit, line.discount)
                products_sold.setdefault(key, 0.0)
                products_sold[key] += line.qty

                if line.tax_ids_after_fiscal_position:
                    line_taxes = line.tax_ids_after_fiscal_position.compute_all(line.price_unit * (1-(line.discount or 0.0)/100.0), currency, line.qty, product=line.product_id, partner=line.order_id.partner_id or False)
                    for tax in line_taxes['taxes']:
                        taxes.setdefault(tax['id'], {'name': tax['name'], 'tax_amount':0.0, 'base_amount':0.0})
                        taxes[tax['id']]['tax_amount'] += tax['amount']
                        taxes[tax['id']]['base_amount'] += tax['base']
                else:
                    taxes.setdefault(0, {'name': _('No Taxes'), 'tax_amount':0.0, 'base_amount':0.0})
                    taxes[0]['base_amount'] += line.price_subtotal_incl

        st_line_ids = self.env["account.bank.statement.line"].search([('pos_statement_id', 'in', orders.ids)]).ids
        if st_line_ids:
            self.env.cr.execute("""
                SELECT aj.name, sum(amount) total
                FROM account_bank_statement_line AS absl,
                     account_bank_statement AS abs,
                     account_journal AS aj
                WHERE absl.statement_id = abs.id
                    AND abs.journal_id = aj.id
                    AND absl.id IN %s
                GROUP BY aj.name
            """, (tuple(st_line_ids),))
            payments = self.env.cr.dictfetchall()
        else:
            payments = []

        return {
            'currency_precision': user_currency.decimal_places,
            'total_paid': user_currency.round(total),
            'payments': payments,
            'company_name': self.env.user.company_id.name,
            'taxes': list(taxes.values()),
            'products': sorted([{
                'product_id': product.id,
                'product_name': product.name,
                'code': product.default_code,
                'quantity': qty,
                'qty_available':  product.with_context({'location': configs_locations}).qty_available,
                'price_unit': price_unit,
                'discount': discount,
                'uom': product.uom_id.name
            } for (product, price_unit, discount), qty in products_sold.items()], key=lambda l: l['product_name'])
        }
    
    @api.model
    def get_sale_details_salespersons(self, date_start, date_stop, pos_salesperson_id, salesperson, configs):
        res = self.get_sale_details_extra(date_start, date_stop, pos_salesperson_id, salesperson, configs)

        categ_qty_dict = {}
        configs_locations = []
        for config in configs:
            configs_locations.append(config.stock_location_id.id)
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
        data.update(self.get_sale_details_salespersons(
            data['date_start'], data['date_stop'], data['pos_salesperson_id'], data['salesperson'], configs))
        return data