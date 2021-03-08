# -*- encoding: utf-8 -*-

from odoo import api, models
import logging

_logger = logging.getLogger(__name__)
class ReporteCompras(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_compras'

    def lineas(self, datos):
        totales = {}

        totales['num_facturas'] = 0
        totales['compra'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['servicio'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['importacion'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['combustible'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['compras'] = {'bienes': 0}
        totales['total'] = 0
        totales['resumen'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['pequenio_contribuyente'] = 0

        journal_ids = [x for x in datos['diarios_id']]
        facturas = self.env['account.invoice'].search([
            ('state', 'in', ['open', 'paid', 'in_payment']),
            ('journal_id', 'in', journal_ids),
            ('date', '<=', datos['fecha_hasta']),
            ('date', '>=', datos['fecha_desde']),
        ], order='date_invoice, reference')

        lineas = []
        for f in facturas:
            totales['num_facturas'] += 1

            tipo_cambio = 1
            if f.currency_id.id != f.company_id.currency_id.id:
                total = 0
                for l in f.move_id.line_ids:
                    if l.account_id.id == f.account_id.id:
                        total += l.credit - l.debit
                tipo_cambio = abs(total / f.amount_total)

            tipo = 'FACT'
            if f.type != 'in_invoice':
                tipo = 'NC'
            if f.partner_id.pequenio_contribuyente:
                tipo += ' PEQ'

            linea = {
                'estado': f.state,
                'tipo': tipo,
                'fecha': f.date_invoice,
                #'serie': f.journal_id.code,
                'serie': f.provider_invoice_serial or '',
                # 'numero': f.reference or '',
                #'numero': f.move_name or '',
                'numero': f.provider_invoice_number or '',
                'proveedor': f.partner_id,
                'compra': 0,
                'compra_exento': 0,
                'servicio': 0,
                'servicio_exento': 0,
                'combustible': 0,
                'combustible_exento': 0,
                'importacion': 0,
                'importacion_exento': 0,
                'importacion_iva': 0,
                'compra_iva': 0,
                'servicio_iva': 0,
                'combustible_iva': 0,
                'base': 0,
                'iva': 0,
                'total': 0
            }
            is_compra = False
            is_service = False
            is_mix = False
            is_import = False
            is_gas = False
            flag_gas = False

            for linea_factura in f.invoice_line_ids:
                precio = (linea_factura.price_unit *
                          (1-(linea_factura.discount or 0.0)/100.0)) * tipo_cambio
                if tipo == 'NC':
                    precio = precio * -1

                tipo_linea = f.tipo_gasto

                if linea_factura.invoice_line_tax_ids:
                    for tax in linea_factura.invoice_line_tax_ids:
                        if tax.sat_tax_type == 'gas':
                            if is_compra or is_service:
                                is_mix = True
                                flag_gas = True
                            else:
                                is_gas = True
                                flag_gas = True
                    if flag_gas:
                        flag_gas = False

                if f.tipo_gasto == 'mixto':

                    if linea_factura.product_id.type == 'product' or linea_factura.product_id.type == 'consu':
                        tipo_linea = 'compra'
                    if linea_factura.product_id.type == 'service':
                        tipo_linea = 'servicio'
                    if is_gas:
                        tipo_linea = 'combustible'

                if f.tipo_gasto == 'combustible':
                    tipo_linea = 'combustible'

                r = linea_factura.invoice_line_tax_ids.compute_all(
                    precio, currency=f.currency_id, quantity=linea_factura.quantity, product=linea_factura.product_id, partner=f.partner_id)

                linea['base'] += r['base']
                totales[tipo_linea]['total'] += r['base']
                #totales[tipo_linea]['total'] += precio * linea_factura.quantity

                if len(linea_factura.invoice_line_tax_ids) > 0:
                    linea[tipo_linea] += r['base']
                    if tipo_linea == 'compra':
                        totales['compras']['bienes'] += r['base']
                    totales[tipo_linea]['neto'] += r['base']
                    totales['resumen']['neto'] += r['base']
                    for i in r['taxes']:
                        if i['id'] == datos['impuesto_id'][0]:
                            linea['iva'] += i['amount']
                            linea[tipo_linea+'_iva'] += i['amount']
                            totales[tipo_linea]['iva'] += i['amount']
                            totales['resumen']['iva'] += r['base']
                            totales[tipo_linea]['total'] += i['amount']
                        elif i['amount'] > 0:

                            if tipo_linea == 'combustible':
                                linea['compra_exento'] += i['amount']
                                totales[tipo_linea]['exento'] += i['amount']
                                totales[tipo_linea]['total'] += i['amount']
                            else:
                                linea[tipo_linea+'_exento'] += i['amount']
                                totales[tipo_linea]['exento'] += i['amount']
                                totales[tipo_linea]['total'] += i['amount']
                            totales['resumen']['exento'] += i['amount']

                else:
                    linea[tipo_linea+'_exento'] += r['base']
                    totales[tipo_linea]['exento'] += r['base']
                    totales['resumen']['exento'] += r['base']
                    totales[tipo_linea]['total'] += r['base']

                linea['total'] += precio * linea_factura.quantity

                totales['total'] += precio * linea_factura.quantity

            if f.partner_id.pequenio_contribuyente:
                totales['pequenio_contribuyente'] += linea['base']

            lineas.append(linea)

        return {'lineas': lineas, 'totales': totales}

    @api.model
    def _get_report_values(self, docids, data=None):
        return self.get_report_values(docids, data)

    @api.model
    def get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))

        diario = self.env['account.journal'].browse(data['form']['diarios_id'][0])

        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'lineas': self.lineas,
            'direccion': diario.direccion and diario.direccion.street,
        }

