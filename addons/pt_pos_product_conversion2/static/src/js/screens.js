odoo.define('pt_pos_product_conversion.screens', function (require) {
    "use strict";

    var screens = require('point_of_sale.screens');
	var gui = require('point_of_sale.gui');
	var models = require('point_of_sale.models');
	var rpc = require('web.rpc');
	var core = require('web.core');
	var PosBaseWidget = require('point_of_sale.BaseWidget');

	var QWeb = core.qweb;
    var _t = core._t;

    screens.ProductScreenWidget.include({
        click_product: function(product) {
            var self_info = this;
            if (product.qty_available <= 0 && product.type != 'service'){
                var options = {
                    'product': product,
                    'stock_location_id': self.pos.config.stock_location_id[0],
                    'current_order_qty': 0,
                    'item': false
                };
                self.gui.show_popup('confirm_product_conversion',options);
            }else{
                if(product.to_weight && this.pos.config.iface_electronic_scale){
                    this.gui.show_screen('scale',{product: product});
                }else{
                    this.pos.get_order().add_product(product);
                }
            }
        },
    });
});