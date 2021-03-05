# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class ResCompany(models.Model):
    _inherit = "res.company"

    fel_certifier = fields.Selection([
        ('digifact', 'Digifact'),
        ('infile', 'InFile'),
        ('megaprint', 'Megaprint'),
        ], string='Certificador a utilizar', default='digifact')

    # DIGIFACT FIELDS
    digifact_username = fields.Char(string="Usuario", default="fel")
    digifact_password = fields.Char(string="Contraseña", default="fel")
    digifact_api_dev_login = fields.Char(string="Login", default="https://felgttestaws.digifact.com.gt/felapi/api/login/get_token")
    digifact_api_dev_certificate = fields.Char(string="Generación FEL", default="https://felgttestaws.digifact.com.gt/felapi/api/FELRequest")
    digifact_api_prod_login = fields.Char(string="Login", default="https://felgttestaws.digifact.com.gt/felapi/api/login/get_token")
    digifact_api_prod_certificate = fields.Char(string="Generación FEL", default="https://felgttestaws.digifact.com.gt/felapi/api/FELRequest")

    # INFILE FIELDS
    infile_user = fields.Char(string="Usuario")
    infile_xml_key_signature = fields.Char(string="Llave Firma")
    infile_xml_url_signature = fields.Char(string="URL Firma", default="https://signer-emisores.feel.com.gt/sign_solicitud_firmas/firma_xml")
    infile_key_certificate = fields.Char(string="Llave Certificación")
    infile_url_certificate = fields.Char(string="URL Certificación", default="https://certificador.feel.com.gt/fel/certificacion/dte")
    infile_url_anulation = fields.Char(string="URL Anulación", default="https://certificador.feel.com.gt/fel/anulacion/dte")
    infile_establishment_code = fields.Char(string="Código Establecimiento")

    fel_company_type = fields.Char(string="Tipo de frase", help="De acuerdo al tipo de afiliación a los impuestos, o el tipo de operación que esté realizando el emisor.", default="1")
    fel_company_code = fields.Char(string="Código de escenario", help="Inidique el escenario del emisor en base al tipo de frase.", default="1")
    consignatary_code = fields.Char(string="Código de Consignatario o Destinatario")
    exporter_code = fields.Char(string="Código Exportador")
