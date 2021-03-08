# -*- coding: utf-8 -*-

from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    is_salesperson_management = fields.Boolean('Manage Salesperson')
    pos_salesperson_ids = fields.Many2many(
        'pos.salesperson', 'pos_config_salesperson_rel', 'config_id', 'salesperson_id', string='Sellers')
