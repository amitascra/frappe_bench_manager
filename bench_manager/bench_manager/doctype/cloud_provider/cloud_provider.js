// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Cloud Provider', {
	refresh: function(frm) {
		if (frm.doc.provider_type === 'AWS EC2') {
			// Clear all custom buttons in Actions group to prevent duplicates
			frm.clear_custom_buttons('Actions');
			
			// Add Provision VPC button if needed
			if (!frm.doc.vpc_id) {
				frm.add_custom_button('Provision VPC', () => {
					frm.dashboard.show_progress('Provisioning VPC', 10, 'Provisioning VPC...');
					frm.page.set_indicator(__('In Progress'), 'orange');
					
					frappe.call({
						method: 'provision_vpc',
						doc: frm.doc,
						freeze: true,
						freeze_message: 'Provisioning VPC...',
						callback: function(r) {
							frm.dashboard.hide_progress('Provisioning VPC');
							if (r.message) {
								frappe.msgprint('VPC provisioned successfully');
								frm.reload_doc();
							}
						},
						error: function(err) {
							frm.dashboard.hide_progress('Provisioning VPC');
							frappe.msgprint({
								title: 'Error',
								message: err.message,
								indicator: 'red'
							});
						}
					});
				}, 'Actions');
			}
			
			// Add Create SSH Key Pair button (no group to put in main menu)
			frm.add_custom_button('Create SSH Key Pair', () => {
				frm.dashboard.show_progress('Creating SSH Key Pair', 10, 'Creating SSH key pair...');
				frm.page.set_indicator(__('In Progress'), 'orange');
				
				frappe.call({
					method: 'create_ssh_key_pair',
					doc: frm.doc,
					freeze: true,
					freeze_message: 'Creating SSH key pair...',
					callback: function(r) {
						frm.dashboard.hide_progress('Creating SSH Key Pair');
						if (r.message) {
							frappe.msgprint('SSH Key Pair created successfully');
							frm.reload_doc();
						}
					},
					error: function(err) {
						frm.dashboard.hide_progress('Creating SSH Key Pair');
						frappe.msgprint({
							title: 'Error',
							message: err.message,
							indicator: 'red'
						});
					}
				});
			});
		}
	},
	
	provider_type: function(frm) {
		if (frm.doc.provider_type === 'AWS EC2') {
			frm.set_df_property('aws_access_key_id', 'reqd', 1);
			frm.set_df_property('aws_secret_access_key', 'reqd', 1);
			frm.set_df_property('region', 'reqd', 1);
		}
	}
});
