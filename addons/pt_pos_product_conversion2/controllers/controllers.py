# -*- coding: utf-8 -*-
from odoo import http

# class PtPosProductConversion(http.Controller):
#     @http.route('/pt_pos_product_conversion/pt_pos_product_conversion/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/pt_pos_product_conversion/pt_pos_product_conversion/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('pt_pos_product_conversion.listing', {
#             'root': '/pt_pos_product_conversion/pt_pos_product_conversion',
#             'objects': http.request.env['pt_pos_product_conversion.pt_pos_product_conversion'].search([]),
#         })

#     @http.route('/pt_pos_product_conversion/pt_pos_product_conversion/objects/<model("pt_pos_product_conversion.pt_pos_product_conversion"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('pt_pos_product_conversion.object', {
#             'object': obj
#         })