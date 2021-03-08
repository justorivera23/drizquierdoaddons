# -*- coding: utf-8 -*-
from odoo import http

# class PtFlexiUsers(http.Controller):
#     @http.route('/pt_flexi_users/pt_flexi_users/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/pt_flexi_users/pt_flexi_users/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('pt_flexi_users.listing', {
#             'root': '/pt_flexi_users/pt_flexi_users',
#             'objects': http.request.env['pt_flexi_users.pt_flexi_users'].search([]),
#         })

#     @http.route('/pt_flexi_users/pt_flexi_users/objects/<model("pt_flexi_users.pt_flexi_users"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('pt_flexi_users.object', {
#             'object': obj
#         })