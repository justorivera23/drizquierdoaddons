# -*- coding: utf-8 -*-
from odoo import fields, models


class ReportPosOrder(models.Model):
    _inherit = "report.pos.order"

    user_id = fields.Many2one('res.users', string='Cashier', readonly=True)
    pos_salesperson_id = fields.Many2one(
        'pos.salesperson', string='Salesperson', readonly=True)

    def _select(self):
        return super(ReportPosOrder, self)._select() + ", s.pos_salesperson_id AS pos_salesperson_id"

    def _group_by(self):
            return super(ReportPosOrder, self)._group_by() + ", s.pos_salesperson_id"
