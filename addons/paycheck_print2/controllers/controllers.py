# -*- coding: utf-8 -*-
from odoo import http

# class PaycheckPrint(http.Controller):
#     @http.route('/paycheck_print/paycheck_print/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/paycheck_print/paycheck_print/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('paycheck_print.listing', {
#             'root': '/paycheck_print/paycheck_print',
#             'objects': http.request.env['paycheck_print.paycheck_print'].search([]),
#         })

#     @http.route('/paycheck_print/paycheck_print/objects/<model("paycheck_print.paycheck_print"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('paycheck_print.object', {
#             'object': obj
#         })