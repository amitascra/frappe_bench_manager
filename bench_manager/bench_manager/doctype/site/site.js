// Copyright (c) 2017, Frappé and contributors
// For license information, please see license.txt

frappe.ui.form.on('Site', {
	onload: function(frm) {
		if (frm.is_new() != 1) {
			frm.save();
			frm.call('update_app_alias');
		}
		frappe.realtime.on('Bench-Manager:reload-page', () => {
			frm.reload_doc();
		});
	},
	check_status_button: function(frm) {
		frappe.call({
			method: 'check_site_status',
			doc: frm.doc,
			callback: function(r) {
				if (r.message) {
					let indicator = r.message.status === 'Online' ? 'green' : 'red';
					let msg = `Site Status: ${r.message.status}`;
					if (r.message.response_time) {
						msg += ` (${r.message.response_time.toFixed(2)}ms)`;
					}
					if (r.message.error) {
						msg += ` - ${r.message.error}`;
					}
					frappe.show_alert({
						message: msg,
						indicator: indicator
					});
					frm.reload_doc();
				}
			}
		});
	},
	validate: function(frm) {
		if (frm.doc.db_name == undefined) {
			let key = frappe.datetime.get_datetime_as_string();
			console_dialog(key);
			frm.doc.key = key;
		}
	},
	refresh: function(frm) {
		$('a.grey-link:contains("Delete")').hide();

		if (frm.doc.db_name == undefined) {
			$('div.form-inner-toolbar').hide();
		} else {
			$('div.form-inner-toolbar').show();
		}

		frm.add_custom_button(__('Create Alias'), function(){
			var dialog = new frappe.ui.Dialog({
				title: __('Alias name'),
				fields: [
					{fieldname: 'alias', fieldtype: 'Data', reqd:true}
				]
			});
			dialog.set_primary_action(__('Create'), () => {
				let key = frappe.datetime.get_datetime_as_string();
				console_dialog(key);
				frm.call('create_alias', {
					key: key,
					alias: dialog.fields_dict.alias.value
				}, () => {
					dialog.hide();
				});
			});
			dialog.show();
		});
		frm.add_custom_button(__('Delete Alias'), function(){
			let alias_list = frm.doc.site_alias.split('\n');
			alias_list.pop();
			var dialog = new frappe.ui.Dialog({
				title: __('Alias name'),
				fields: [
					{fieldname: 'alias', fieldtype: 'Select', reqd:true, options:alias_list}
				]
			});
			dialog.set_primary_action(__('Delete'), () => {
				let key = frappe.datetime.get_datetime_as_string();
				console_dialog(key);
				frm.call('console_command', {
					key: key,
					caller: 'delete-alias',
					alias: dialog.fields_dict.alias.value
				}, () => {
					dialog.hide();
				});
			});
			dialog.show();
		});
		frm.add_custom_button(__('Migrate'), function() {
			let key = frappe.datetime.get_datetime_as_string();
			console_dialog(key);
			frm.call('console_command', {
				key: key,
				caller: 'migrate',
			});
		});
		frm.add_custom_button(__('Backup'), function() {
			let key = frappe.datetime.get_datetime_as_string();
			console_dialog(key);
			frm.call('console_command', {
				key: key,
				caller: 'backup',
			});
		});
		frm.add_custom_button(__('Reinstall'), function(){
			frappe.call({
				method: 'bench_manager.bench_manager.doctype.site.site.pass_exists',
				args: {
					doctype: frm.doctype,
					docname: frm.doc.name
				},
				btn: this,
				callback: function(r){
					var dialog = new frappe.ui.Dialog({
						title: __('Are you sure?'),
						fields: [
							{fieldname: 'admin_password', fieldtype: 'Password',
								label: 'Administrator Password', reqd: r['message']['condition'][0] != 'T',
								default: (r['message']['admin_password'] ? r['message']['admin_password'] :'admin'),
								depends_on: `eval:${String(r['message']['condition'][0] != 'T')}`}
						]
					});
					dialog.set_primary_action(__('Reinstall'), () => {
						let key = frappe.datetime.get_datetime_as_string();
						console_dialog(key);
						frm.call('console_command', {
							key: key,
							caller: 'reinstall',
							admin_password: dialog.fields_dict.admin_password.value
						}, () => {
							dialog.hide();
						});
					});
					dialog.show();
				}
			});
		});
		frm.add_custom_button(__('Install App'), function(){
			frappe.call({
				method: 'bench_manager.bench_manager.doctype.site.site.get_installable_apps',
				args: {
					doctype: frm.doctype,
					docname: frm.doc.name
				},
				btn: this,
				callback: function(r) {
					var dialog = new frappe.ui.Dialog({
						title: __('Select app'),
						fields: [
							{'fieldname': 'installable_apps', 'fieldtype': 'Select', options: r.message}
						],
					});
					dialog.set_primary_action(__('Install App'), () => {
						let key = frappe.datetime.get_datetime_as_string();
						console_dialog(key);
						frm.call('console_command', {
							key: key,
							caller: 'install_app',
							app_name: dialog.fields_dict.installable_apps.value
						}, () => {
							dialog.hide();
						});
					});
					dialog.show();
				}
			});
		});
		frm.add_custom_button(__('Uninstall App'), function(){
			frappe.call({
				method: 'bench_manager.bench_manager.doctype.site.site.get_removable_apps',
				args: {
					doctype: frm.doctype,
					docname: frm.doc.name
				},
				btn: this,
				callback: function(r) {
					var dialog = new frappe.ui.Dialog({
						title: __('Select app'),
						fields: [
							{'fieldname': 'removable_apps', 'fieldtype': 'Select', options: r.message},
						]
					});
					dialog.set_primary_action(__('Uninstall App'), () => {
						let key = frappe.datetime.get_datetime_as_string();
						console_dialog(key);
						frm.call('console_command', {
							key: key,
							caller: 'uninstall_app',
							app_name: dialog.fields_dict.removable_apps.value
						}, () => {
							dialog.hide();
						});
					});
					dialog.show();
				}
			});
		});
		frm.add_custom_button(__('Drop Site'), function(){
			frappe.call({
				method: 'bench_manager.bench_manager.doctype.site.site.pass_exists',
				args: {
					doctype: frm.doctype,
					docname: frm.doc.name
				},
				btn: this,
				callback: function (r) {
					var dialog = new frappe.ui.Dialog({
						title: __('Drop Site - Confirm'),
						fields: [
							{
								fieldname: 'mysql_password',
								fieldtype: 'Password',
								label: 'MySQL Root Password',
								reqd: r['message']['condition'][0] != 'T',
								default: r['message']['root_password'],
								depends_on: `eval:${String(r['message']['condition'][0] != 'T')}`
							},
							{
								fieldname: 'admin_password', 
								fieldtype: 'Password',
								label: 'Administrator Password', 
								reqd: r['message']['condition'][1] != 'T',
								default: (r['message']['admin_password'] ? r['message']['admin_password'] : 'admin'),
								depends_on: `eval:${String(r['message']['condition'][1] != 'T')}`
							},
							{
								fieldname: 'warning',
								fieldtype: 'HTML',
								options: '<div class="alert alert-danger"><strong>Warning:</strong> This will permanently delete the site and all its data. This action cannot be undone!</div>'
							}
						],
					});
					dialog.set_primary_action(__('Drop Site'), () => {
						let key = frappe.datetime.get_datetime_as_string();
						dialog.hide();
						
						// Verify MySQL password first
						frappe.call({
							method: 'bench_manager.bench_manager.doctype.site.site.verify_password',
							args: {
								site_name: frm.doc.name,
								mysql_password: dialog.fields_dict.mysql_password.value
							},
							callback: function(r){
								if (r.message == 'console'){
									// Open console dialog
									console_dialog(key);
									
									// Execute drop site command
									frm.call('console_command', {
										key: key,
										caller: 'drop_site',
										mysql_password: dialog.fields_dict.mysql_password.value
									}).then(() => {
										// Wait for command to complete, then delete the doc
										setTimeout(() => {
											frappe.msgprint({
												title: __('Site Dropped'),
												message: __('Site {0} has been dropped successfully. Deleting the document...', [frm.doc.name]),
												indicator: 'green'
											});
											// Delete the Site document
											frappe.call({
												method: 'frappe.client.delete',
												args: {
													doctype: 'Site',
													name: frm.doc.name
												},
												callback: function() {
													frappe.set_route('List', 'Site');
												}
											});
										}, 3000); // Wait 3 seconds for drop command to complete
									});
								}
							},
							error: function(r) {
								frappe.msgprint({
									title: __('Error'),
									message: __('Failed to verify MySQL password. Please check and try again.'),
									indicator: 'red'
								});
							}
						});
					});
					dialog.show();
				}
			});
		});
		frm.add_custom_button(__('View Site'), () => {
			// Use site_url if available, otherwise use site_name directly
			let url = frm.doc.site_url || `http://${frm.doc.name}`;
			window.open(url, '_blank');
		});
	}
});