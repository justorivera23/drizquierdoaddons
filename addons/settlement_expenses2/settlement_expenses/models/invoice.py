# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    settlement_expenses_id = fields.Many2one("settlement_expenses", string="Liquidacion", readonly=False, states={'paid': [('readonly', True)]}, ondelete='restrict')