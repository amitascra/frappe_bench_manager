// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Database Server', {
	refresh: function(frm) {
		if (frm.doc.status === 'Pending') {
			frm.add_custom_button('Provision Server', () => {
				frappe.call({
					method: 'provision_server',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Server provisioning initiated');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Installing') {
			frm.add_custom_button('Activate Server', () => {
				frappe.call({
					method: 'activate_server',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Server activated successfully');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
		}
	},
	
	virtual_machine: function(frm) {
		if (frm.doc.virtual_machine) {
			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					doctype: 'Virtual Machine',
					name: frm.doc.virtual_machine,
					fieldname: ['cloud_provider', 'status']
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('cloud_provider', r.message.cloud_provider);
					}
				}
			});
		}
	}
});
