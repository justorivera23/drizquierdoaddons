# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_receipt_journal = fields.Boolean(string="¿Es recibo?")
