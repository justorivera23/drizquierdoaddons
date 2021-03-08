odoo.define('pos_salesperson.pos_salesperson', function (require) {
"use strict";

    var models = require('point_of_sale.models');
    var chrome = require('point_of_sale.chrome');
    var PosBaseWidget = require('point_of_sale.BaseWidget');
    var gui = require('point_of_sale.gui');
    var PopupWidget = require('point_of_sale.popups');
    var screens = require('point_of_sale.screens');
    var PosDB = require('point_of_sale.DB');
    var core = require('web.core');
    var _t = core._t;

    models.PosModel.prototype.models.push({
        model:  'pos.salesperson',
        fields: ['id', 'name', 'pos_security_pin'],
        ids:    function(self){ 
            return self.config.pos_salesperson_ids; 
        },
        loaded: function(self, pos_salespersons){
            self.pos_salespersons = pos_salespersons;
        },
    });

    PosDB.include({
        set_pos_salesperson: function(pos_salesperson) {
            this.save('pos_salesperson_id', pos_salesperson || null);
        },
        get_pos_salesperson: function() {
            return this.load('pos_salesperson_id');
        }
    });

    var _super_order = models.Order.prototype;
    models.Order = models.Order.extend({
        initialize: function() {
            _super_order.initialize.apply(this,arguments);
            if (this.get_pos_salesperson() == undefined) {
                this.set_pos_salesperson(this.pos.config.pos_salesperson_ids ? this.pos.config.pos_salesperson_ids[0] : false);
                this.save_to_db();
            }
        },
        export_as_JSON: function() {
            var json = _super_order.export_as_JSON.apply(this,arguments);
            json.pos_salesperson_id = this.get_pos_salesperson();
            return json;
        },
        init_from_JSON: function(json) {
            _super_order.init_from_JSON.apply(this,arguments);
            this.pos_salesperson_id = json.pos_salesperson_id;
        },
        get_pos_salesperson: function(){
            return this.pos_salesperson_id || this.pos.db.get_pos_salesperson();
        },
        get_pos_salesperson_name: function(){
            if (this.get_pos_salesperson()) {
                return this.pos.get_salesperson_by_id(this.get_pos_salesperson()).name
            }
        },
        set_pos_salesperson: function(pos_salesperson) {
            this.pos_salesperson_id = pos_salesperson;
            this.pos.db.set_pos_salesperson(pos_salesperson);
            this.trigger('change');
        },
    });

    var PosModelSuper = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({
        get_salesperson_by_id: function(id){
            for (var i=0; i<this.pos_salespersons.length; i++) {
                if (this.pos_salespersons[i].id == id) {
                    return this.pos_salespersons[i];
                }
            }
        },
    });

    var SalespersonWidget = screens.ActionButtonWidget.extend({
        template: 'SalespersonWidget',
        init: function(parent, options) {
            var self = this;
            this._super(parent, options);

            this.pos.bind('change:selectedOrder', function() {
                self.renderElement();
            });
        },
        button_click: function(){
            if (this.pos.config.pos_salesperson_ids.length > 1) {
                var self = this;
                this.select_seller().then(function(seller){
                    self.pos.get_order().set_pos_salesperson(seller.id);
                    self.renderElement();
                });
            }
        },
        salesperson: function() {
            if (this.pos.get_order()) {
                return this.pos.get_order().get_pos_salesperson_name();
            } else {
                var pos_salesperson_id = this.pos.config.pos_salesperson_ids ? this.pos.config.pos_salesperson_ids[0] : false;
                if (pos_salesperson_id) {
                    return this.pos.get_salesperson_by_id(pos_salesperson_id).name
                }
            }
        },
        select_seller: function(options){
            var self = this;
            var def  = new $.Deferred();
            var list = [];
            for (var i = 0; i < this.pos.config.pos_salesperson_ids.length; i++) {
                var seller = this.pos.pos_salespersons[i];
                list.push({
                    'label': seller.name,
                    'item':  seller,
                });
            }
            this.gui.show_popup('selection',{
                title: _t('Select Salesperson'),
                list: list,
                confirm: function(seller){ def.resolve(seller); },
                cancel: function(){ def.reject();},
                is_selected: function(seller){
                    return seller.id === this.pos.get_order().get_pos_salesperson();
                },
            });

            return def.then(function(seller){
                if(seller.pos_security_pin) {
                    return self.ask_password(seller.pos_security_pin).then(function(){
                        return seller;
                    }); 
                } else {
                    return seller;
                }
            });
        },
        ask_password: function(password) {
            var self = this;
            var ret = new $.Deferred();
            if (password) {
                this.gui.show_popup('password',{
                    'title': _t('Password ?'),
                    confirm: function(pw) {
                        if (pw !== password) {
                            self.gui.show_popup('error',_t('Incorrect Password'));
                            ret.reject();
                        } else {
                            ret.resolve();
                        }
                    },
                });
            } else {
                ret.resolve();
            }
            return ret;
        },
    });

    screens.define_action_button({
        'name': 'salesperson_widget',
        'widget': SalespersonWidget,
        'condition': function(){ 
            if (this.pos.config.pos_salesperson_ids.length > 0) {
                return true;
            }
        },
    });
});