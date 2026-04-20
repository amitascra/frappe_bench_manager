// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Cloud Settings', {
	refresh: function(frm) {
		frm.add_custom_button('Test Docker Registry', () => {
			frappe.msgprint('Docker registry test not implemented yet');
		}, 'Actions');
	},
	
	monitoring_enabled: function(frm) {
		if (!frm.doc.monitoring_enabled) {
			frm.set_value('monitoring_endpoint', '');
		}
	},
	
	logging_enabled: function(frm) {
		if (!frm.doc.logging_enabled) {
			frm.set_value('logging_endpoint', '');
		}
	}
});
