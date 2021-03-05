# -*- coding: utf-8 -*-
from odoo import http

# class DigifactFelgt(http.Controller):
#     @http.route('/digifact_felgt/digifact_felgt/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/digifact_felgt/digifact_felgt/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('digifact_felgt.listing', {
#             'root': '/digifact_felgt/digifact_felgt',
#             'objects': http.request.env['digifact_felgt.digifact_felgt'].search([]),
#         })

#     @http.route('/digifact_felgt/digifact_felgt/objects/<model("digifact_felgt.digifact_felgt"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('digifact_felgt.object', {
#             'object': obj
#         })