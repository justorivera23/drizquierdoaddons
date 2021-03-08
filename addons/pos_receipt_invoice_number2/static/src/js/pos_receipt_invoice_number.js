odoo.define('pos_receipt_invoice_number', function (require) {
    var models = require('point_of_sale.models');
    var screens = require('point_of_sale.screens');
    var rpc = require('web.rpc');
    var core = require('web.core');
    var qweb = core.qweb;

    var _super_Order = models.Order.prototype;
    models.Order = models.Order.extend({
        initialize: function (attributes, options) {
            _super_Order.initialize.apply(this, arguments);
            if (this.pos.config.pos_auto_invoice) {
                this.to_invoice = true;
            }
        },
        init_from_JSON: function (json) {
            var res = _super_Order.init_from_JSON.apply(this, arguments);
            if (json.to_invoice) {
                this.to_invoice = json.to_invoice;
            }
        }
    });
    var _super_PosModel = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({
        initialize: function (session, attributes) {
            var partner_model = _.find(this.models, function (model) {
                return model.model === 'res.partner';
            });
            partner_model.fields.push('vat');
            _super_PosModel.initialize.apply(this, arguments);
        }
    });
    screens.ReceiptScreenWidget.include({
        print_xml: function () {
            var self = this;
            if (this.pos.config.receipt_invoice_number) {
                self.receipt_data = this.get_receipt_render_env();
                var order = this.pos.get_order();
                return rpc.query({
                    model: 'pos.order',
                    method: 'search_read',
                    domain: [['pos_reference', '=', order['name']]],
                    fields: ['invoice_id'],
                }).then(function (orders) {
                    if (orders.length > 0) {
                        if (orders[0]['invoice_id']) {
                            console.log('POS MOD CALL')
                            var invoice_number = orders[0]['invoice_id'][1].split(" ")[0];
                            self.receipt_data['order']['invoice_number'] = invoice_number;
                            var invoice_id = orders[0]['invoice_id'][0];
                            self.pos.get_order()['invoice_number'] = invoice_number;
                            rpc.query({
                                model: 'account.invoice',
                                method: 'search_read',
                                domain: [['id', '=', invoice_id]]
                            }).then(function (invoice_number) {
                                
                                invoice_number = invoice_number;
                                serie = invoice_number[0]['serie']
                                dte_number = invoice_number[0]['dte_number']
                                dte_date = invoice_number[0]['dte_date']
                                uuid = invoice_number[0]['uuid']

                                self.receipt_data['order']['serie'] = serie;
                                self.receipt_data['order']['dte_number'] = dte_number;
                                self.receipt_data['order']['dte_date'] = dte_date;
                                self.receipt_data['order']['uuid'] = uuid;
                                
                                var receipt = qweb.render('XmlReceipt', self.receipt_data);
                                self.pos.proxy.print_receipt(receipt);
                                
                            });
                        }
                    }
                });
            } else {
                this._super();
            }
        },
        /*render_receipt: function () {
            this._super();
            var self = this;
            var order = this.pos.get_order();
            if (!this.pos.config.iface_print_via_proxy && this.pos.config.receipt_invoice_number && order.is_to_invoice()) {
                var invoiced = new $.Deferred();
                rpc.query({
                    model: 'pos.order',
                    method: 'search_read',
                    domain: [['pos_reference', '=', order['name']]],
                    fields: ['invoice_id']
                }).then(function (orders) {
                    if (orders.length > 0 && orders[0]['invoice_id'] && orders[0]['invoice_id'][1]) {
                        var invoice_number = orders[0]['invoice_id'][1].split(" ")[0];
                        var invoice_id = orders[0]['invoice_id'][0];
                        self.pos.get_order()['invoice_number'] = invoice_number;
                        rpc.query({
                            model: 'account.invoice',
                            method: 'search_read',
                            domain: [['id', '=', invoice_id]]
                        }).then(function (invoice_number) {
                            invoice_number = invoice_number;
                            serie = invoice_number[0]['serie']
                            dte_number = invoice_number[0]['dte_number']
                            dte_date = invoice_number[0]['dte_date']
                            uuid = invoice_number[0]['uuid']
                            self.pos.get_order()['serie'] = serie;
                            self.pos.get_order()['dte_number'] = dte_number;
                            self.pos.get_order()['dte_date'] = dte_date;
                            self.pos.get_order()['uuid'] = uuid;
                            self.$('.pos-receipt-container').html(qweb.render('PosTicket', self.get_receipt_render_env()));
                        });
                    }
                    invoiced.resolve();
                }).fail(function (type, error) {
                    invoiced.reject(error);
                });
                return invoiced;
            } else {
                this._super();
            }
        }*/
    })
});
