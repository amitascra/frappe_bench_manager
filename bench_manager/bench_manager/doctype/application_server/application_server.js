// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Application Server', {
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
			frm.add_custom_button('Install Agent', () => {
				frappe.call({
					method: 'install_agent',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Agent installed successfully');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
			
			frm.add_custom_button('Install Docker', () => {
				frappe.call({
					method: 'install_docker',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Docker installed successfully');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Installing' && frm.doc.agent_installed && frm.doc.docker_installed) {
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
		
		if (frm.doc.status === 'Active') {
			frm.add_custom_button('Restart Server', () => {
				frappe.call({
					method: 'restart_server',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Server restart initiated');
						}
					}
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Active' || frm.doc.status === 'Broken') {
			frm.add_custom_button('Archive Server', () => {
				frappe.confirm('Are you sure you want to archive this server?', () => {
					frappe.call({
						method: 'archive_server',
						doc: frm.doc,
						callback: function(r) {
							if (r.message) {
								frappe.msgprint('Server archived successfully');
								frm.reload_doc();
							}
						}
					});
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
