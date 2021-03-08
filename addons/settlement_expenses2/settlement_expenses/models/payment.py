from odoo import models, fields, api, _
from openerp.exceptions import UserError, ValidationError

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    settlement_expenses_id = fields.Many2one("settlement_expenses", string="Liquidacion", readonly=False, states={'reconciled': [('readonly', True)]}, ondelete='restrict')
   