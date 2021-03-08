# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    pos_salesperson_id = fields.Many2one('pos.salesperson', string='Salesperson')
    user_id = fields.Many2one(
        comodel_name='res.users', string='Cashier',
        help="Person who uses the cash register. It can be a reliever, a student or an interim employee.",
        default=lambda self: self.env.uid,
        states={'done': [('readonly', True)], 'invoiced': [('readonly', True)]},
    )

    @api.model
    def _order_fields(self, ui_order):
        order_fields = super(PosOrder, self)._order_fields(ui_order)
        order_fields['pos_salesperson_id'] = ui_order.get('pos_salesperson_id', False)
        return order_fields
