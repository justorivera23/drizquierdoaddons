# -*- encoding: utf-8 -*-

from odoo import api, fields, models, tools, SUPERUSER_ID


class PtMuticertFelgtInfileFelgtXmlSent(models.Model):
    _name = "pt_multicert_felgt.infile_xml_sent"
    _description = "Records the XMLs generated on the api calls"

    name = fields.Char(string="Nombre",  required=True)
    xml_content = fields.Char(string="content")
    api_sent = fields.Char(string="api sent")
