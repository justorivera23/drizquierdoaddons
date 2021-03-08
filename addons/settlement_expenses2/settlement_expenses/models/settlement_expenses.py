# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging 

class SettlementExpensesSettlement(models.Model):
    _name = 'settlement_expenses'
    _description = 'Liquidación'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']

    settlement_date = fields.Date(string="Fecha", required=True)
    name = fields.Char(string="Descripcion", required=True)
    invoice_id = fields.One2many("account.invoice", "settlement_expenses_id", string="Facturas")
    payment_id = fields.One2many("account.payment", "settlement_expenses_id", string="Pagos")
    company_id = fields.Many2one("res.company", string="Empresa", required=True, default=lambda self: self.env.user.company_id.id)
    journal_id = fields.Many2one("account.journal", string="Diario", required=True)
    account_move_id = fields.Many2one("account.move", string="Asiento")
    employee_id = fields.Many2one("hr.employee", string="Empleado")
    adjustment_account_id = fields.Many2one("account.account", string="Cuenta de desajuste")

    # =========== TOTAL FIELDS ===========
    currency_id = fields.Many2one('res.currency', string="Moneda")
    invoice_total = fields.Monetary(string="Total de facturas", compute="get_invoice_totals")
    payment_total = fields.Monetary(string="Total de pagos", compute="get_payment_totals")
    final_balance = fields.Monetary(string="Balance final", compute="get_final_balance")

    def get_final_balance(self):
        for rec in self:
            # rec.invoice_total = rec.invoice_total * -1
            rec.final_balance = rec.payment_total - rec.invoice_total

    def get_invoice_totals(self):
        company_currency_id = self.env.user.company_id.currency_id.id
        for rec in self:
            total = 0
            for invoice in rec.invoice_id:
                if invoice.type == 'in_invoice':
                    if invoice.currency_id.id != company_currency_id:
                        invoice_currency = self.env['res.currency.rate'].search([
                            ('currency_id', '=', invoice.currency_id.id),
                            ('name', '=', invoice.invoice_date),
                            ('company_id', '=', self.env.user.company_id.id)
                        ], limit=1)
                        invoice_conversion_rate = invoice_currency.rate
                        # invoice_conversion_rate = invoice.currency_id.with_context(date='2020-04-26').rate
                        invoice_amount = invoice.amount_total
                        if invoice_conversion_rate > 0:
                            invoice_amount = invoice.amount_total / invoice_conversion_rate
                        total += invoice_amount
                    else:
                        total += invoice.amount_total

            print('Invoice total', total)
            rec.invoice_total = total

    def get_payment_totals(self):
        company_currency_id = self.env.user.company_id.currency_id.id
        for rec in self:
            total = 0
            for payment in rec.payment_id:
                if payment.payment_type == 'outbound':
                    if payment.currency_id.id != company_currency_id:
                        outbound_currency = self.env['res.currency.rate'].search([
                            ('currency_id', '=', payment.currency_id.id),
                            ('name', '=', payment.payment_date),
                            ('company_id', '=', self.env.user.company_id.id)
                        ], limit=1)
                        conversion_rate = outbound_currency.rate
                        payment_amount = payment.amount
                        if conversion_rate > 0:
                            payment_amount = payment.amount / conversion_rate
                        total += payment_amount
                    else:
                        total += payment.amount
                if payment.payment_type == 'inbound':
                    if payment.currency_id.id != company_currency_id:
                        inbound_currency = self.env['res.currency.rate'].search([
                            ('currency_id', '=', payment.currency_id.id),
                            ('name', '=', payment.payment_date),
                            ('company_id', '=', self.env.user.company_id.id)
                        ], limit=1)
                        conversion_rate = inbound_currency.rate
                        payment_amount = payment.amount
                        if conversion_rate > 0:
                            payment_amount = payment.amount / conversion_rate
                        total -= payment_amount
                    else:
                        total -= payment.amount
            print('Payment total', total)
            rec.payment_total = total

    @api.multi
    def conciliar(self):
        for rec in self:
            lines = []

            total = 0
            for invoice in rec.invoice_id:
                if invoice.state == "draft":
                    raise UserError('La factura  %s no esta validada' % (invoice.number))

                for invoice_lines in invoice.move_id.line_ids:

                    if invoice_lines.account_id.reconcile:
                        if not invoice_lines.reconciled:
                            total += invoice_lines.credit - invoice_lines.debit
                            lines.append(invoice_lines)
                        else:
                            raise UserError('La factura %s ya esta conciliada' % (invoice.number))

            for payment in rec.payment_id:
                payment_type = payment.payment_type
                for l in payment.move_line_ids:
                    if l.account_id.reconcile:
                        if not l.reconciled :
                            if payment_type == 'outbound' and l.debit > 0:
                                # total -= payment_line.debit - payment_line.credit
                                total = total - l.debit
                                lines.append(l)
                            if payment_type == 'inbound' and l.credit > 0:
                                # total -= payment_line.debit - payment_line.credit
                                total = total + l.credit
                                lines.append(l)
                        else:
                            raise UserError('El cheque %s ya esta conciliado' % (payment.name))

            print('Total PRE', total)
            if round(total) != 0 and not rec.adjustment_account_id:
                raise UserError('Debe seleccionar la cuenta de desajuste')

            print('Total', total)

            pairs = []
            new_lines = []
            for line in lines:
                new_lines.append((0, 0, {
                    'name': line.name,
                    'debit': line.credit,
                    'credit': line.debit,
                    'account_id': line.account_id.id,
                    'partner_id': line.partner_id.id,
                    'journal_id': rec.journal_id.id,
                    'date_maturity': rec.settlement_date,
                }))

            if total != 0:
                new_lines.append((0, 0, {
                    'name': 'Diferencial en ' + rec.name,
                    'debit': -1 * total if total < 0 else 0,
                    'credit': total if total > 0 else 0,
                    # 'account_id': rec.invoice_id[0].account_id.id,
                    'account_id': rec.adjustment_account_id.id,
                    'date_maturity': rec.settlement_date,
                }))

            move = self.env['account.move'].create({
                'line_ids': new_lines,
                'ref': rec.name,
                'date': rec.settlement_date,
                'journal_id': rec.journal_id.id,
            });

            index = 0
            invertidas = move.line_ids[::-1]
            for line in lines:
                par = line | invertidas[index]
                par.reconcile()
                index += 1

            move.post()
            self.write({'account_move_id': move.id})

        return True

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'payroll_state' in init_values and self.payroll_state == 'generated':
            return 'planilla_gt.mt_payroll_generated'  # Full external id
        elif 'payroll_state' in init_values and self.payroll_state == 'validated':
            return 'planilla_gt.mt_payroll_validated'  # Full external id
        elif 'payroll_state' in init_values and self.payroll_state == 'paid':
            return 'planilla_gt.mt_payroll_paid'  # Full external id
        return super(PlanillaGTPayroll, self)._track_subtype(init_values)

    @api.multi
    def cancelar(self):
        for rec in self:
            for l in rec.account_move_id.line_ids:
                if l.reconciled:
                    l.remove_move_reconcile()
            rec.account_move_id.button_cancel()
            rec.account_move_id.unlink()

        return True