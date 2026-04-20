// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Cloud Bench', {
	refresh: function(frm) {
		if (frm.doc.status === 'Pending') {
			frm.add_custom_button('Deploy Bench', () => {
				frappe.call({
					method: 'deploy_bench',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Bench deployment initiated');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Active') {
			frm.add_custom_button('Restart Bench', () => {
				frappe.call({
					method: 'restart_bench',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Bench restart initiated');
						}
					}
				});
			}, 'Actions');
			
			frm.add_custom_button('Rebuild Bench', () => {
				frappe.call({
					method: 'rebuild_bench',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Bench rebuild initiated');
						}
					}
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Active' || frm.doc.status === 'Broken') {
			frm.add_custom_button('Archive Bench', () => {
				frappe.confirm('Are you sure you want to archive this bench?', () => {
					frappe.call({
						method: 'archive_bench',
						doc: frm.doc,
						callback: function(r) {
							if (r.message) {
								frappe.msgprint('Bench archived successfully');
								frm.reload_doc();
							}
						}
					});
				});
			}, 'Actions');
		}
	},
	
	application_server: function(frm) {
		if (frm.doc.application_server) {
			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					doctype: 'Application Server',
					name: frm.doc.application_server,
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
