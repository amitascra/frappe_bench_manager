// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Load Balancing', {
	refresh: function(frm) {
		if (frm.doc.status === 'Pending') {
			frm.add_custom_button('Configure Load Balancer', () => {
				frappe.call({
					method: 'configure_load_balancer',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Load balancer configuration initiated');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Configuring') {
			frm.add_custom_button('Activate Load Balancer', () => {
				frappe.call({
					method: 'activate_load_balancer',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Load balancer activated successfully');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Active') {
			frm.add_custom_button('Add Upstream', () => {
				frappe.prompt([
					{
						fieldname: 'cloud_bench',
						fieldtype: 'Link',
						label: 'Cloud Bench',
						options: 'Cloud Bench',
						reqd: 1
					},
					{
						fieldname: 'port',
						fieldtype: 'Int',
						label: 'Port',
						default: 8000,
						reqd: 1
					}
				], (values) => {
					frappe.call({
						method: 'add_upstream',
						doc: frm.doc,
						args: values,
						callback: function(r) {
							if (r.message) {
								frappe.msgprint('Upstream added successfully');
							}
						}
					});
				}, 'Add Upstream');
			}, 'Actions');
		}
	},
	
	proxy_server: function(frm) {
		if (frm.doc.proxy_server) {
			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					doctype: 'Proxy Server',
					name: frm.doc.proxy_server,
					fieldname: ['virtual_machine', 'status']
				},
				callback: function(r) {
					if (r.message) {
						frappe.call({
							method: 'frappe.client.get_value',
							args: {
								doctype: 'Virtual Machine',
								name: r.message.virtual_machine,
								fieldname: ['cloud_provider']
							},
							callback: function(vm_r) {
								if (vm_r.message) {
									frm.set_value('cloud_provider', vm_r.message.cloud_provider);
								}
							}
						});
					}
				}
			});
		}
	}
});
