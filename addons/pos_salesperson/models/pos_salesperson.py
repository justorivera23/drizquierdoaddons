# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError


class POSSalesperson(models.Model):
    _name = 'pos.salesperson'
    _description = 'POS Salesperson'

    name = fields.Char(index=True, required=True)
    active = fields.Boolean(default=True)
    email = fields.Char()
    phone = fields.Char()

    image = fields.Binary("Image", attachment=True,
        help="This field holds the image used as avatar for this contact, limited to 1024x1024px",)
    image_medium = fields.Binary("Medium-sized image", attachment=True,
        help="Medium-sized image of this contact. It is automatically "\
             "resized as a 128x128px image, with aspect ratio preserved. "\
             "Use this field in form views or some kanban views.")
    image_small = fields.Binary("Small-sized image", attachment=True,
        help="Small-sized image of this contact. It is automatically "\
             "resized as a 64x64px image, with aspect ratio preserved. "\
             "Use this field anywhere a small image is required.")

    pos_security_pin = fields.Char(string='Security PIN', size=32, help='A Security PIN used to protect sensible functionality in the Point of Sale')

    @api.constrains('pos_security_pin')
    def _check_pin(self):
        if self.pos_security_pin and not self.pos_security_pin.isdigit():
            raise UserError(_("Security PIN can only contain digits"))

    @api.model
    def create(self, vals):
        tools.image_resize_images(vals)
        return super(POSSalesperson, self).create(vals)

    @api.multi
    def write(self, vals):
        tools.image_resize_images(vals)
        return super(POSSalesperson, self).write(vals)
