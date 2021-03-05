# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fel_certifier = fields.Selection([
        ('digifact', 'Digifact'),
        ('infile', 'InFile'),
        ('megaprint', 'Megaprint'),
        ], string='Certificador a utilizar', related="company_id.fel_certifier", readonly=False, default='digifact')
    # DIGIFACT FIELDS
    digifact_username = fields.Char(string="Usuario", related="company_id.digifact_username", readonly=False)
    digifact_password = fields.Char(string="Contraseña", related="company_id.digifact_password", readonly=False)
    digifact_api_dev_login = fields.Char(string="Login", related="company_id.digifact_api_dev_login", readonly=False)
    digifact_api_dev_certificate = fields.Char(string="Generación FEL", related="company_id.digifact_api_dev_certificate", readonly=False)
    digifact_api_prod_login = fields.Char(string="Login", related="company_id.digifact_api_prod_login", readonly=False)
    digifact_api_prod_certificate = fields.Char(string="Generación FEL", related="company_id.digifact_api_prod_certificate", readonly=False)
    digifact_establishment_code = fields.Char(string="Código Establecimiento", related="company_id.digifact_establishment_code", readonly=False)

    # INFILE FIELDS
    infile_user = fields.Char(string="Usuario", related="company_id.infile_user", readonly=False)
    infile_xml_key_signature = fields.Char(string="Llave Firma", related="company_id.infile_xml_key_signature", readonly=False)
    infile_xml_url_signature = fields.Char(string="URL Firma", related="company_id.infile_xml_url_signature", readonly=False)
    infile_key_certificate = fields.Char(string="Llave Certificación", related="company_id.infile_key_certificate", readonly=False)
    infile_url_certificate = fields.Char(string="URL Certificación", related="company_id.infile_url_certificate", readonly=False)
    infile_url_anulation = fields.Char(string="URL Anulación", related="company_id.infile_url_anulation", readonly=False)
    infile_establishment_code = fields.Char(string="Código Establecimiento", related="company_id.infile_establishment_code", readonly=False)
