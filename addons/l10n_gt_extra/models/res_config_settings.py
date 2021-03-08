# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    iva_retencion_account_id = fields.Many2one('account.journal', related="company_id.iva_retencion_account_id", string='Diario de retencion de IVA', readonly=False)
    isr_retencion_account_id = fields.Many2one('account.journal', related="company_id.isr_retencion_account_id", string='Diario de retencion de ISR', readonly=False)
