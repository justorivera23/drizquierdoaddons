# -*- coding: utf-8 -*-

from odoo import fields, models, api
from decimal import Decimal, ROUND_HALF_UP
from odoo.tools import float_compare, float_is_zero
from odoo.exceptions import UserError, ValidationError


# SAT LAW REFERENCE AS 2019-11-25 for Agentes Retenedores de IVA
# ---------------------------------------------------------------------------------------------------------------
# |         AGENTE RETENCION        |      Producto / Operacion      |  % Retencion  |    Retener a partir de   |
# |-------------------------------------------------------------------------------------------------------------|
# | Exportadores                    | Agrícolas y pecuarios          |       65 %    |       Q 2,500.00         |
# |                                 | Producto no agropecuarios      |       15 %    |       Q 2,500.00         |
# |                                 | Bienes o servicios             |       15 %    |       Q 2,500.00         |
# |-------------------------------------------------------------------------------------------------------------|
# | Beneficiarios del Decreto 29-89 | Bienes o servicios             |       65 %    |       Q 2,500.00         |
# |-------------------------------------------------------------------------------------------------------------|
# | Sector publico                  | Bienes o servicios             |       25 %    |       Q 2,500.00         |
# |-------------------------------------------------------------------------------------------------------------|
# | Operadores de tarjetas de       | Pagos de tarjetahabientes      |       15 %    |    Cualquier Monto       |
# | Credito                         | Pago de combustibles           |      1.5 %    |    Cualquier Monto       |
# |-------------------------------------------------------------------------------------------------------------|
# | Contribuyentes especiales       | Bienes o servicios             |       15 %    |       Q 2,500.00         |
# |-------------------------------------------------------------------------------------------------------------|
# | Otros Agentes de retencion      | Bienes o servicios             |       15 %    |       Q 2,500.00         |
# |-------------------------------------------------------------------------------------------------------------|


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    tax_withholding_isr = fields.Selection(
        [
            ('quarter_witholding', 'Sujeto a Pagos Trimestrales'),
            ('definitive_withholding', 'Sujeto a Retención Definitiva'),
            ('small_taxpayer_withholding',
             'P.C. No genera Devolución de Crédito Fiscal')
        ], string="Retención ISR", default="quarter_witholding"
    )

    tax_withholding_price = fields.Float(string='Monto de retención')
    tax_withholding_other = fields.Boolean(string='Otro', default=False)
    tax_withholding_iva = fields.Selection(
        [
            ('no_witholding', 'No es agente rentenedor de IVA'),
            ('export', 'Exportadores'),
            ('decree_28_89', 'Beneficiarios del Decreto 28-89'),
            ('public_sector', 'Sector Público'),
            ('credit_cards_companies', 'Operadores de Tarjetas de Crédito y/o Débito'),
            ('special_taxpayer', 'Contribuyente Especiales'),
            ('others', 'Otros Agentes de Retención')
        ], string='Retención IVA', default=lambda self: self._set_initial_values())

    type_invoice = fields.Selection(
        [
            ('normal_invoice', 'Factura normal'),
            ('special_invoice', 'Factura especial')
        ], string='Tipo de factura', default='normal_invoice')

    supplier_id = fields.Many2one('res.partner', string='Proveedor Servicios', change_default=True,
                                  readonly=True, states={'draft': [('readonly', False)]},
                                  track_visibility='always', help="Ingresar el nombre del proveedor que tiene la factura.")

    tax_withold_amount = fields.Monetary(string='Retención ISR', store=True, readonly=True, compute='_compute_amount')
    tax_withholding_amount_iva = fields.Monetary(string='Retención IVA', store=True, readonly=True, compute='_compute_amount')
    user_country_id = fields.Char(
        string="UserCountry", default=lambda self: self.env.user.company_id.country_id.code)

    provider_invoice_serial = fields.Char(string="Factura serie")
    provider_invoice_number = fields.Char(string="Factura número")
    bank_operation_ref = fields.Char(string="Referencia bancaria")

    def _set_initial_values(self):
        initial_iva_withhold = 'no_witholding'

        if self.type == 'out_invoice':
            if self.partner_id.company_type == "company":
                initial_iva_withhold = self.partner_id.tax_withholding_iva
            else:
                initial_iva_withhold = self.partner_id.parent_id.tax_withholding_iva

        if self.type == 'in_invoice':
            initial_iva_withhold = self.env.user.company_id.tax_withholding_iva

        return initial_iva_withhold

    def update_amounts(self):
        supplier_invoices  = self.env['account.invoice'].search([
            ('state', 'in', ('open', 'in_payment')),
            ('tax_withold_amount', '>', 0)
        ])
        for invoice in supplier_invoices:
            invoice._compute_amount()

        supplier_invoices_iva  = self.env['account.invoice'].search([
            ('state', 'in', ('open', 'in_payment')),
            ('tax_withholding_amount_iva', '>', 0)
        ])
        for invoice in supplier_invoices_iva:
            invoice._compute_amount()

    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'tax_line_ids.amount_rounding',
                 'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_amount(self):
        response = super(AccountInvoice, self)._compute_amount()
        company_iva_agent_type = self.env.user.company_id.tax_withholding_iva

        tax_summary = 0

        self.amount_total = self.amount_untaxed + self.amount_tax - self.tax_withholding_price

        tax_withholding_isr = ''
        isr_withold_type = 0

        # VENTA
        isr_withold_type = ""
        if self.type == 'out_invoice':
            if self.partner_id.company_type == "company":
                isr_withold_type = self.partner_id.tax_withholding_isr
            else:
                isr_withold_type = self.partner_id.parent_id.tax_withholding_isr

            if self.partner_id.company_type == "company":
                partner_iva_agent_type = self.partner_id.tax_withholding_iva
            else:
                partner_iva_agent_type = self.partner_id.parent_id.tax_withholding_iva

            # IVA RETENECION
            # SI AMBOS, CLIENTE Y PROVEEDOR, SON AGENTES RETENEDORES DE IVA NO SE REALIZA LA RETENCION

            if partner_iva_agent_type is not 'no_witholding' and company_iva_agent_type == 'no_witholding' and self.journal_id.is_receipt_journal is False:
                iva_withhold_amount = 0
                if isr_withold_type == 'small_taxpayer_withholding' and self.amount_total >= 2500:
                    for invoice_line in self.invoice_line_ids:
                        total_amount = invoice_line.price_total
                        iva_amount = total_amount * 0.05
                        iva_withhold_amount += iva_amount
                elif self.type_invoice == 'special_invoice' and self.amount_total >= 2500:
                    for invoice_line in self.invoice_line_ids:
                        iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                        iva_withhold_amount += iva_amount
                else:
                    if partner_iva_agent_type == 'export' and self.amount_total >= 2500:
                        iva_withhold_amount = 0
                        for invoice_line in self.invoice_line_ids:
                            line_amount = invoice_line.price_unit * invoice_line.quantity

                            # EVERY PRODUCT CATEGORY TAX PERCENTAGE IS SEPARATE IN CASE OF FUTHER LAW CHANGES

                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'agriculture':
                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.65
                                iva_withhold_amount += iva_amount

                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'not_agriculture':
                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount

                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal

                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount

                    if partner_iva_agent_type == 'decree_28_89' and self.amount_total >= 2500:
                        for invoice_line in self.invoice_line_ids:
                            line_amount = invoice_line.price_unit * invoice_line.quantity
                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.65
                                iva_withhold_amount += iva_amount

                    if partner_iva_agent_type == 'public_sector' and self.amount_total >= 2500:
                        for invoice_line in self.invoice_line_ids:
                            line_amount = invoice_line.price_unit * invoice_line.quantity
                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.25
                                iva_withhold_amount += iva_amount

                    if partner_iva_agent_type == 'credit_cards_companies' and self.amount_total >= 2500:
                        for invoice_line in self.invoice_line_ids:
                            line_amount = invoice_line.price_unit * invoice_line.quantity
                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'payment_creditholders':
                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount

                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'fuel_payments':
                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.015
                                iva_withhold_amount += iva_amount

                    if partner_iva_agent_type == 'special_taxpayer' and self.amount_total >= 2500:
                        for invoice_line in self.invoice_line_ids:
                            line_amount = invoice_line.price_unit * invoice_line.quantity
                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount
                            else:
                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount

                    if partner_iva_agent_type == 'others' and self.amount_total >= 2500:
                        for invoice_line in self.invoice_line_ids:
                            line_amount = invoice_line.price_unit * invoice_line.quantity
                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount
                            else:
                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount

                self.tax_withholding_amount_iva = iva_withhold_amount
                self.amount_total = self.amount_total - iva_withhold_amount

        # COMPRA
        if self.type == 'in_invoice':
            if self.partner_id.company_type == "company":
                isr_withold_type = self.partner_id.tax_withholding_isr
            else:
                isr_withold_type = self.partner_id.parent_id.tax_withholding_isr

            if self.partner_id.company_type == "company":
                partner_iva_agent_type = self.partner_id.tax_withholding_iva
            else:
                partner_iva_agent_type = self.partner_id.parent_id.tax_withholding_iva

            # IVA RETENECION
            # SI AMBOS, CLIENTE Y PROVEEDOR, SON AGENTES RETENEDORES DE IVA NO SE REALIZA LA RETENCION

            if company_iva_agent_type is not 'no_witholding' and partner_iva_agent_type == 'no_witholding' and self.journal_id.is_receipt_journal is False:
                iva_withhold_amount = 0
                if isr_withold_type == 'small_taxpayer_withholding' and self.amount_total >= 2500:
                    for invoice_line in self.invoice_line_ids:
                        total_amount = invoice_line.price_total
                        iva_amount = total_amount * 0.05
                        iva_withhold_amount += iva_amount
                elif self.type_invoice == 'special_invoice' and self.amount_total >= 2500:
                    for invoice_line in self.invoice_line_ids:
                        iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                        iva_withhold_amount += iva_amount
                else:
                    if company_iva_agent_type == 'export' and self.amount_total >= 2500:
                        iva_withhold_amount = 0
                        for invoice_line in self.invoice_line_ids:
                            line_amount = invoice_line.price_unit * invoice_line.quantity

                            # EVERY PRODUCT CATEGORY TAX PERCENTAGE IS SEPARATE IN CASE OF FUTHER LAW CHANGES

                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'agriculture':
                                # iva_amount = line_amount / 1.12
                                iva_amount = iva_amount * 0.12
                                iva_amount = iva_amount * 0.65
                                iva_withhold_amount += iva_amount

                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'not_agriculture':
                                # iva_amount = line_amount / 1.12
                                iva_amount = invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.12
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount

                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                # iva_amount = line_amount / 1.12
                                iva_amount = invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.12
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount

                    if company_iva_agent_type == 'decree_28_89' and self.amount_total >= 2500:
                        for invoice_line in self.invoice_line_ids:
                            line_amount = invoice_line.price_unit * invoice_line.quantity
                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                # iva_amount = line_amount / 1.12
                                iva_amount = invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.12
                                iva_amount = iva_amount * 0.65
                                iva_withhold_amount += iva_amount

                    if company_iva_agent_type == 'public_sector' and self.amount_total >= 2500:
                        for invoice_line in self.invoice_line_ids:
                            line_amount = invoice_line.price_unit * invoice_line.quantity
                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                # iva_amount = line_amount / 1.12
                                iva_amount = invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.12
                                iva_amount = iva_amount * 0.25
                                iva_withhold_amount += iva_amount

                    if company_iva_agent_type == 'credit_cards_companies' and self.amount_total >= 2500:
                        for invoice_line in self.invoice_line_ids:
                            line_amount = invoice_line.price_unit * invoice_line.quantity
                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'payment_creditholders':
                                # iva_amount = line_amount / 1.12
                                iva_amount = invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.12
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount

                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'fuel_payments':
                                # iva_amount = line_amount / 1.12
                                iva_amount = invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.12
                                iva_amount = iva_amount * 0.015
                                iva_withhold_amount += iva_amount

                    if company_iva_agent_type == 'special_taxpayer' and self.amount_total >= 2500:
                        for invoice_line in self.invoice_line_ids:
                            line_amount = invoice_line.price_unit * invoice_line.quantity
                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                # iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                # iva_amount = line_amount / 1.12
                                iva_amount = invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.12
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount
                            else:
                                # iva_amount = line_amount / 1.12
                                iva_amount = invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.12
                                iva_amount = iva_amount * 0.15
                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount

                    if company_iva_agent_type == 'others' and self.amount_total >= 2500:
                        for invoice_line in self.invoice_line_ids:
                            line_amount = invoice_line.price_unit * invoice_line.quantity
                            if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                # iva_amount = line_amount / 1.12
                                iva_amount = invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.12
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount
                            else:
                                # iva_amount = line_amount / 1.12
                                iva_amount = invoice_line.price_subtotal
                                iva_amount = iva_amount * 0.12
                                iva_amount = iva_amount * 0.15
                                iva_withhold_amount += iva_amount

                self.tax_withholding_amount_iva = iva_withhold_amount
                self.amount_total = self.amount_total - iva_withhold_amount

        if isr_withold_type == 'definitive_withholding' and self.journal_id.is_receipt_journal is False:
            if self.amount_untaxed > 30000.00:
                isr_amount = 0
                isr_amount = Decimal(float(isr_amount))
                base_amount = self.amount_untaxed - 30000
                isr_amount = (((base_amount * 7) / 100.00) + 1500.00)
                isr_amount = Decimal(isr_amount).quantize(Decimal('0.01'), ROUND_HALF_UP)
                self.tax_withold_amount = isr_amount
                self.amount_total = self.amount_total - self.tax_withold_amount
            if self.amount_untaxed >= 2500.00 and self.amount_untaxed <= 30000.00:
                isr_amount = 0
                isr_amount = Decimal(float(isr_amount))
                isr_amount = ((self.amount_untaxed * 5) / 100.00)
                isr_amount = Decimal(isr_amount).quantize(Decimal('0.01'), ROUND_HALF_UP)
                self.tax_withold_amount = isr_amount
                self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
                self.amount_total = self.amount_total - self.tax_withold_amount

            if self.type_invoice == 'special_invoice' and self.amount_untaxed > 30000.00:

                isr_amount = 0
                isr_amount = Decimal(float(isr_amount))
                isr_amount = (((self.amount_untaxed * 7) / 100.00) + 1500.00)
                isr_amount = Decimal(isr_amount).quantize(Decimal('0.01'), ROUND_HALF_UP)
                self.tax_withold_amount = isr_amount
                self.amount_total = self.amount_total - self.tax_withold_amount

            if self.type_invoice == 'special_invoice' and self.amount_untaxed >= 2500.00 and self.amount_untaxed <= 30000.00:
                isr_amount = 0
                isr_amount = Decimal(float(isr_amount))
                isr_amount = ((self.amount_untaxed * 5) / 100.00)
                isr_amount = Decimal(isr_amount).quantize(Decimal('0.01'), ROUND_HALF_UP)
                self.tax_withold_amount = isr_amount
                self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
                self.amount_total = self.amount_total - self.tax_withold_amount

        if self.type_invoice == "special_invoice":
            self.amount_total = self.amount_untaxed + self.amount_tax

        self.amount_total_signed = self.amount_total
        self.amount_total_company_signed = self.amount_total
        self.residual_signed = self.residual
        self.residual_company_signed = self.residual

        return response

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        response = super(AccountInvoice, self)._onchange_partner_id()
        company_iva_agent_type = self.env.user.company_id.tax_withholding_iva

        if self.partner_id.tax_withholding_isr == "small_taxpayer_withholding" and self.type == 'in_invoice':
            for invoice_lines in self.invoice_line_ids:
                invoice_lines.invoice_line_tax_ids = False
                self.tax_line_ids = False
        else:
            default_tax = False
            if self.type == 'out_invoice':
                default_tax = self.env.user.company_id.account_sale_tax_id
            if self.type == 'in_invoice':
                default_tax = self.env.user.company_id.account_purchase_tax_id

                for invoice_lines in self.invoice_line_ids:
                    if len(invoice_lines.invoice_line_tax_ids) == 0:
                        tax_ids = []
                        if invoice_lines.product_id.product_tmpl_id.taxes_id.id is False:
                            tax_ids.append((4, default_tax.id, None))
                            if default_tax.id:
                                invoice_lines.invoice_line_tax_ids = tax_ids
                        else:
                            if self.type == 'out_invoice':
                                if default_tax is not False:
                                    for tax in invoice_lines.product_id.product_tmpl_id.taxes_id:
                                        tax_ids.append((4, tax.id, None))
                                    if tax_ids:
                                        invoice_lines.invoice_line_tax_ids = tax_ids
                                if default_tax.id:
                                    invoice_lines.invoice_line_tax_ids = tax_ids
                            if self.type == 'in_invoice':
                                if default_tax is not False:
                                    for tax in invoice_lines.product_id.product_tmpl_id.supplier_taxes_id:
                                        tax_ids.append((4, tax.id, None))
                                    if tax_ids:
                                        invoice_lines.invoice_line_tax_ids = tax_ids
                                if default_tax.id:
                                    invoice_lines.invoice_line_tax_ids = tax_ids

        if self.partner_id:
            isr_withold_type = ""
            iva_withold_type = ""

            if self.partner_id.company_type == "company":
                isr_withold_type = self.partner_id.tax_withholding_isr
            else:
                isr_withold_type = self.partner_id.parent_id.tax_withholding_isr

            self.tax_withholding_isr = isr_withold_type

            if self.journal_id.is_receipt_journal is False:

                if self.type == 'out_invoice':
                    if self.partner_id.company_type == "company":
                        company_iva_agent_type = self.partner_id.tax_withholding_iva
                    else:
                        company_iva_agent_type = self.partner_id.parent_id.tax_withholding_iva

                    if company_iva_agent_type is not 'no_witholding':
                        self.tax_withholding_iva = company_iva_agent_type
                        self.amount_total = self.amount_total + self.tax_withholding_amount_iva
                        self.tax_withholding_amount_iva = 0
                    else:
                        self.tax_withholding_iva = company_iva_agent_type

                # FACTURAS COMPRA
                if self.type == 'in_invoice':
                    if company_iva_agent_type is not 'no_witholding':
                        self.tax_withholding_iva = company_iva_agent_type
                        self.amount_total = self.amount_total + self.tax_withholding_amount_iva
                        self.tax_withholding_amount_iva = 0
                    else:
                        self.tax_withholding_iva = company_iva_agent_type

        return response

    @api.onchange('incoterm_id')
    def _onchange_incoterm_id(self):
        type_expense = self.tipo_gasto
        #Banderas que verifican el tipo de facturas
        is_compra = False
        is_service = False
        is_mix = False
        is_import = False
        is_gas = False
        flag_gas = False
        #Recorre todos los productos que están dentro de la facturas
        #Verifica el tipo y así cambia la bandera del tipo para dejar
        #un tipo de factura
        for invoice_lines in self.invoice_line_ids:
            #Si existe incoterm
            if self.incoterm_id:
                is_import = True
                break

            #Si existe un impuesto
            if invoice_lines.invoice_line_tax_ids:
                for tax in invoice_lines.invoice_line_tax_ids:
                    if tax.sat_tax_type == 'gas':
                        if is_compra or is_service:
                            is_mix = True
                        else:
                            is_gas = True
                            flag_gas = True
                if flag_gas:
                    flag_gas = False
                    continue

            #Si la línea de factura es un producto
            if invoice_lines.product_id.type == 'product' or invoice_lines.product_id.type == 'consu':
                if is_service or is_gas:
                    is_mix = True
                else:
                    is_compra = True

            #Si la línea de factura es un servicio
            elif invoice_lines.product_id.type == 'service':
                if is_compra or is_gas:
                    is_mix = True
                else:
                    is_service = True

        #Cambia el tipo de la factura dependiendo el tipo de las líneas de la facturas
        if is_mix:
            self.tipo_gasto = 'mixto'
        elif is_compra:
            self.tipo_gasto='compra'
        elif is_service:
            self.tipo_gasto = 'servicio'
        elif is_import:
            self.tipo_gasto = 'importacion'
        elif is_gas:
            self.tipo_gasto = 'combustible'

    @api.onchange('invoice_line_ids', 'tax_withold_amount')
    def _onchange_invoice_line_ids(self):
        res = super(AccountInvoice, self)._onchange_invoice_line_ids()

        type_expense = self.tipo_gasto
        #Banderas que verifican el tipo de facturas
        is_compra = False
        is_service = False
        is_mix = False
        is_import = False
        is_gas = False
        flag_gas = False
        #Recorre todos los productos que están dentro de la facturas
        #Verifica el tipo y así cambia la bandera del tipo para dejar
        #un tipo de factura
        for invoice_lines in self.invoice_line_ids:
            #Si existe incoterm
            if self.incoterm_id:
                is_import = True
                break

            #Si existe un impuesto
            if invoice_lines.invoice_line_tax_ids:
                for tax in invoice_lines.invoice_line_tax_ids:
                    if tax.sat_tax_type == 'gas':
                        if is_compra or is_service:
                            is_mix = True
                        else:
                            is_gas = True
                            flag_gas = True
                if flag_gas:
                    flag_gas = False
                    continue

            #Si la línea de factura es un producto
            if invoice_lines.product_id.type == 'product' or invoice_lines.product_id.type == 'consu':
                if is_service or is_gas:
                    is_mix = True
                else:
                    is_compra = True

            #Si la línea de factura es un servicio
            elif invoice_lines.product_id.type == 'service':
                if is_compra or is_gas:
                    is_mix = True
                else:
                    is_service = True

        #Cambia el tipo de la factura dependiendo el tipo de las líneas de la facturas
        if is_mix:
            self.tipo_gasto = 'mixto'
        elif is_compra:
            self.tipo_gasto = 'compra'
        elif is_service:
            self.tipo_gasto = 'servicio'
        elif is_import:
            self.tipo_gasto = 'importacion'
        elif is_gas:
            self.tipo_gasto = 'combustible'


        account_id = 7
        self._compute_amount()
        if self.partner_id.tax_withholding_isr == "small_taxpayer_withholding" and self.type == 'in_invoice':
            for invoice_lines in self.invoice_line_ids:
                invoice_lines.invoice_line_tax_ids = False
                self.tax_line_ids = False

        else:
            if self.type_invoice == "special_invoice":
                tax_obj = self.env['account.tax'].search(
                    [('name', '=', 'IVA FACTURAS ESPECIALES'), ('company_id', '=', self.company_id.id)], limit=1)
                account_id = 7
                if tax_obj:
                    account_id = tax_obj.account_id.id
                iva_create = {'invoice_id': self.id, 'name': "IVA FACTURAS ESPECIALES", 'amount': self.amount_tax * -1, 'manual': False, 'sequence': 0, 'account_analytic_id': False, 'account_id':  account_id, 'analytic_tag_ids': False}
                tax_obj = self.env['account.tax'].search([('name', '=', 'ISR FACTURAS ESPECIALES'), ('company_id', '=', self.company_id.id)], limit=1)
                account_id = 7
                if tax_obj:
                    account_id = tax_obj.account_id.id

            taxes_grouped = self.get_taxes_values()
            tax_lines = self.tax_line_ids.filtered('manual')
            counter = 0
            for tax in taxes_grouped.values():
                tax_lines += tax_lines.new(tax)

                if self.type_invoice == "FE" and self.tax_withold_amount > 0:
                    tax_lines += tax_lines.new(iva_create)
            self.tax_line_ids = tax_lines

        return res

    def organize_moves(self):

        provider_invoices = self.env['account.invoice'].search([
            ('type', '=', 'in_invoice')
        ])

        for invoice in provider_invoices:

            is_compra = False
            is_service = False
            is_mix = False
            is_import = False
            is_gas = False
            flag_gas = False


            for invoice_lines in invoice.invoice_line_ids:
                #Si existe incoterm
                if invoice.incoterm_id:
                    is_import = True
                    break
                #Si existe un impuesto
                if invoice_lines.invoice_line_tax_ids:
                    for tax in invoice_lines.invoice_line_tax_ids:
                        if tax.sat_tax_type == 'gas':
                            if is_compra or is_service:
                                is_mix = True
                                flag_gas = True
                            else:
                                is_gas = True
                                flag_gas = True
                    if flag_gas:
                        flag_gas = False
                        continue

                #Si la línea de factura es un producto
                if invoice_lines.product_id.type == 'product' or invoice_lines.product_id.type == 'consu':
                    if is_service or is_gas:
                        is_mix = True
                    else:
                        is_compra = True

                #Si la línea de factura es un servicio
                elif invoice_lines.product_id.type == 'service':
                    if is_compra or is_gas:
                        is_mix = True
                    else:
                        is_service = True

            if is_mix:
                invoice.write({"tipo_gasto":"mixto"})
            elif is_compra:
                invoice.write({"tipo_gasto": 'compra'})
            elif is_service:
                invoice.write({"tipo_gasto":"servicio"})
            elif is_import:
                invoice.write({"tipo_gasto":'importacion'})
            elif is_gas:
                invoice.write({"tipo_gasto":'combustible'})

    @api.one
    @api.depends(
        'state', 'currency_id', 'invoice_line_ids.price_subtotal',
        'move_id.line_ids.amount_residual',
        'move_id.line_ids.currency_id')
    def _compute_residual(self):
        residual = 0.0
        residual_company_signed = 0.0
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        for line in self._get_aml_for_amount_residual():
            residual_company_signed += line.amount_residual
            if line.currency_id == self.currency_id:
                residual += line.amount_residual_currency if line.currency_id else line.amount_residual
            else:
                from_currency = line.currency_id or line.company_id.currency_id
                residual += from_currency._convert(line.amount_residual, self.currency_id, line.company_id, line.date or fields.Date.today())
        self.residual_company_signed = abs(residual_company_signed) * sign
        self.residual_signed = abs(residual) * sign
        self.residual = abs(residual)

        if self.journal_id.is_receipt_journal is False:

            if self.tax_withold_amount > 0:
                self.residual = self.residual - self.tax_withold_amount

            if self.tax_withholding_amount_iva > 0:
                self.residual = self.residual - self.tax_withholding_amount_iva

        digits_rounding_precision = self.currency_id.rounding
        if float_is_zero(self.residual, precision_rounding=digits_rounding_precision):
            self.reconciled = True
        else:
            self.reconciled = False

    def _get_aml_for_amount_residual(self):
        """ Get the aml to consider to compute the amount residual of invoices """
        self.ensure_one()
        return self.sudo().move_id.line_ids.filtered(lambda l: l.account_id == self.account_id)

    @api.multi
    def action_invoice_open(self):  
        res = super(AccountInvoice, self).action_invoice_open()
        self._compute_amount()

        if self.tax_withold_amount > 0 and self.type == 'in_invoice' and self.journal_id.is_receipt_journal is False:

            if self.env.user.company_id.isr_retencion_account_id.id is False:
                raise ValidationError('Debe seleccionar un diario para las retenciones de ISR en configuración de contabilidad')

            if self.env.user.company_id.isr_retencion_account_id.default_credit_account_id.id is False:
                raise ValidationError('Debe seleccionar una cuenta de crédito para el diario de retenciones de ISR en configuración de contabilidad')

            if self.env.user.company_id.isr_retencion_account_id.default_debit_account_id.id is False:
                raise ValidationError('Debe seleccionar una cuentas de débito para el diario de retenciones de ISR en configuración de contabilidad')

            retencion_isr_journal_id = self.env.user.company_id.isr_retencion_account_id.id
            credit_account_id = self.env.user.company_id.isr_retencion_account_id.default_credit_account_id.id
            debit_account_id = self.env.user.company_id.isr_retencion_account_id.default_debit_account_id.id

            user_id = self.env.user.id
            company_id = self.env.user.company_id.id
            currency_id = self.env.user.company_id.currency_id.id

            move_name = "RETENCION ISR - " + str(self.move_name)

            credit_new_line_ids = {
                'name': move_name,
                'debit': 0.0,
                'credit': self.tax_withold_amount,
                'account_id': credit_account_id,
                'invoice_id': self.id,
                'date': self.date_invoice
            }

            debit_new_line_ids = {
                'name': move_name,
                'debit': self.tax_withold_amount,
                'credit': 0.0,
                'account_id': debit_account_id,
                'invoice_id': self.id,
                'date': self.date_invoice
            }

            lines_ids = []
            lines_ids.append(credit_new_line_ids)
            lines_ids.append(debit_new_line_ids)

            new_account_move = {
                'name': move_name,
                'ref': move_name,
                'journal_id': retencion_isr_journal_id,
                'currency_id': currency_id,
                'state': 'posted',
                'line_ids': [(0, 0, line) for line in lines_ids],
                'amount': self.tax_withold_amount,
                'narration': 'FACTURA ' + str(self.name),
                'company_id': company_id,
                'date': self.date_invoice
            }
            account_move = self.env['account.move'].create(new_account_move)


        if self.tax_withholding_amount_iva > 0 and self.type == 'in_invoice' and self.journal_id.is_receipt_journal is False:

            if self.env.user.company_id.iva_retencion_account_id.id is False:
                raise ValidationError('Debe seleccionar un diario para las retenciones de IVA en configuración de contabilidad')

            if self.env.user.company_id.iva_retencion_account_id.default_credit_account_id.id is False:
                raise ValidationError('Debe seleccionar una cuenta de cŕedito para el diario de retenciones de IVA en configuración de contabilidad')

            if self.env.user.company_id.iva_retencion_account_id.default_debit_account_id.id is False:
                raise ValidationError('Debe seleccionar una cuenta de débito para el diario de retenciones de IVA en configuración de contabilidad')

            retencion_iva_journal_id = self.env.user.company_id.iva_retencion_account_id.id
            credit_account_id = self.env.user.company_id.iva_retencion_account_id.default_credit_account_id.id
            debit_account_id = self.env.user.company_id.iva_retencion_account_id.default_debit_account_id.id

            user_id = self.env.user.id
            company_id = self.env.user.company_id.id
            currency_id = self.env.user.company_id.currency_id.id

            move_name = "RETENCION IVA - " + str(self.move_name)

            credit_new_line_ids = {
                'name': move_name,
                'debit': 0.0,
                'credit': self.tax_withholding_amount_iva,
                'account_id': credit_account_id,
                'invoice_id': self.id,
                'date': self.date_invoice
            }

            debit_new_line_ids = {
                'name': move_name,
                'debit': self.tax_withholding_amount_iva,
                'credit': 0.0,
                'account_id': debit_account_id,
                'invoice_id': self.id,
                'date': self.date_invoice
            }

            lines_ids = []
            lines_ids.append(credit_new_line_ids)
            lines_ids.append(debit_new_line_ids)

            new_account_move = {
                'name': move_name,
                'ref': move_name,
                'journal_id': retencion_iva_journal_id,
                'currency_id': currency_id,
                'state': 'posted',
                'line_ids': [(0, 0, line) for line in lines_ids],
                'amount': self.tax_withholding_amount_iva,
                'narration': 'FACTURA ' + str(self.name),
                'company_id': company_id,
                'date': self.date_invoice
            }
            account_move = self.env['account.move'].create(new_account_move)

        return res


    @api.multi
    def action_invoice_cancel(self):

        res = super(AccountInvoice, self).action_invoice_cancel()

        if self.tax_withold_amount > 0 and self.type == 'in_invoice' and self.journal_id.is_receipt_journal is False:

            if self.env.user.company_id.isr_retencion_account_id.id is False:
                raise ValidationError('Debe seleccionar un diario para las retenciones de ISR en configuración de contabilidad')

            if self.env.user.company_id.isr_retencion_account_id.default_credit_account_id.id is False:
                raise ValidationError('Debe seleccionar una cuenta de crédito para el diario de retenciones de ISR en configuración de contabilidad')

            if self.env.user.company_id.isr_retencion_account_id.default_debit_account_id.id is False:
                raise ValidationError('Debe seleccionar una cuentas de débito para el diario de retenciones de ISR en configuración de contabilidad')

            retencion_isr_journal_id = self.env.user.company_id.isr_retencion_account_id.id
            credit_account_id = self.env.user.company_id.isr_retencion_account_id.default_credit_account_id.id
            debit_account_id = self.env.user.company_id.isr_retencion_account_id.default_debit_account_id.id

            user_id = self.env.user.id
            company_id = self.env.user.company_id.id
            currency_id = self.env.user.company_id.currency_id.id

            move_name = "RETENCION ISR - " + str(self.move_name)

            credit_new_line_ids = {
                'name': move_name,
                'debit': self.tax_withold_amount,
                'credit': 0.0,
                'account_id': credit_account_id,
                'invoice_id': self.id,
                'date': self.date_invoice
            }

            debit_new_line_ids = {
                'name': move_name,
                'debit': 0.0,
                'credit': self.tax_withold_amount,
                'account_id': debit_account_id,
                'invoice_id': self.id,
                'date': self.date_invoice
            }

            lines_ids = []
            lines_ids.append(credit_new_line_ids)
            lines_ids.append(debit_new_line_ids)

            new_account_move = {
                'name': move_name,
                'ref': move_name,
                'journal_id': retencion_isr_journal_id,
                'currency_id': currency_id,
                'state': 'posted',
                'line_ids': [(0, 0, line) for line in lines_ids],
                'amount': self.tax_withold_amount,
                'narration': 'FACTURA ' + str(self.name),
                'company_id': company_id,
                'date': self.date_invoice
            }
            account_move = self.env['account.move'].create(new_account_move)
            self.residual = 0.0

        if self.tax_withholding_amount_iva > 0 and self.type == 'in_invoice' and self.journal_id.is_receipt_journal is False:

            if self.env.user.company_id.iva_retencion_account_id.id is False:
                raise ValidationError('Debe seleccionar un diario para las retenciones de IVA en configuración de contabilidad')

            if self.env.user.company_id.iva_retencion_account_id.default_credit_account_id.id is False:
                raise ValidationError('Debe seleccionar una cuenta de cŕedito para el diario de retenciones de IVA en configuración de contabilidad')

            if self.env.user.company_id.iva_retencion_account_id.default_debit_account_id.id is False:
                raise ValidationError('Debe seleccionar una cuenta de débito para el diario de retenciones de IVA en configuración de contabilidad')

            retencion_iva_journal_id = self.env.user.company_id.iva_retencion_account_id.id
            credit_account_id = self.env.user.company_id.iva_retencion_account_id.default_credit_account_id.id
            debit_account_id = self.env.user.company_id.iva_retencion_account_id.default_debit_account_id.id

            user_id = self.env.user.id
            company_id = self.env.user.company_id.id
            currency_id = self.env.user.company_id.currency_id.id

            move_name = "RETENCION IVA - " + str(self.move_name)

            credit_new_line_ids = {
                'name': move_name,
                'debit': self.tax_withholding_amount_iva,
                'credit': 0.0,
                'account_id': credit_account_id,
                'invoice_id': self.id,
                'date': self.date_invoice
            }

            debit_new_line_ids = {
                'name': move_name,
                'debit': 0.0,
                'credit': self.tax_withholding_amount_iva,
                'account_id': debit_account_id,
                'invoice_id': self.id,
                'date': self.date_invoice
            }

            lines_ids = []
            lines_ids.append(credit_new_line_ids)
            lines_ids.append(debit_new_line_ids)

            new_account_move = {
                'name': move_name,
                'ref': move_name,
                'journal_id': retencion_iva_journal_id,
                'currency_id': currency_id,
                'state': 'posted',
                'line_ids': [(0, 0, line) for line in lines_ids],
                'amount': self.tax_withholding_amount_iva,
                'narration': 'FACTURA ' + str(self.name),
                'company_id': company_id,
                'date': self.date_invoice
            }
            account_move = self.env['account.move'].create(new_account_move)
            self.residual = 0.0

        return res
