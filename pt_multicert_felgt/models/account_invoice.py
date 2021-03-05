# -*- encoding: UTF-8 -*-
'''
1. Factura Cambiaria: Crear una factura normal y dar click en otra pestaña, seleccionar tipo de factura, seleccionar factura cambiaria y validar.
2. Factura cambiaria Exp: Crear una factura normal y dar click en otra pestaña, seleccionar tipo de factura, seleccionar factura cambiaria Exp. (El cliente no debe de tener nit solo debe de aparecer CF, dentro del cliente hay un campo que se llama Código comprador, hay que llenarlo)
3. Factura especial: Crear una factura normal y dar click en otra pestaña, seleccionar tipo de factura, seleccionar factura especial y llenar el monto de retención, luego validar.
4. Nota de abono: La nota de abono se crea desde Rectificativas de cliente (Facturas rectificativas), la creas y le das click en otra pestaña y le das click en un check box que dice Nota de abono y validas.
 5. Nota de crédito rebajando régimen face: Esta se crea una factura rectificativa a partir de una factura normal, antes de validar la factura rectificativa dar click en otra pestaña y click en el check box nota de crédito rebajando régimen anterior, luego validar.
'''
from odoo import api, models, sql_db, fields, _
import xml.etree.cElementTree as ET
from datetime import datetime, timedelta

import datetime as dt
from datetime import date, datetime, timedelta
import dateutil.parser
from dateutil.tz import gettz
from dateutil import parser
import json
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
import base64
import requests
from requests.auth import AuthBase
from json import loads
from random import randint
import re
import logging
from decimal import Decimal, ROUND_HALF_UP, ROUND_05UP, ROUND_UP, ROUND_HALF_EVEN

_logger = logging.getLogger(__name__)


# VALIDATIONS CONSTANTS
RAISE_VALIDATION_COMPANY_REGISTRY = "Por favor ingrese el registro fiscal de la empresa emisora."
RAISE_VALIDATION_COMPANY_EMAIL = "Por favor ingrese el correo electrónico de la empresa emisora."
RAISE_VALIDATION_COMPANY_VAT = "Por favor ingrese el número de NIT de la empresa emisora."
RAISE_VALIDATION_COMPANY_STREET = "Por favor ingrese la dirección de la empresa emisora."
RAISE_VALIDATION_COMPANY_FEL_COMPANY_CODE = "Por favor ingrese el código de escenario asociado al tipo de frase utilizado por el emisor."
RAISE_VALIDATION_COMPANY_FEL_COMPANY_TYPE = "Por favor ingrese tipo de frase la empresa emisora en base al tipo de documeto de DTE."
RAISE_VALIDATION_INVOICE_DATE_DUE = "Por favor ingrese la fecha de vencimiento de la factura."
RAISE_VALIDATION_INVOICE_PARTNER_NAME = "Por favor ingrese un nombre para el receptor de la factura."
RAISE_VALIDATION_UUID_CANCEL = "La factura debe tener un número de serie para poder ser cancelada."
RAISE_VALIDATION_PARTNER_BUYER_CODE = "Por favor ingresar el código de comprador del receptor de la factura."
RAISE_VALIDATION_COMPANY_CONSIGNATARY_CODE = "Por favor ingresar el código de consignatario de la empresa emisora."
RAISE_VALIDATION_COMPANY_EXPORTER_CODE = "Por favor ingresar el código de exportador de la empresa emisora."
RAISE_VALIDATION_SOURCE_UUID = "El documento no tiene un número de autorización asignada"


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    invoice_text_detail = fields.Char(string="Detalle de producto facturado")

    uuid = fields.Char("Número de Autorización", readonly=True,states={'draft': [('readonly', False)]})
    uuid_original = fields.Char("Número de Autorización original", readonly=True, states={'draft': [('readonly', False)]})
    serie = fields.Char("Serie", readonly=True, states={'draft': [('readonly', False)]})
    dte_number = fields.Char("Número DTE", readonly=True, states={'draft': [('readonly', False)]})
    dte_date = fields.Datetime("Fecha Autorización", readonly=True, states={'draft': [('readonly', False)]})
    cae = fields.Text("CAE", readonly=True, states={'draft': [('readonly', False)]})
    total_in_letters = fields.Text("Total Letras", readonly=True, states={'draft': [('readonly', False)]})
    fel_gt_withhold_amount = fields.Float(string="Retención", readonly=True, states={'draft': [('readonly', False)]})
    fel_gt_invoice_type = fields.Selection([
        ('normal', 'Factura Normal'),
        ('especial', 'Factura Especial'),
        ('cambiaria', 'Factura Cambiaria'),
        ('cambiaria_exp', 'Factura Cambiaria Exp.'),
        ('nota_debito', 'Nota de Débito'),
    ], string='Tipo de Factura', default='normal', readonly=True, states={'draft': [('readonly', False)]})
    old_tax_regime = fields.Boolean(string="Nota de crédito rebajando régimen antiguo", readonly=True, states={'draft': [('readonly', False)]}, default=False)
    credit_note = fields.Boolean(string="Nota de Abono", readonly=True, states={'draft': [('readonly', False)]}, default=False)

    sat_ref_id = fields.Char(string="AcuseReciboSAT")
    fel_link = fields.Char(string="Documento FEL", compute="get_link")
    source_debit_note_id = fields.Many2one('account.invoice', string="Documento origen")
    debit_note_id = fields.Many2one('account.invoice', string="Nota de débito")

    def action_debit_note(self):
        view_id = self.env.ref('account.invoice_form').id
        return {
            'name': _('Invoice'),
            # 'type': 'ir.ui.view',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.invoice',
            'view_id': view_id,
            'target': 'new',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_type': 'out_invoice',
                'default_source_debit_note_id': self.id,
                'default_fel_gt_invoice_type': 'nota_debito'
            }
        }

    def get_link(self):
        for rec in self:
            if rec.uuid is not False:
                rec.fel_link = "https://report.feel.com.gt/ingfacereport/ingfacereport_documento?uuid="+str(rec.uuid_original)
            else:
                rec.fel_link = ""

    @api.multi
    def action_invoice_open(self):
        fel_certifier = self.env.user.company_id.fel_certifier
        uuid = ""
        serie = ""
        dte_number = ""
        dte_date = ""
        sat_ref_id = ""
        # Updated to process the data returned by the DIGIFACT WS
        if fel_certifier == "digifact":
            if self.journal_id.is_fel == 'inactive':
                return super(AccountInvoice, self).action_invoice_open()
        if fel_certifier == "infile":
            if self.journal_id.infile_fel_active is False:
                return super(AccountInvoice, self).action_invoice_open()

        invoice_response = super(AccountInvoice, self).action_invoice_open()

        if self.type == "out_invoice":
            self.total_in_letters = str(number2text(self.amount_total))
            if self.fel_gt_invoice_type == 'normal':
                xml_data = self.set_data_for_invoice(fel_certifier)
                uuid, serie, dte_number, dte_date, sat_ref_id = self.send_data_api(xml_data)
                message = _("Facturación Electrónica: Serie %s  Número %s") % (serie, dte_number)
            if self.fel_gt_invoice_type == 'especial':
                xml_data = self.set_data_for_invoice_special(fel_certifier)
                uuid, serie, dte_number, dte_date, sat_ref_id = self.send_data_api(
                    xml_data)
                message = _("Facturación Especial Electrónica: Serie %s  Número %s") % (serie, dte_number)
            if self.fel_gt_invoice_type == 'cambiaria':
                xml_data = self.set_data_for_invoice_cambiaria(fel_certifier)
                uuid, serie, dte_number, dte_date, sat_ref_id = self.send_data_api(
                    xml_data)
                message = _("Facturación Electrónica Cambiaria: Serie %s  Número %s") % (serie, dte_number)
            if self.fel_gt_invoice_type == 'cambiaria_exp':
                xml_data = self.set_data_for_invoice_cambiaria_exp(fel_certifier)
                uuid, serie, dte_number, dte_date, sat_ref_id = self.send_data_api(
                    xml_data)
                message = _("Facturación Electrónica Cambiaria de Exportación: Serie %s  Número %s") % (serie, dte_number)
            
            if self.fel_gt_invoice_type == 'nota_debito':
                xml_data = self.set_data_for_invoice_nota_debito(fel_certifier)
                uuid, serie, dte_number, dte_date, sat_ref_id = self.send_data_api(
                    xml_data)
                message = _("Nota de Débito: Serie %s  Número %s") % (serie, dte_number)
            
            self.message_post(body=message)
            self.uuid = uuid
            self.uuid_original = uuid
            self.serie = serie
            self.dte_number = dte_number
            self.sat_ref_id = sat_ref_id
            dte_given_time = dateutil.parser.parse(dte_date)
            timezone_gt_adjust = timedelta(hours=6)
            gt_time = dte_given_time + timezone_gt_adjust
            dte_timedate_format = "%Y-%m-%d %H:%M:%S"
            gt_time = gt_time.strftime(dte_timedate_format)
            self.dte_date = gt_time

        if self.type == "out_refund" and self.refund_invoice_id:
            xml_data = self.set_data_for_invoice_credit(fel_certifier)
            uuid, serie, dte_number, dte_date, sat_ref_id = self.send_data_api(xml_data)
            message = _("Nota de Crédito: Serie %s  Número %s") % (serie, dte_number)
            self.message_post(body=message)
            self.uuid = uuid
            self.uuid_original = uuid
            self.serie = serie
            self.sat_ref_id = sat_ref_id
            self.dte_number = dte_number
            dte_given_time = dateutil.parser.parse(dte_date)
            timezone_gt_adjust = timedelta(hours=6)
            gt_time = dte_given_time + timezone_gt_adjust
            dte_timedate_format = "%Y-%m-%d %H:%M:%S"
            gt_time = gt_time.strftime(dte_timedate_format)
            self.dte_date = gt_time

        if self.type == "out_refund" and self.credit_note is True:
            xml_data = self.set_data_for_invoice_abono(fel_certifier)
            uuid, serie, dte_number, dte_date, sat_ref_id = self.send_data_api(xml_data)
            message = _("Nota de Abono: Serie %s  Número %s") % (serie, dte_number)
            self.message_post(body=message)
            self.uuid = uuid
            self.uuid_original = uuid
            self.serie = serie
            self.dte_number = dte_number
            self.sat_ref_id = sat_ref_id
            dte_given_time = dateutil.parser.parse(dte_date)
            timezone_gt_adjust = timedelta(hours=6)
            gt_time = dte_given_time + timezone_gt_adjust
            dte_timedate_format = "%Y-%m-%d %H:%M:%S"
            gt_time = gt_time.strftime(dte_timedate_format)
            self.dte_date = gt_time

        return invoice_response

    @api.multi
    def action_invoice_cancel(self):

        fel_certifier = self.env.user.company_id.fel_certifier

        # Updated to process the data returned by the DIGIFACT WS
        if fel_certifier == "digifact":
            if self.journal_id.is_fel == 'inactive':
                return super(AccountInvoice, self).action_invoice_cancel()

        if fel_certifier == "infile":
            if self.journal_id.infile_fel_active is False:
                return super(AccountInvoice, self).action_invoice_cancel()

        invoice_response = super(AccountInvoice, self).action_invoice_cancel()
        if self.type == "out_invoice":
            self.uuid_original = self.uuid
            xml_data = self.set_data_for_invoice_cancel(fel_certifier)
            uuid, serie, dte_number, dte_date, sat_ref_id = self.send_data_api(xml_data, 'cancel')
            message = _("Factura Cancelada: Serie %s  Número %s") % (serie, dte_number)
            self.message_post(body=message)
            self.uuid = uuid
            self.serie = serie
            self.dte_number = dte_number
            self.sat_ref_id = sat_ref_id

            dte_given_time = dateutil.parser.parse(dte_date)
            timezone_gt_adjust = timedelta(hours=6)
            gt_time = dte_given_time + timezone_gt_adjust
            dte_timedate_format = "%Y-%m-%d %H:%M:%S"
            gt_time = gt_time.strftime(dte_timedate_format)
            self.dte_date = gt_time

        if self.type == "out_refund" and self.uuid:
            self.uuid_original = self.uuid
            xml_data = self.set_data_for_invoice_cancel(fel_certifier)
            uuid, serie, dte_number, dte_date, sat_ref_id = self.send_data_api(xml_data, 'cancel')
            if self.credit_note is True:
                message = _("Nota de Abono Cancelada: Serie %s  Número %s") % (serie, dte_number)
            else:
                message = _("Nota de Crédito Cancelada: Serie %s  Número %s") % (serie, dte_number)
            # message = _("Nota de Crédito Cancelada: Serie %s  Número %s") % (serie, dte_number)
            self.message_post(body=message)
            self.uuid = uuid
            self.serie = serie
            self.dte_number = dte_number
            self.sat_ref_id = sat_ref_id
            dte_given_time = dateutil.parser.parse(dte_date)
            timezone_gt_adjust = timedelta(hours=6)
            gt_time = dte_given_time + timezone_gt_adjust
            dte_timedate_format = "%Y-%m-%d %H:%M:%S"
            gt_time = gt_time.strftime(dte_timedate_format)
            self.dte_date = gt_time

        return invoice_response

    # FACTURA NORMAL
    @api.multi
    def set_data_for_invoice(self, fel_certifier):

        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        vat = ""

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.company_id.street is False:
            raise UserError(RAISE_VALIDATION_COMPANY_STREET)

        if self.company_id.fel_company_code is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_CODE)

        if self.company_id.fel_company_type is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_TYPE)

        if self.date_due is False:
            raise UserError(RAISE_VALIDATION_INVOICE_DATE_DUE)

        if self.partner_id.name.strip() == "":
            raise UserError(RAISE_VALIDATION_INVOICE_PARTNER_NAME)

        xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")

        currency_code = "GTQ"
        if self.currency_id.name:
            currency_code = self.currency_id.name

        last_5_days = date.today() - timedelta(5)
        if last_5_days > self.date_invoice:
            raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.date_invoice:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.date_invoice.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]

        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="FACT")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento=self.company_id.infile_establishment_code, CorreoEmisor=self.company_id.email, NITEmisor=self.company_id.vat, NombreComercial=self.company_id.name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        street_address = self.company_id.street
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = street_address or self.company_id.street  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = self.company_id.zip or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = self.company_id.city or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = self.company_id.state_id.name or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            vat = "CF"

        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")

        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"

        # Frases
        xml_frases = ET.SubElement(xml_data_emision, "{" + xmlns + "}Frases")
        ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=self.company_id.fel_company_type, CodigoEscenario=self.company_id.fel_company_code)
        invoice_line = self.invoice_line_ids
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        invoice_counter = 0
        rounding_decimals = 2
        fel_taxes = {
            "IVA": 0,
            "PETROLEO": 0,
            "TURISMO HOSPEDAJE": 0,
            "TURISMO PASAJES": 0,
            "TIMBRE DE PRENSA": 0,
            "BOMBEROS": 0,
            "TASA MUNICIPAL": 0,
        }
        # LineasFactura
        for line in invoice_line:
            invoice_counter += 1

            BienOServicio = "B"
            if line.product_id.type == 'service':
                BienOServicio = "S"

            # Item
            # if line.product_id.name != line.name:
            # line_complete_name = line.product_id.name + " " + line.name
            # else:
            line_complete_name = line.name
            xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(invoice_counter))
            line_price = line.quantity * line.price_unit
            line_price = round(line_price, rounding_decimals)
            ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
            ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
            ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.name or " "
            ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(line.price_unit)
            ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
            ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line.price_unit))/100, rounding_decimals))

            if line.invoice_line_tax_ids:
                tax = "IVA"
            else:
                raise UserError(_("Las líneas de Factura deben de llevar impuesto (IVA)."))
            xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
            if line.invoice_line_tax_ids:
                for tax in line.invoice_line_tax_ids:
                    tax_name = tax.fel_tax
                    xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")

                    # Compute TAX
                    base = line.price_unit * line.quantity
                    if tax_name == "IVA":
                        price_tax = tax._compute_amount(base, line.price_unit, line.quantity, line.product_id, self.partner_id)
                    else:
                        price_tax = tax._compute_amount(line.price_subtotal, line.price_unit, line.quantity, line.product_id, self.partner_id)

                    ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = tax_name
                    ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
                    ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line.price_subtotal, rounding_decimals))
                    price_tax = round(price_tax, 3)
                    split_num = str(price_tax).split('.')
                    if int(split_num[1]) > 0:
                        decimal = str(split_num[1])
                        if len(decimal) > 2:
                            if int(decimal[2]) == 5:
                                price_tax += 0.001

                    decimal_set = '0.01'
                    price_tax = Decimal(price_tax).quantize(Decimal(decimal_set), rounding=ROUND_HALF_UP)
                    ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(price_tax)
                    fel_taxes[tax_name] += price_tax
            ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line.price_total, rounding_decimals))

        # Totales

        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        xml_total_impuestos = ET.SubElement(xml_totales, "{" + xmlns + "}TotalImpuestos")

        if fel_taxes['IVA'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='IVA', TotalMontoImpuesto=str(round(fel_taxes['IVA'], rounding_decimals)))
        if fel_taxes['PETROLEO'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='PETROLEO', TotalMontoImpuesto=str(round(fel_taxes['PETROLEO'], rounding_decimals)))
        if fel_taxes['TURISMO HOSPEDAJE'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO HOSPEDAJE', TotalMontoImpuesto=str(round(fel_taxes['TURISMO HOSPEDAJE'], rounding_decimals)))
        if fel_taxes['TURISMO PASAJES'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO PASAJES', TotalMontoImpuesto=str(round(fel_taxes['TURISMO PASAJES'], rounding_decimals)))
        if fel_taxes['TIMBRE DE PRENSA'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TIMBRE DE PRENSA', TotalMontoImpuesto=str(round(fel_taxes['TIMBRE DE PRENSA'], rounding_decimals)))
        if fel_taxes['BOMBEROS'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='BOMBEROS', TotalMontoImpuesto=str(round(fel_taxes['BOMBEROS'], rounding_decimals)))
        if fel_taxes['TASA MUNICIPAL'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TASA MUNICIPAL', TotalMontoImpuesto=str(round(fel_taxes['TASA MUNICIPAL'], rounding_decimals)))
        grand_total = Decimal(float(self.amount_total))
        grand_total = Decimal(grand_total).quantize(Decimal('0.01'), ROUND_HALF_UP)
        ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(grand_total)

        # Adenda
        xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
        # ET.SubElement(ade, "NITEXTRANJERO").text = "111111"
        # ET.SubElement(xml_adenda, "DETALLE_PRODUCTO").text = self.invoice_text_detail
        # ET.SubElement(xml_adenda, "CERTIFICADO").text = "PRODUCTO CERTIFICADO GLOBALGAP, GGN 4049928186782"
        date_due = self.date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')

        date_due_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_due_format)
        ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method="xml")
        search_string = "ns0"
        string_remplace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, string_remplace)
        xml_content = xml_content.encode('utf_8')

        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if fel_certifier == 'infile':
            xml_content = base64.b64encode(xml_content)

        return xml_content

    @api.multi
    def set_data_for_invoice_special(self, fel_certifier):
        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        schemaLocation_complementos = "http://www.sat.gob.gt/face2/ComplementoFacturaEspecial/0.1.0 GT_Complemento_Fac_Especial-0.1.0.xsd"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        cno = "http://www.sat.gob.gt/face2/ComplementoFacturaEspecial/0.1.0"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.date_due is False:
            raise UserError(RAISE_VALIDATION_INVOICE_DATE_DUE)

        if self.partner_id.name.strip() == "":
            raise UserError(RAISE_VALIDATION_INVOICE_PARTNER_NAME)

        # ISR CALCULATIONS
        # TODO: Replicate calculation in invoice calculate amount
        invoice_base_amount = round(self.amount_untaxed - self.fel_gt_withhold_amount, 2)
        isr_withold = 0
        if self.amount_total < 30000:
            isr_withold = invoice_base_amount * 0.05
        if self.amount_total > 30000:
            isr_withold = 1500
            exceed_amount = invoice_base_amount - 30000
            isr_withold = (exceed_amount * 0.07) + isr_withold
        isr_withold = round(isr_withold, 2)
        self.fel_gt_withhold_amount = isr_withold

        xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        ET.register_namespace('cfe', cno)
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")

        last_5_days = date.today() - timedelta(5)
        if last_5_days > self.date_invoice:
            raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.date_invoice:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.date_invoice.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]

        currency_code = "GTQ"
        if self.currency_id.name:
            currency_code = self.currency_id.name
        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="FESP")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento="1", CorreoEmisor=self.company_id.email, NITEmisor=self.company_id.vat, NombreComercial=self.company_id.name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        street_address = self.company_id.street
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = street_address or self.company_id.street  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = self.company_id.zip or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = self.company_id.city or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = self.company_id.state_id.name or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            # vat = "CF"
            vat = self.company_id.vat

        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"

        invoice_line = self.invoice_line_ids
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        tax_in_ex = 1
        invoice_counter = 0
        # LineasFactura
        for line in invoice_line:
            invoice_counter += 1
            p_type = 0
            BienOServicio = "B"
            if line.product_id.type == 'service':
                p_type = 1
                BienOServicio = "S"
            for tax in line.invoice_line_tax_ids:
                if tax.price_include:
                    tax_in_ex = 0

            # Item
            xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(invoice_counter))
            line_price = line.quantity * line.price_unit
            line_price = round(line_price, 2)
            ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
            ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
            ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.name or " "
            ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(line.price_unit)
            ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
            ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line.price_unit))/100, 2))

            if line.invoice_line_tax_ids:
                tax = "IVA"
            else:
                raise UserError(_("Las líneas de Factura deben de llevar impuesto (IVA)."))

            xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
            xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")
            price_tax = line.price_total - line.price_subtotal
            ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = tax
            ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
            ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line.price_subtotal, 2))
            ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(round(price_tax, 2))
            ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line.price_total, 2))
        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        xml_total_impuestos = ET.SubElement(xml_totales, "{" + xmlns + "}TotalImpuestos")
        xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto="IVA", TotalMontoImpuesto=str(round(self.amount_tax, 2)))
        ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(self.amount_total, 2))

        xml_complementos = ET.SubElement(xml_data_emision, "{" + xmlns + "}Complementos")
        xml_complemento = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento="FacturaEspecial", URIComplemento="FESP", attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos})
        xml_retenciones = ET.SubElement(xml_complemento, "{" + cno + "}RetencionesFacturaEspecial", Version="1")
        ET.SubElement(xml_retenciones, "{" + cno + "}RetencionISR").text = str(self.fel_gt_withhold_amount)
        ET.SubElement(xml_retenciones, "{" + cno + "}RetencionIVA").text = str(round(self.amount_tax, 2))
        ET.SubElement(xml_retenciones, "{" + cno + "}TotalMenosRetenciones").text = str(round(self.amount_untaxed - self.fel_gt_withhold_amount, 2))
        # Adenda
        xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
        ET.SubElement(xml_adenda, "CAJERO").text = "1"
        ET.SubElement(xml_adenda, "VENDEDOR").text = "1"
        ET.SubElement(xml_adenda, "Subtotal").text = str(round(self.amount_untaxed, 2))
        ET.SubElement(xml_adenda, "Fuente").text = self.user_id.name
        date_due = self.date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        date_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_format)
        ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        search_replace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, search_replace)
        xml_content = xml_content.encode('utf_8')

        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if fel_certifier == 'infile':
            xml_content = base64.b64encode(xml_content)

        return xml_content

    @api.multi
    def set_data_for_invoice_abono(self, fel_certifier):
        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        version = "0.4"
        ns = "{xsi}"
        DTE = "dte"
        cno = "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.company_id.street is False:
            raise UserError(RAISE_VALIDATION_COMPANY_STREET)

        if self.date_due is False:
            raise UserError(RAISE_VALIDATION_INVOICE_DATE_DUE)

        if self.partner_id.name.strip() == "":
            raise UserError(RAISE_VALIDATION_INVOICE_PARTNER_NAME)

        xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")
        # fecha_emision = dt.datetime.now(gettz("America/Guatemala")).isoformat()   #dt.datetime.now().isoformat()

        last_5_days = date.today() - timedelta(5)
        if last_5_days > self.date_invoice:
            raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.date_invoice:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.date_invoice.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]

        currency_code = "GTQ"
        if self.currency_id.name:
            currency_code = self.currency_id.name
        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="NABN")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento="1", CorreoEmisor=self.company_id.email, NITEmisor=self.company_id.vat, NombreComercial=self.company_id.name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        street_address = self.company_id.street
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = street_address or self.company_id.street  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = self.company_id.zip or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = self.company_id.city or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = self.company_id.state_id.name or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            vat = "CF"

        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"

        invoice_line = self.invoice_line_ids
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        tax_in_ex = 1
        cnt = 0
        # LineasFactura
        for line in invoice_line:
            cnt += 1
            p_type = 0
            BienOServicio = "B"
            if line.product_id.type == 'service':
                p_type = 1
                BienOServicio = "S"
            for tax in line.invoice_line_tax_ids:
                if tax.price_include:
                    tax_in_ex = 0

            # Item
            xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(cnt))
            line_price = line.quantity * line.price_unit
            line_price = round(line_price, 2)
            ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
            ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
            ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.name or " "
            ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(line.price_unit)
            ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
            ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line.price_unit))/100, 2))
            ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line.price_total, 2))
        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(self.amount_total, 2))

        # Adenda
        xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
        ET.SubElement(xml_adenda, "CAJERO").text = "1"
        ET.SubElement(xml_adenda, "VENDEDOR").text = "1"
        ET.SubElement(xml_adenda, "Subtotal").text = str(round(self.amount_untaxed, 2))
        ET.SubElement(xml_adenda, "Fuente").text = self.user_id.name
        date_due = self.date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        date_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_format)
        ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        search_replace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, search_replace)
        xml_content = xml_content.encode('utf_8')

        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if fel_certifier == 'infile':
            xml_content = base64.b64encode(xml_content)

        return xml_content

    @api.multi
    def set_data_for_invoice_cancel(self, fel_certifier):
        xmlns = "http://www.sat.gob.gt/dte/fel/0.1.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.1.0"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        cno = "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.uuid is False:
            raise UserError(RAISE_VALIDATION_UUID_CANCEL)

        xml_root = ET.Element("{" + xmlns + "}GTAnulacionDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}AnulacionDTE", ID="DatosCertificados")
        date_invoice = self.date_invoice or datetime.now()

        # if self.dte_date is not False:
        #    date_invoice = datetime.strptime(date_invoice, '%Y-%m-%d %H:%M:%S')

        racion_de_6h = timedelta(hours=6)
        date_invoice = date_invoice - racion_de_6h
        invoice_date_format = "%Y-%m-%dT%H:%M:%S.%f"
        date_invoice = date_invoice.strftime(invoice_date_format)[:-3]

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            vat = "CF"
        fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        dge = ET.SubElement(xml_dte, "{" + xmlns + "}DatosGenerales", FechaEmisionDocumentoAnular=date_invoice, FechaHoraAnulacion=fecha_emision, ID="DatosAnulacion", IDReceptor=vat, MotivoAnulacion="Anulación", NITEmisor=self.company_id.vat, NumeroDocumentoAAnular=str(self.uuid))

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        attribute_replace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, attribute_replace)
        xml_content = xml_content.encode('utf_8')
        date_due = ""
        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if fel_certifier == 'infile':
            xml_content = base64.b64encode(xml_content)

        return xml_content

    @api.multi
    def set_data_for_invoice_credit(self, fel_certifier):
        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        schemaLocation_complementos = "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0 GT_Complemento_Referencia_Nota-0.1.0.xsd"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        complemento_xmlns = "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        # if self.uuid is False:
        #    raise UserError(RAISE_VALIDATION_UUID_CANCEL)

        xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1")
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")
        # fecha_emision = dt.datetime.now(gettz("America/Guatemala")).isoformat()   #dt.datetime.now().isoformat()
        last_5_days = date.today() - timedelta(5)
        if last_5_days > self.date_invoice:
            raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.date_invoice:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.date_invoice.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]

        currency_code = "GTQ"
        if self.currency_id.name:
            currency_code = self.currency_id.name
        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="NCRE")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento="1", CorreoEmisor=self.company_id.email, NITEmisor=self.company_id.vat, NombreComercial=self.company_id.name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        street_address = self.company_id.street
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = street_address or self.company_id.street  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = self.company_id.zip or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = self.company_id.city or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = self.company_id.state_id.name or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            vat = "CF"

        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"

        invoice_line = self.invoice_line_ids
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        tax_in_ex = 1
        cnt = 0
        rounding_decimals = 2
        fel_taxes = {
            "IVA": 0,
            "PETROLEO": 0,
            "TURISMO HOSPEDAJE": 0,
            "TURISMO PASAJES": 0,
            "TIMBRE DE PRENSA": 0,
            "BOMBEROS": 0,
            "TASA MUNICIPAL": 0,
        }
        # LineasFactura
        for line in invoice_line:
            cnt += 1
            p_type = 0
            BienOServicio = "B"
            if line.product_id.type == 'service':
                p_type = 1
                BienOServicio = "S"
            for tax in line.invoice_line_tax_ids:
                if tax.price_include:
                    tax_in_ex = 0

            # Item
            xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(cnt))

            line_price = line.quantity * line.price_unit
            line_price = round(line_price, 2)

            ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
            ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
            ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.name or " "
            ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(line.price_unit)
            ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
            ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line.price_unit))/100, 2))

            xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
            if line.invoice_line_tax_ids:
                for tax in line.invoice_line_tax_ids:
                    tax_name = tax.fel_tax
                    xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")

                    # Compute TAX
                    base = line.price_unit * line.quantity
                    if tax_name == "IVA":
                        price_tax = tax._compute_amount(base, line.price_unit, line.quantity, line.product_id, self.partner_id)
                    else:
                        price_tax = tax._compute_amount(line.price_subtotal, line.price_unit, line.quantity, line.product_id, self.partner_id)

                    ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = tax_name
                    ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
                    ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line.price_subtotal, rounding_decimals))
                    price_tax = round(price_tax, 3)
                    split_num = str(price_tax).split('.')
                    if int(split_num[1]) > 0:
                        decimal = str(split_num[1])
                        if len(decimal) > 2:
                            if int(decimal[2]) == 5:
                                price_tax += 0.001

                    decimal_set = '0.01'
                    price_tax = Decimal(price_tax).quantize(Decimal(decimal_set), rounding=ROUND_HALF_UP)

                    ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(price_tax)
                    fel_taxes[tax_name] += price_tax
            ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line.price_total, rounding_decimals))

        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        xml_total_impuestos = ET.SubElement(xml_totales, "{" + xmlns + "}TotalImpuestos")
        if fel_taxes['IVA'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='IVA', TotalMontoImpuesto=str(round(fel_taxes['IVA'], rounding_decimals)))
        if fel_taxes['PETROLEO'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='PETROLEO', TotalMontoImpuesto=str(round(fel_taxes['PETROLEO'], rounding_decimals)))
        if fel_taxes['TURISMO HOSPEDAJE'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO HOSPEDAJE', TotalMontoImpuesto=str(round(fel_taxes['TURISMO HOSPEDAJE'], rounding_decimals)))
        if fel_taxes['TURISMO PASAJES'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO PASAJES', TotalMontoImpuesto=str(round(fel_taxes['TURISMO PASAJES'], rounding_decimals)))
        if fel_taxes['TIMBRE DE PRENSA'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TIMBRE DE PRENSA', TotalMontoImpuesto=str(round(fel_taxes['TIMBRE DE PRENSA'], rounding_decimals)))
        if fel_taxes['BOMBEROS'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='BOMBEROS', TotalMontoImpuesto=str(round(fel_taxes['BOMBEROS'], rounding_decimals)))
        if fel_taxes['TASA MUNICIPAL'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TASA MUNICIPAL', TotalMontoImpuesto=str(round(fel_taxes['TASA MUNICIPAL'], rounding_decimals)))

        grand_total = Decimal(float(self.amount_total))
        grand_total = Decimal(grand_total).quantize(Decimal('0.01'), ROUND_HALF_UP)
        ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(grand_total)

        # Complementos
        dte_date = self.refund_invoice_id.date_invoice
        if not dte_date:
            raise UserError('La factura no posee una fecha de DTE, si desea realizar cambios sobre la misma desactive la facturación electrónica en el diario asociado a la misma.')
        # dte_date = datetime.strptime(dte_date, '%Y-%m-%d %H:%M:%S')
        racion_de_6h = timedelta(hours=6)
        dte_date = dte_date - racion_de_6h
        date_format = "%Y-%m-%d"
        dte_date = dte_date.strftime(date_format)
        xml_complementos = ET.SubElement(xml_data_emision, "{" + xmlns + "}Complementos")
        xml_complemento = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento=self.name, URIComplemento='http://www.sat.gob.gt/fel/notas.xsd', attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos})
        ET.register_namespace('cno', complemento_xmlns)
        if self.old_tax_regime is False:
            ET.SubElement(xml_complemento, "{" + complemento_xmlns + "}ReferenciasNota", FechaEmisionDocumentoOrigen=dte_date, MotivoAjuste=self.name, NumeroAutorizacionDocumentoOrigen=str(self.refund_invoice_id.uuid), NumeroDocumentoOrigen=str(self.refund_invoice_id.dte_number), SerieDocumentoOrigen=str(self.refund_invoice_id.serie), Version="0.1")
        if self.old_tax_regime is True:
            ET.SubElement(xml_complemento, "{" + complemento_xmlns + "}ReferenciasNota", FechaEmisionDocumentoOrigen=dte_date, RegimenAntiguo="Antiguo", MotivoAjuste=self.name, NumeroAutorizacionDocumentoOrigen=str(self.refund_invoice_id.uuid), NumeroDocumentoOrigen=str(self.refund_invoice_id.dte_number), SerieDocumentoOrigen=str(self.refund_invoice_id.serie), Version="0.1")

        # Adenda
        xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
        ET.SubElement(xml_adenda, "CAJERO").text = "1"
        ET.SubElement(xml_adenda, "VENDEDOR").text = "1"
        ET.SubElement(xml_adenda, "Subtotal").text = str(round(self.amount_untaxed, 2))
        ET.SubElement(xml_adenda, "Fuente").text = self.user_id.name
        ET.SubElement(xml_adenda, "NIT_EXTRANJERO").text = self.partner_id.buyer_code
        date_due = self.date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        date_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_format)
        ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        search_replace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, search_replace)
        xml_content = xml_content.encode('utf_8')

        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)
        _logger.info('FEL CONTENT ' + str(xml_content))

        if fel_certifier == 'infile':
            xml_content = base64.b64encode(xml_content)

        return xml_content

    @api.multi
    def set_data_for_invoice_cambiaria_exp(self, fel_certifier):

        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        schemaLocation_complementos = "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0 GT_Complemento_Cambiaria-0.1.0.xsd"
        schemaLocation_complementos_exportaciones = "http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0 GT_Complemento_Cambiaria-0.1.0.xsd"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.company_id.street is False:
            raise UserError(RAISE_VALIDATION_COMPANY_STREET)

        if self.company_id.fel_company_code is False:

            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_CODE)

        if self.company_id.fel_company_type is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_TYPE)

        if self.partner_id.buyer_code is False:
            raise UserError(RAISE_VALIDATION_PARTNER_BUYER_CODE)

        if self.company_id.consignatary_code is False:
            raise UserError(RAISE_VALIDATION_COMPANY_CONSIGNATARY_CODE)

        if self.company_id.exporter_code is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EXPORTER_CODE)

        cno = "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0"
        cna = "http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0"

        xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        ET.register_namespace('cex', cna)
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")

        last_5_days = date.today() - timedelta(5)
        if last_5_days > self.date_invoice:
            raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.date_invoice:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.date_invoice.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]

        currency_code = "GTQ"
        if self.currency_id.name:
            currency_code = self.currency_id.name
        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code, Exp="SI", FechaHoraEmision=fecha_emision, Tipo="FCAM")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento="1", CorreoEmisor=self.company_id.email, NITEmisor=self.company_id.vat, NombreComercial=self.company_id.name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        street_address = self.company_id.street
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = street_address or self.company_id.street  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = self.company_id.zip or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = self.company_id.city or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = self.company_id.state_id.name or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            vat = "CF"

        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"

        # Frases
        xml_frases = ET.SubElement(xml_data_emision, "{" + xmlns + "}Frases")
        ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=self.company_id.fel_company_type, CodigoEscenario=self.company_id.fel_company_code)
        ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase="4", CodigoEscenario="1")

        invoice_line = self.invoice_line_ids
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        tax_in_ex = 1
        invoice_counter = 0
        rounding_decimals = 2
        fel_taxes = {
            "IVA": 0,
            "PETROLEO": 0,
            "TURISMO HOSPEDAJE": 0,
            "TURISMO PASAJES": 0,
            "TIMBRE DE PRENSA": 0,
            "BOMBEROS": 0,
            "TASA MUNICIPAL": 0,
        }
        # LineasFactura
        for line in invoice_line:
            invoice_counter += 1
            p_type = 0
            BienOServicio = "B"
            if line.product_id.type == 'service':
                p_type = 1
                BienOServicio = "S"
            for tax in line.invoice_line_tax_ids:
                if tax.price_include:
                    tax_in_ex = 0

            # Item
            xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(invoice_counter))
            line_price = line.quantity * line.price_unit
            line_price = round(line_price, 2)
            ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
            ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
            ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.name or " "
            ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(line.price_unit)
            ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
            ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line.price_unit))/100, 2))

            xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
            if line.invoice_line_tax_ids:
                for tax in line.invoice_line_tax_ids:
                    tax_name = tax.fel_tax
                    xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")

                    # Compute TAX
                    base = line.price_unit * line.quantity
                    if tax_name == "IVA":
                        price_tax = tax._compute_amount(base, line.price_unit, line.quantity, line.product_id, self.partner_id)
                    else:
                        price_tax = tax._compute_amount(line.price_subtotal, line.price_unit, line.quantity, line.product_id, self.partner_id)

                    ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = tax_name
                    ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
                    ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line.price_subtotal, rounding_decimals))
                    price_tax = round(price_tax, 3)
                    split_num = str(price_tax).split('.')
                    if int(split_num[1]) > 0:
                        decimal = str(split_num[1])
                        if len(decimal) > 2:
                            if int(decimal[2]) == 5:
                                price_tax += 0.001

                    decimal_set = '0.01'
                    price_tax = Decimal(price_tax).quantize(Decimal(decimal_set), rounding=ROUND_HALF_UP)
                    ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(price_tax)
                    fel_taxes[tax_name] += price_tax
            ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line.price_total, rounding_decimals))

        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        xml_total_impuestos = ET.SubElement(xml_totales, "{" + xmlns + "}TotalImpuestos")
        if fel_taxes['IVA'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='IVA', TotalMontoImpuesto=str(round(fel_taxes['IVA'], rounding_decimals)))
        if fel_taxes['PETROLEO'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='PETROLEO', TotalMontoImpuesto=str(round(fel_taxes['PETROLEO'], rounding_decimals)))
        if fel_taxes['TURISMO HOSPEDAJE'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO HOSPEDAJE', TotalMontoImpuesto=str(round(fel_taxes['TURISMO HOSPEDAJE'], rounding_decimals)))
        if fel_taxes['TURISMO PASAJES'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO PASAJES', TotalMontoImpuesto=str(round(fel_taxes['TURISMO PASAJES'], rounding_decimals)))
        if fel_taxes['TIMBRE DE PRENSA'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TIMBRE DE PRENSA', TotalMontoImpuesto=str(round(fel_taxes['TIMBRE DE PRENSA'], rounding_decimals)))
        if fel_taxes['BOMBEROS'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='BOMBEROS', TotalMontoImpuesto=str(round(fel_taxes['BOMBEROS'], rounding_decimals)))
        if fel_taxes['TASA MUNICIPAL'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TASA MUNICIPAL', TotalMontoImpuesto=str(round(fel_taxes['TASA MUNICIPAL'], rounding_decimals)))
        grand_total = Decimal(float(self.amount_total))
        grand_total = Decimal(grand_total).quantize(Decimal('0.01'), ROUND_HALF_UP)
        ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(grand_total)

        date_due = self.date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        formato2 = "%Y-%m-%d"
        date_due = date_due.strftime(formato2)

        xml_complementos = ET.SubElement(xml_data_emision, "{" + xmlns + "}Complementos")
        xml_complemento = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento="AbonosFacturaCambiaria", URIComplemento=cno, attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos})
        xml_retenciones = ET.SubElement(xml_complemento, "{" + cno + "}AbonosFacturaCambiaria", Version="1")
        xml_abono = ET.SubElement(xml_retenciones, "{" + cno + "}Abono")
        ET.SubElement(xml_abono, "{" + cno + "}NumeroAbono").text = "1"
        ET.SubElement(xml_abono, "{" + cno + "}FechaVencimiento").text = date_due
        ET.SubElement(xml_abono, "{" + cno + "}MontoAbono").text = str(round(self.amount_total, 2))

        xml_complemento_secondary = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento="AbonosFacturaCambiariaExp", URIComplemento=cna, attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos})
        xml_retenciones_secondary = ET.SubElement(xml_complemento_secondary, "{" + cna + "}Exportacion", Version="1", attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos_exportaciones})
        ET.SubElement(xml_retenciones_secondary, "{" + cna + "}NombreConsignatarioODestinatario").text = self.company_id.name
        ET.SubElement(xml_retenciones_secondary, "{" + cna + "}DireccionConsignatarioODestinatario").text = self.company_id.street
        ET.SubElement(xml_retenciones_secondary, "{" + cna + "}CodigoConsignatarioODestinatario").text = self.company_id.consignatary_code
        ET.SubElement(xml_retenciones_secondary, "{" + cna + "}NombreComprador").text = self.partner_id.name
        ET.SubElement(xml_retenciones_secondary, "{" + cna + "}DireccionComprador").text = self.partner_id.street
        ET.SubElement(xml_retenciones_secondary, "{" + cna + "}CodigoComprador").text = self.partner_id.buyer_code
        ET.SubElement(xml_retenciones_secondary, "{" + cna + "}OtraReferencia").text = self.partner_id.ref or "Otra Referencia"
        ET.SubElement(xml_retenciones_secondary, "{" + cna + "}INCOTERM").text = self.incoterm_id.code or "EXW"
        ET.SubElement(xml_retenciones_secondary, "{" + cna + "}NombreExportador").text = self.company_id.name
        ET.SubElement(xml_retenciones_secondary, "{" + cna + "}CodigoExportador").text = self.company_id.exporter_code

        # Adenda
        xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
        ET.SubElement(xml_adenda, "NIT_EXTRANJERO").text = self.partner_id.buyer_code
        # ET.SubElement(xml_adenda, "CAJERO").text = "1"
        # ET.SubElement(xml_adenda, "VENDEDOR").text = "1"
        # ET.SubElement(xml_adenda, "Subtotal").text = str(round(self.amount_untaxed, 2))
        # ET.SubElement(xml_adenda, "Fuente").text = self.user_id.name
        date_due = self.date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        date_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_format)
        # ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        string_remplace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, string_remplace)
        xml_content = xml_content.encode('utf_8')

        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if fel_certifier == 'infile':
            xml_content = base64.b64encode(xml_content)

        return xml_content

    # VALIDATED
    @api.multi
    def set_data_for_invoice_cambiaria(self, fel_certifier):

        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        schemaLocation_complementos = "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0 GT_Complemento_Cambiaria-0.1.0.xsd"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        cno = "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.company_id.street is False:
            raise UserError(RAISE_VALIDATION_COMPANY_STREET)

        if self.company_id.fel_company_code is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_CODE)

        if self.company_id.fel_company_type is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_TYPE)

        if self.date_due is False:
            raise UserError(RAISE_VALIDATION_INVOICE_DATE_DUE)

        if self.partner_id.name.strip() == "":
            raise UserError(RAISE_VALIDATION_INVOICE_PARTNER_NAME)

        xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        ET.register_namespace('cfc', cno)
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")

        last_5_days = date.today() - timedelta(5)
        if last_5_days > self.date_invoice:
            raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.date_invoice:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.date_invoice.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]

        currency_code = "GTQ"
        if self.currency_id.name:
            currency_code = self.currency_id.name

        last_5_days = date.today() - timedelta(5)
        if last_5_days > self.date_invoice:
            raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.date_invoice:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.date_invoice.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]

        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="FCAM")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento="1", CorreoEmisor=self.company_id.email, NITEmisor=self.company_id.vat, NombreComercial=self.company_id.name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        street_address = self.company_id.street
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = street_address or self.company_id.street  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = self.company_id.zip or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = self.company_id.city or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = self.company_id.state_id.name or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            vat = "CF"

        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"

        # Frases
        xml_frases = ET.SubElement(xml_data_emision, "{" + xmlns + "}Frases")
        ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=self.company_id.fel_company_type, CodigoEscenario=self.company_id.fel_company_code)

        invoice_line = self.invoice_line_ids
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        tax_in_ex = 1
        invoice_counter = 0
        rounding_decimals = 2
        fel_taxes = {
            "IVA": 0,
            "PETROLEO": 0,
            "TURISMO HOSPEDAJE": 0,
            "TURISMO PASAJES": 0,
            "TIMBRE DE PRENSA": 0,
            "BOMBEROS": 0,
            "TASA MUNICIPAL": 0,
        }
        # LineasFactura
        for line in invoice_line:
            invoice_counter += 1
            p_type = 0
            BienOServicio = "B"
            if line.product_id.type == 'service':
                p_type = 1
                BienOServicio = "S"
            for tax in line.invoice_line_tax_ids:
                if tax.price_include:
                    tax_in_ex = 0

            # Item
            xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(invoice_counter))
            line_price = line.quantity * line.price_unit
            line_price = round(line_price, 2)
            ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
            ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
            ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.name or " "
            ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(line.price_unit)
            ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
            ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line.price_unit))/100, 2))

            if line.invoice_line_tax_ids:
                tax = "IVA"
            else:
                raise UserError(_("Las líneas de Factura deben de llevar impuesto (IVA)."))

            xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
            if line.invoice_line_tax_ids:
                for tax in line.invoice_line_tax_ids:
                    tax_name = tax.fel_tax
                    xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")

                    # Compute TAX
                    base = line.price_unit * line.quantity
                    if tax_name == "IVA":
                        price_tax = tax._compute_amount(base, line.price_unit, line.quantity, line.product_id, self.partner_id)
                    else:
                        price_tax = tax._compute_amount(line.price_subtotal, line.price_unit, line.quantity, line.product_id, self.partner_id)

                    ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = tax_name
                    ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
                    ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line.price_subtotal, rounding_decimals))
                    price_tax = round(price_tax, 3)
                    split_num = str(price_tax).split('.')
                    if int(split_num[1]) > 0:
                        decimal = str(split_num[1])
                        if len(decimal) > 2:
                            if int(decimal[2]) == 5:
                                price_tax += 0.001

                    decimal_set = '0.01'
                    price_tax = Decimal(price_tax).quantize(Decimal(decimal_set), rounding=ROUND_HALF_UP)

                    ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(price_tax)
                    fel_taxes[tax_name] += price_tax
            ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line.price_total, 2))
        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        xml_total_impuestos = ET.SubElement(xml_totales, "{" + xmlns + "}TotalImpuestos")
        if fel_taxes['IVA'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='IVA', TotalMontoImpuesto=str(round(fel_taxes['IVA'], rounding_decimals)))
        if fel_taxes['PETROLEO'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='PETROLEO', TotalMontoImpuesto=str(round(fel_taxes['PETROLEO'], rounding_decimals)))
        if fel_taxes['TURISMO HOSPEDAJE'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO HOSPEDAJE', TotalMontoImpuesto=str(round(fel_taxes['TURISMO HOSPEDAJE'], rounding_decimals)))
        if fel_taxes['TURISMO PASAJES'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO PASAJES', TotalMontoImpuesto=str(round(fel_taxes['TURISMO PASAJES'], rounding_decimals)))
        if fel_taxes['TIMBRE DE PRENSA'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TIMBRE DE PRENSA', TotalMontoImpuesto=str(round(fel_taxes['TIMBRE DE PRENSA'], rounding_decimals)))
        if fel_taxes['BOMBEROS'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='BOMBEROS', TotalMontoImpuesto=str(round(fel_taxes['BOMBEROS'], rounding_decimals)))
        if fel_taxes['TASA MUNICIPAL'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TASA MUNICIPAL', TotalMontoImpuesto=str(round(fel_taxes['TASA MUNICIPAL'], rounding_decimals)))
        grand_total = Decimal(float(self.amount_total))
        grand_total = Decimal(grand_total).quantize(Decimal('0.01'), ROUND_HALF_UP)
        ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(grand_total)

        # Complementos

        date_due = self.date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        formato2 = "%Y-%m-%d"
        date_due = date_due.strftime(formato2)
        xml_complementos = ET.SubElement(xml_data_emision, "{" + xmlns + "}Complementos")
        xml_complemento = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento="AbonosFacturaCambiaria", URIComplemento="FCAM", attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos})
        xml_retenciones = ET.SubElement(xml_complemento, "{" + cno + "}AbonosFacturaCambiaria", Version="1")
        xml_abono = ET.SubElement(xml_retenciones, "{" + cno + "}Abono")
        ET.SubElement(xml_abono, "{" + cno + "}NumeroAbono").text = "1"
        ET.SubElement(xml_abono, "{" + cno + "}FechaVencimiento").text = date_due
        ET.SubElement(xml_abono, "{" + cno + "}MontoAbono").text = str(round(self.amount_total, 2))
        # Adenda
        xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
        ET.SubElement(xml_adenda, "CAJERO").text = "1"
        ET.SubElement(xml_adenda, "VENDEDOR").text = "1"
        ET.SubElement(xml_adenda, "Subtotal").text = str(round(self.amount_untaxed, 2))
        ET.SubElement(xml_adenda, "Fuente").text = self.user_id.name
        date_due = self.date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        date_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_format)
        ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        string_remplace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, string_remplace)
        xml_content = xml_content.encode('utf_8')

        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if fel_certifier == 'infile':
            xml_content = base64.b64encode(xml_content)

        return xml_content
    
    # NOTA DEBITO
    @api.multi
    def set_data_for_invoice_nota_debito(self, fel_certifier):

        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        schemaLocation_complementos = "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0 GT_Complemento_Referencia_Nota-0.1.0.xsd"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        vat = ""
        complemento_xmlns = "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.company_id.street is False:
            raise UserError(RAISE_VALIDATION_COMPANY_STREET)

        if self.company_id.fel_company_code is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_CODE)

        if self.company_id.fel_company_type is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_TYPE)

        if self.date_due is False:
            raise UserError(RAISE_VALIDATION_INVOICE_DATE_DUE)

        if self.partner_id.name.strip() == "":
            raise UserError(RAISE_VALIDATION_INVOICE_PARTNER_NAME)

        if self.source_debit_note_id is False:
            raise UserError(RAISE_VALIDATION_SOURCE_UUID)

        xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")

        currency_code = "GTQ"
        if self.currency_id.name:
            currency_code = self.currency_id.name

        last_5_days = date.today() - timedelta(5)
        if last_5_days > self.date_invoice:
            raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.date_invoice:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.date_invoice.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]

        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="NDEB")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento="1", CorreoEmisor=self.company_id.email, NITEmisor=self.company_id.vat, NombreComercial=self.company_id.name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        street_address = self.company_id.street
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = street_address or self.company_id.street  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = self.company_id.zip or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = self.company_id.city or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = self.company_id.state_id.name or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            vat = "CF"

        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"

        # Frases
        # xml_frases = ET.SubElement(xml_data_emision, "{" + xmlns + "}Frases")
        # ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=self.company_id.fel_company_type, CodigoEscenario=self.company_id.fel_company_code)
        # ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase="2", CodigoEscenario="1")
        invoice_line = self.invoice_line_ids
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        invoice_counter = 0
        rounding_decimals = 2
        fel_taxes = {
            "IVA": 0,
            "PETROLEO": 0,
            "TURISMO HOSPEDAJE": 0,
            "TURISMO PASAJES": 0,
            "TIMBRE DE PRENSA": 0,
            "BOMBEROS": 0,
            "TASA MUNICIPAL": 0,
        }
        # LineasFactura
        for line in invoice_line:
            invoice_counter += 1

            BienOServicio = "B"
            if line.product_id.type == 'service':
                BienOServicio = "S"

            # Item
            xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(invoice_counter))
            line_price = line.quantity * line.price_unit
            line_price = round(line_price, 2)
            ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
            ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
            ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.name or " "
            ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(line.price_unit)
            ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
            ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line.price_unit))/100, 2))

            if line.invoice_line_tax_ids:
                tax = "IVA"
            else:
                raise UserError(_("Las líneas de Factura deben de llevar impuesto (IVA)."))
            xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
            if line.invoice_line_tax_ids:
                for tax in line.invoice_line_tax_ids:
                    tax_name = tax.fel_tax
                    xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")

                    # Compute TAX
                    base = line.price_unit * line.quantity
                    if tax_name == "IVA":
                        price_tax = tax._compute_amount(base, line.price_unit, line.quantity, line.product_id, self.partner_id)
                    else:
                        price_tax = tax._compute_amount(line.price_subtotal, line.price_unit, line.quantity, line.product_id, self.partner_id)

                    ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = tax_name
                    ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
                    ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line.price_subtotal, rounding_decimals))
                    price_tax = round(price_tax, 3)
                    split_num = str(price_tax).split('.')
                    if int(split_num[1]) > 0:
                        decimal = str(split_num[1])
                        if len(decimal) > 2:
                            if int(decimal[2]) == 5:
                                price_tax += 0.001

                    decimal_set = '0.01'
                    price_tax = Decimal(price_tax).quantize(Decimal(decimal_set), rounding=ROUND_HALF_UP)

                    ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(price_tax)
                    fel_taxes[tax_name] += price_tax
            ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line.price_total, rounding_decimals))

        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        xml_total_impuestos = ET.SubElement(xml_totales, "{" + xmlns + "}TotalImpuestos")

        if fel_taxes['IVA'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='IVA', TotalMontoImpuesto=str(round(fel_taxes['IVA'], rounding_decimals)))
        if fel_taxes['PETROLEO'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='PETROLEO', TotalMontoImpuesto=str(round(fel_taxes['PETROLEO'], rounding_decimals)))
        if fel_taxes['TURISMO HOSPEDAJE'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO HOSPEDAJE', TotalMontoImpuesto=str(round(fel_taxes['TURISMO HOSPEDAJE'], rounding_decimals)))
        if fel_taxes['TURISMO PASAJES'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO PASAJES', TotalMontoImpuesto=str(round(fel_taxes['TURISMO PASAJES'], rounding_decimals)))
        if fel_taxes['TIMBRE DE PRENSA'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TIMBRE DE PRENSA', TotalMontoImpuesto=str(round(fel_taxes['TIMBRE DE PRENSA'], rounding_decimals)))
        if fel_taxes['BOMBEROS'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='BOMBEROS', TotalMontoImpuesto=str(round(fel_taxes['BOMBEROS'], rounding_decimals)))
        if fel_taxes['TASA MUNICIPAL'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TASA MUNICIPAL', TotalMontoImpuesto=str(round(fel_taxes['TASA MUNICIPAL'], rounding_decimals)))
        grand_total = Decimal(float(self.amount_total))
        grand_total = Decimal(grand_total).quantize(Decimal('0.01'), ROUND_HALF_UP)
        ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(grand_total)

        # Complementos
        debit_note_name = "Nota de débito " + str(self.source_debit_note_id.dte_number)
        dte_date = self.source_debit_note_id.dte_date
        if not dte_date:
            raise UserError('La factura no posee una fecha de DTE, si desea realizar cambios sobre la misma desactive la facturación electrónica en el diario asociado a la misma.')
        # dte_date = datetime.strptime(dte_date, '%Y-%m-%d %H:%M:%S')
        racion_de_6h = timedelta(hours=6)
        dte_date = dte_date - racion_de_6h
        date_format = "%Y-%m-%d"
        dte_date = dte_date.strftime(date_format)
        xml_complementos = ET.SubElement(xml_data_emision, "{" + xmlns + "}Complementos")
        xml_complemento = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento=debit_note_name, URIComplemento='http://www.sat.gob.gt/fel/notas.xsd', attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos})
        ET.register_namespace('cno', complemento_xmlns)

        if self.old_tax_regime is False:
            ET.SubElement(xml_complemento, "{" + complemento_xmlns + "}ReferenciasNota", FechaEmisionDocumentoOrigen=dte_date, MotivoAjuste=debit_note_name, NumeroAutorizacionDocumentoOrigen=str(self.source_debit_note_id.uuid), NumeroDocumentoOrigen=str(self.source_debit_note_id.dte_number), SerieDocumentoOrigen=str(self.source_debit_note_id.serie), Version="0.1")
        if self.old_tax_regime is True:
            ET.SubElement(xml_complemento, "{" + complemento_xmlns + "}ReferenciasNota", FechaEmisionDocumentoOrigen=dte_date, RegimenAntiguo="Antiguo", MotivoAjuste=debit_note_name, NumeroAutorizacionDocumentoOrigen=str(self.source_debit_note_id.uuid), NumeroDocumentoOrigen=str(self.source_debit_note_id.dte_number), SerieDocumentoOrigen=str(self.source_debit_note_id.serie), Version="0.1")

        # Adenda
        xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
        # ET.SubElement(ade, "NITEXTRANJERO").text = "111111"
        # ET.SubElement(xml_adenda, "DETALLE_PRODUCTO").text = self.invoice_text_detail
        # ET.SubElement(xml_adenda, "CERTIFICADO").text = "PRODUCTO CERTIFICADO GLOBALGAP, GGN 4049928186782"
        date_due = self.date_due

        # date_due = datetime.strptime(date_due, '%Y-%m-%d')

        date_due_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_due_format)
        ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method="xml")
        search_string = "ns0"
        string_remplace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, string_remplace)
        xml_content = xml_content.encode('utf_8')

        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if self.id:
            self.source_debit_note_id.write({'debit_note_id': self.id})

        if fel_certifier == 'infile':
            xml_content = base64.b64encode(xml_content)

        return xml_content

    @api.multi
    def send_data_api(self, xml_data=None, type_document='fel'):
        company_nit = self.env.user.company_id.vat

        # GET FEL CERTFIER SELECTED

        fel_certifier = self.env.user.company_id.fel_certifier
        uuid = ""
        serie = ""
        dte_number = ""
        dte_date = ""
        sat_ref_id = ""

        # DIGIFACT

        if fel_certifier == 'digifact':
            digifact_user = self.env.user.company_id.digifact_username
            digifact_password = self.env.user.company_id.digifact_password
            if self.journal_id.is_fel == 'development':
                digifact_api_login = self.env.user.company_id.digifact_api_dev_login
                digifact_api_certificate = self.env.user.company_id.digifact_api_dev_certificate
            if self.journal_id.is_fel == 'production':
                digifact_api_login = self.env.user.company_id.digifact_api_prod_login
                digifact_api_certificate = self.env.user.company_id.digifact_api_prod_certificate

            digifact_access_code = company_nit.zfill(12)

            # GET ACTIVE TOKENS
            today_date = datetime.now()
            today_date = str(today_date)

            tokens_query = self.env['pt_multicert_felgt.digifact_auth_tokens'].search([
                ('expiration_date', '>', today_date)
            ])

            auth_token = ""
            for token in tokens_query:
                auth_token = token['auth_token']

            if auth_token == "":

                username = "GT."+str(digifact_access_code)+"."+str(digifact_user)

                login_data = {
                    "Username": username,
                    "Password": digifact_password
                }

                login_headers = {
                    'content-type': "application/json"
                }

                # GET AUTH TOKEN
                login_response = requests.request("POST", digifact_api_login, data=json.dumps(login_data), headers=login_headers, verify=False)
                json_login_response = login_response.json()
                print('LoginResponse', json_login_response)
                auth_token = ""
                if "Token" in json_login_response:
                    auth_token = json_login_response['Token']
                    expiration_date = json_login_response['expira_en']
                    new_token = {
                        "name": "authToken"+str(today_date),
                        "auth_token": auth_token,
                        "expiration_date": expiration_date
                    }
                    self.env['pt_multicert_felgt.digifact_auth_tokens'].create(new_token)
                else:
                    raise ValidationError("Error de autenticación con el Certficador FEL: \n "+str(json_login_response["message"]))

            certificate_headers = {
                'content-type': "application/xml",
                'Authorization': 'Bearer ' + auth_token
            }

            type_document_sent = "CERTIFICATE_DTE_XML_TOSIGN"
            if type_document == 'cancel':
                type_document_sent = 'ANULAR_FEL_TOSIGN'

            complete_url_certificate = str(digifact_api_certificate) + "?NIT="+str(digifact_access_code)+"&TIPO="+str(type_document_sent)+"&FORMAT=XML"

            certificate_response = requests.request("POST", complete_url_certificate, data=xml_data, headers=certificate_headers, verify=False)
            json_certificate_response = certificate_response.json()

            if type_document == 'cancel':
                if 'Codigo' in json_certificate_response:
                    if json_certificate_response['Codigo'] == 1:
                        if 'AcuseReciboSAT' in json_certificate_response:
                            sat_ref_id = json_certificate_response['AcuseReciboSAT']

                        if 'Autorizacion' in json_certificate_response:
                            uuid = json_certificate_response['Autorizacion']

                        if 'Serie' in json_certificate_response:
                            serie = json_certificate_response['Serie']

                        if 'NUMERO' in json_certificate_response:
                            dte_number = json_certificate_response['NUMERO']

                        if 'Fecha_DTE' in json_certificate_response:
                            dte_date = json_certificate_response['Fecha_DTE']
                    else:
                        raise ValidationError('Ha ocurrido un error al generar la factura en la SAT: \n Codigo: '+str(json_certificate_response['Codigo'])+' \n Mensaje: '+str(json_certificate_response['Mensaje'])+'\n Detalle técnico:\n'+str(json_certificate_response['ResponseDATA1']))
                else:
                    if 'Mensaje' in json_certificate_response:
                        raise ValidationError('Ha ocurrido un error al generar la factura en la SAT: \n Codigo: '+str(json_certificate_response['Codigo'])+' \n Mensaje: '+str(json_certificate_response['Mensaje'])+'\n Detalle técnico:\n'+str(json_certificate_response['ResponseDATA1']))
                    elif 'Message' in json_certificate_response:
                        raise ValidationError('Ha ocurrido un error al comunicarse con el CERTIFICADOR: \n Mensaje: '+str(json_certificate_response['Message'])+'\n Detalle técnico:\n'+str(json_certificate_response['ExceptionMessage'] + '\n StackTrace:' + str(json_certificate_response['StackTrace'])))
                    else:
                        raise ValidationError('Ha ocurrido un error al generar la factura en la SAT (Error de CERTFICADOR)')

            if type_document == 'fel':

                if 'Codigo' in json_certificate_response:
                    if json_certificate_response['Codigo'] == 1:
                        if 'AcuseReciboSAT' in json_certificate_response:
                            sat_ref_id = json_certificate_response['AcuseReciboSAT']

                        if 'Autorizacion' in json_certificate_response:
                            uuid = json_certificate_response['Autorizacion']

                        if 'Serie' in json_certificate_response:
                            serie = json_certificate_response['Serie']

                        if 'NUMERO' in json_certificate_response:
                            dte_number = json_certificate_response['NUMERO']

                        if 'Fecha_DTE' in json_certificate_response:
                            dte_date = json_certificate_response['Fecha_DTE']

                    else:
                        raise ValidationError('Ha ocurrido un error al generar la factura en la SAT: \n Codigo: '+str(json_certificate_response['Codigo'])+' \n Mensaje: '+str(json_certificate_response['Mensaje'])+'\n Detalle técnico:\n'+str(json_certificate_response['ResponseDATA1']))

                else:
                    if 'Mensaje' in json_certificate_response:
                        raise ValidationError('Ha ocurrido un error al generar la factura en la SAT: \n Codigo: '+str(json_certificate_response['Codigo'])+' \n Mensaje: '+str(json_certificate_response['Mensaje'])+'\n Detalle técnico:\n'+str(json_certificate_response['ResponseDATA1']))
                    elif 'Message' in json_certificate_response:
                        raise ValidationError('Ha ocurrido un error al comunicarse con el CERTIFICADOR: \n Mensaje: '+str(json_certificate_response['Message'])+'\n Detalle técnico:\n'+str(json_certificate_response['ExceptionMessage'] + '\n StackTrace:' + str(json_certificate_response['StackTrace'])))
                    else:
                        raise ValidationError('Ha ocurrido un error al generar la factura en la SAT (Error de CERTFICADOR)')

        # INFILE

        if fel_certifier == 'infile':

            infile_user = self.env.user.company_id.infile_user
            infile_xml_url_signature = self.env.user.company_id.infile_xml_url_signature
            infile_xml_key_signature = self.env.user.company_id.infile_xml_key_signature
            infile_url_certificate = self.env.user.company_id.infile_url_certificate
            infile_key_certificate = self.env.user.company_id.infile_key_certificate
            infile_url_cancel = self.env.user.company_id.infile_url_anulation

            XML = xml_data
            ran = str(randint(1, 99999))
            is_anullment = "N"
            if type_document == 'cancel':
                is_anullment = 'S'
            data_send = {
                'llave': infile_xml_key_signature,
                'archivo': XML,
                'codigo': ran,
                'alias': infile_user,
                'es_anulacion': is_anullment
            }

            response = requests.request("POST", infile_xml_url_signature, data=data_send)
            JSON_response_signature = response.json()
            xml_dte = JSON_response_signature["archivo"]
            payload = {
                'nit_emisor': self.company_id.vat,
                'correo_copia': self.company_id.email,
                'xml_dte': xml_dte,
            }

            ident = str(randint(1111111, 9999999))
            headers = {
                'usuario': infile_user,
                'llave': infile_key_certificate,
                'content-type': "application/json",
                'identificador': ident,
            }

            api_url = infile_url_certificate
            if type_document == 'cancel':
                api_url = infile_url_cancel

            response = requests.request("POST", api_url, data=json.dumps(payload), headers=headers)
            JSON_response_certificate = response.json()

            uuid = JSON_response_certificate["uuid"]
            serie = JSON_response_certificate["serie"]
            dte_number = JSON_response_certificate["numero"]
            dte_date = JSON_response_certificate["fecha"]
            error_count = JSON_response_certificate["cantidad_errores"]
            error_description = JSON_response_certificate["descripcion_errores"]
            # resulta_codigo = tree_res.find('ERROR').attrib['Codigo']
            # resulta_descripcion = tree_res.find('ERROR').text
            if error_count > 0:
                raise UserError(_("You cannot validate an invoice\n Error No:%s\n %s." % (error_count, error_description)))

        return uuid, serie, dte_number, dte_date, sat_ref_id


def number2text(number_in):

    converted = ''
    if type(number_in) != 'str':
        number = str(number_in)
    else:
        number = number_in

    number_str = number
    number_str = number_str.replace(',', '')
    try:
        number_int, number_dec = number_str.split(".")
    except ValueError:
        number_int = number_str
        number_dec = ""

    number_str = number_int.zfill(9)
    millones = number_str[:3]
    miles = number_str[3:6]
    cientos = number_str[6:]

    if(millones):
        if(millones == '001'):
            converted += 'UN MILLON '
        elif(int(millones) > 0):
            converted += '%sMILLONES ' % __convertNumber(millones)

    if(miles):
        if(miles == '001'):
            converted += 'MIL '
        elif(int(miles) > 0):
            converted += '%sMIL ' % __convertNumber(miles)
    if(cientos):
        if(cientos == '001'):
            converted += 'UN '
        elif(int(cientos) > 0):
            converted += '%s ' % __convertNumber(cientos)

    if number_dec == "":
        number_dec = "00"
    if (len(number_dec) < 2):
        number_dec += '0'

    converted += 'CON ' + number_dec + "/100."
    return converted.title()


UNIDADES = (
    '',
    'UNO ',
    'DOS ',
    'TRES ',
    'CUATRO ',
    'CINCO ',
    'SEIS ',
    'SIETE ',
    'OCHO ',
    'NUEVE ',
    'DIEZ ',
    'ONCE ',
    'DOCE ',
    'TRECE ',
    'CATORCE ',
    'QUINCE ',
    'DIECISEIS ',
    'DIECISIETE ',
    'DIECIOCHO ',
    'DIECINUEVE ',
    'VEINTE '
)
DECENAS = (
    'VEINTI',
    'TREINTA ',
    'CUARENTA ',
    'CINCUENTA ',
    'SESENTA ',
    'SETENTA ',
    'OCHENTA ',
    'NOVENTA ',
    'CIEN '
)
CENTENAS = (
    'CIENTO ',
    'DOSCIENTOS ',
    'TRESCIENTOS ',
    'CUATROCIENTOS ',
    'QUINIENTOS ',
    'SEISCIENTOS ',
    'SETECIENTOS ',
    'OCHOCIENTOS ',
    'NOVECIENTOS '
)


def store_sent_xml(self, xml_content, vat, date_due, certifier="digifact"):

    if certifier == "digifact":
        api_sent = self.env.user.company_id.digifact_api_dev_certificate
        if self.journal_id.is_fel == 'development':
            api_sent = self.env.user.company_id.digifact_api_dev_certificate
        if self.journal_id.is_fel == 'production':
            api_sent = self.env.user.company_id.digifact_api_prod_certificate

        new_xml_sent = {
                "name": str(vat) + '-'+str(self.company_id.vat)+'-'+str(date_due),
                "xml_content": xml_content,
                "api_sent": api_sent
        }
        self.env['pt_multicert_felgt.digifact_xml_sent'].create(new_xml_sent)

    if certifier == "infile":
        api_sent = self.env.user.company_id.infile_xml_url_signature

        sql = "INSERT INTO pt_multicert_felgt_infile_xml_sent(name, xml_content, api_sent, create_uid, create_date, write_uid, write_date)"
        sql += " VALUES(%s, %s, %s, %s, %s, %s, %s)"

        db_name = self.env.cr.dbname
        cr_log = sql_db.db_connect(self.env.cr.dbname).cursor()
        # create transaction cursor
        name = str(vat) + '-'+str(self.company_id.vat)+'-'+str(date_due)
        final_xml = xml_content.decode('utf-8')
        params = [name, final_xml, api_sent, self.env.user.id, datetime.now(), self.env.user.id, datetime.now()]
        cr_log.execute(sql, params)
        cr_log.commit()

    if certifier == "megaprint":
        api_sent = self.env.user.company_id.megaprint_api_dev_url_invoices
        if self.journal_id.is_fel == 'development':
            api_sent = self.env.user.company_id.megaprint_api_dev_url_invoices
        if self.journal_id.is_fel == 'production':
            api_sent = self.env.user.company_id.megaprint_api_prod_url_invoices

        new_xml_sent = {
                "name": str(vat) + '-'+str(self.company_id.vat)+'-'+str(date_due),
                "data_content": xml_content,
                "api_sent": api_sent
        }

        self.env['pt_multicert_felgt.megaprint_json_sent'].create(new_xml_sent)


def __convertNumber(n):
    output = ''

    if(n == '100'):
        output = "CIEN"
    elif(n[0] != '0'):
        output = CENTENAS[int(n[0])-1]

    k = int(n[1:])
    if(k <= 20):
        output += UNIDADES[k]
    else:
        if((k > 30) & (n[2] != '0')):
            output += '%sY %s' % (DECENAS[int(n[1])-2], UNIDADES[int(n[2])])
        else:
            output += '%s%s' % (DECENAS[int(n[1])-2], UNIDADES[int(n[2])])

    return output
