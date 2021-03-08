# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosDetailsWizard(models.TransientModel):
    _inherit = 'pos.details.wizard'
    _description = "Sale Order Wizard"

    salesperson = fields.Boolean(string="Report by Sales Person")
    pos_salesperson_id = fields.Many2many(
        'pos.salesperson', string='Seller')

    @api.multi
    def generate_report(self):
        super(PosDetailsWizard, self).generate_report()
        data = {
            'date_start': self.start_date,
            'date_stop': self.end_date,
            'config_ids': self.pos_config_ids.ids,
            'salesperson': self.salesperson,
            'pos_salesperson_id': self.pos_salesperson_id.ids
        }
        return self.env.ref('point_of_sale.sale_details_report').report_action([], data=data)
