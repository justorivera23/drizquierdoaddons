odoo.define('pt_pos_product_conversion.popup', function (require) {
    "use strict";

    var gui = require('point_of_sale.gui');
    var rpc = require('web.rpc');
    var PosBaseWidget = require('point_of_sale.BaseWidget');
    var PopupWidget = require('point_of_sale.popups');
    var core = require('web.core');
    var chrome = require('point_of_sale.chrome');
    var models = require('point_of_sale.models');
    var framework = require('web.framework');
    var utils = require('web.utils');
    var field_utils = require('web.field_utils');
    var round_pr = utils.round_precision;
    var round_di = utils.round_decimals;

    var _t = core._t;
    var QWeb = core.qweb;

    var ConfirmConversionPopupWidget = PopupWidget.extend({
        template: 'ConfirmConversionPopupWidget',
        show: function (options) {
            this._super(options);
            this.product = options.product;
            this.stock_location_id = options.stock_location_id;
            this.current_order_qty = options.current_order_qty;
            this.order_item = options.item;
            this.conversion_rate = 0;
            this.main_uom_name = "";
            this.main_product_name = "";
            this.main_product_id = 0;
            this.main_product_qty = 0;
            this.new_qty = 0;
            this.units_qyt = 0;
            this.current_qty = options.product.qty_available;
            this.main_valid_qty = true;
            var self = this;
            var order = self.pos.get_order();
            self.renderElement();
            var params = {
                model: "product.conversion",
                method: "pos_check_conversion",
                args: [{ 'product_id': self.product.id, 'stock_location_id': self.stock_location_id }],
            }
            rpc.query(params, { async: false })
                .then(function (result) {
                    if (result) {
                        self.conversion_rate = result.conversion_ratio;
                        self.main_uom_name = result.uom_name;
                        self.main_product_name = result.product_name;
                        self.main_product_id = result.main_product_id;
                        self.main_product_qty = result.main_current_qty;
                        if (self.main_product_id == 0 && self.conversion_rate == 0){
                            $('#conversion_tittle').html('El producto seleccionado no tiene un producto para conversión asignado');
                            $('#conversion_tittle').addClass('main_product_not_found');
                            $('.confirm').hide();
                            $('#total_units').hide();
                        }
                        if (self.main_product_qty <= 0){
                            $('#conversion_tittle').html('El producto de conversión seleccionado no tiene cantidades en inventario disponibles');
                            $('#conversion_tittle').addClass('main_product_not_found');
                            $('.confirm').hide();
                            $('#total_units').hide();
                        }
                    }
                });
            $('#total_units').on('keyup', function () {
                var total_units = Number($("#total_units").val());
                if (total_units > 0) {
                    if (total_units <= self.conversion_rate) {
                        self.units_qty = 1;
                        self.new_qty = self.conversion_rate;
                    } else {
                        if (self.conversion_rate > 0) {
                            self.units_qty = total_units / self.conversion_rate;
                            self.units_qty = Math.ceil(self.units_qty);
                            self.new_qty = self.conversion_rate * self.units_qty;
                        }
                    }
                    var plural_name = ""
                    if (self.main_uom_name == 'UNIDAD'){
                        plural_name = "(ES)"
                    }
                    if (self.main_uom_name == 'CAJA' || self.main_uom_name == 'TABLETA'){
                        plural_name = "(S)"
                    }
                    if (self.main_product_qty >= self.units_qty){
                        $('#btn_conversion_confirm').prop('disabled', false);
                        $('#btn_conversion_confirm').removeClass('disable_btn');
                        $('#validation_message').html('AVISO: Procederá a convertir ' + self.units_qty + ' ' + self.main_uom_name + plural_name + ' del producto ' + self.main_product_name);
                    }else{
                        $('#btn_conversion_confirm').prop('disabled', true);
                        $('#btn_conversion_confirm').addClass('disable_btn');
                        $('#validation_message').html('AVISO: No es posible realizar la conversión.<br/> La razón es que no hay suficientes ' + self.main_uom_name + plural_name + ' del producto ' + self.main_product_name);
                    }

                }
            });
        },
        click_confirm: function () {
            $('#btn_conversion_confirm').addClass('disable_btn');
            $('#btn_conversion_confirm').prop('disabled', true);
            var self = this;
            var params = {
                model: "product.conversion",
                method: "pos_process_conversion",
                args: [{ 'product_id': self.product.id, 'stock_location_id': self.stock_location_id, 'units_qty': self.units_qty }],
            }
            rpc.query(params, { async: true })
                .then(function (result) {
                    if (result) {
                        if (self.product.to_weight && self.pos.config.iface_electronic_scale) {
                            self.gui.show_screen('scale', { product: self.product });
                        } else {
                            var new_qty = self.new_qty + self.current_qty;
                            self.product.qty_available = new_qty;
                            $('[data-product-id="' + self.product.id + '"]').find('div.css_product_custom_qty span').removeClass('product-qty-low');
                            $('[data-product-id="' + self.product.id + '"]').find('div.css_product_custom_qty span').addClass('product-qty');
                            $('[data-product-id="' + self.product.id + '"]').find('div.css_product_custom_qty span.stock_qty').html(new_qty);
                            var new_main_product_qty = self.main_product_qty - self.units_qty;

                            // Main Product QTY Update
                            if (new_main_product_qty <= 0){
                                $('[data-product-id="' + self.product.id + '"]').find('div.css_product_custom_qty span').removeClass('product-qty');
                                $('[data-product-id="' + self.product.id + '"]').find('div.css_product_custom_qty span').addClass('product-qty-low');
                            }
                            $('[data-product-id="' + self.main_product_id + '"]').find('div.css_product_custom_qty span.stock_qty').html(new_main_product_qty);
                            self.product.qty_available = self.new_qty;

                            if (self.current_qty <= 0){
                                var options = {
                                    "quantity": $('#total_units').val()
                                }
                                self.pos.get_order().add_product(self.product, options);
                            }else{
                                self.pos.get_order().remove_orderline(self.order_item);
                                var options = {
                                    "quantity": self.current_order_qty
                                }
                                self.pos.get_order().add_product(self.product, options);
                            }

                        }
                        self.gui.close_popup();
                    }
                });
        },
    });
    gui.define_popup({ name: 'confirm_product_conversion', widget: ConfirmConversionPopupWidget });
});