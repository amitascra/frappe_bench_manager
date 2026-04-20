// Copyright (c) 2017, Frappé and contributors
// For license information, please see license.txt

frappe.ui.form.on('Site', {
	onload: function(frm) {
		// Don't auto-save on load - causes frequent connection checks
		// User can manually refresh if needed
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
					let msg = `Overall Status: ${r.message.overall_status}`;
					
					// Add HTTP status
					if (r.message.protocols && r.message.protocols.http) {
						let http_status = r.message.protocols.http.status;
						let http_indicator = http_status === 'Online' ? '✓' : '✗';
						let http_time = r.message.protocols.http.response_time ? ` (${r.message.protocols.http.response_time.toFixed(2)}ms)` : '';
						msg += `\nHTTP: ${http_indicator} ${http_status}${http_time}`;
					}
					
					// Add HTTPS status
					if (r.message.protocols && r.message.protocols.https) {
						let https_status = r.message.protocols.https.status;
						let https_indicator = https_status === 'Online' ? '✓' : '✗';
						let https_time = r.message.protocols.https.response_time ? ` (${r.message.protocols.https.response_time.toFixed(2)}ms)` : '';
						msg += `\nHTTPS: ${https_indicator} ${https_status}${https_time}`;
					}
					
					// Add SSL info
					if (r.message.has_ssl) {
						msg += `\nSSL: Enabled`;
					}
					
					let indicator = r.message.overall_status === 'Online' ? 'green' : 'red';
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

		// === SITE ACTIONS GROUP ===
		frm.add_custom_button(__('View Site'), () => {
			let url = frm.doc.site_url || `http://${frm.doc.name}`;
			window.open(url, '_blank');
		}, __('Site Actions'));
		
		frm.add_custom_button(__('Check Status'), function() {
			frm.events.check_status_button(frm);
		}, __('Site Actions'));
		
		frm.add_custom_button(__('Refresh Apps'), function() {
			frm.call('update_app_alias', {}, () => {
				frappe.show_alert({
					message: __('App list and aliases refreshed'),
					indicator: 'green'
				});
				frm.reload_doc();
			});
		}, __('Site Actions'));
		
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
		}, __('Site Actions'));
		
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
		}, __('Site Actions'));

		frm.add_custom_button(__('Install SSL'), function(){
			let key = frappe.datetime.get_datetime_as_string();
			console_dialog(key);
			frm.call('console_command', {
				key: key,
				caller: 'install_ssl',
			});
		}, __('Site Actions'));

		// === APP MANAGEMENT GROUP ===
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
		}, __('App Management'));
		
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
		}, __('App Management'));

		// === MAINTENANCE GROUP ===
		frm.add_custom_button(__('Migrate'), function() {
			let key = frappe.datetime.get_datetime_as_string();
			console_dialog(key);
			frm.call('console_command', {
				key: key,
				caller: 'migrate',
			});
		}, __('Maintenance'));
		
		frm.add_custom_button(__('Backup'), function() {
			let key = frappe.datetime.get_datetime_as_string();
			console_dialog(key);
			frm.call('console_command', {
				key: key,
				caller: 'backup',
			});
		}, __('Maintenance'));
		
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
						title: __('Reinstall Site - Warning: All data will be lost!'),
						fields: [
							{fieldname: 'warning', fieldtype: 'HTML',
								options: '<div style="padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107; margin-bottom: 15px;"><strong>⚠️ Warning:</strong> This will completely reinstall the site and <strong>all data will be lost</strong>. Make sure you have a backup!</div>'},
							{fieldname: 'admin_password', fieldtype: 'Password',
								label: 'Administrator Password', reqd: r['message']['condition'][0] != 'T',
								default: (r['message']['admin_password'] ? r['message']['admin_password'] :'admin'),
								depends_on: `eval:${String(r['message']['condition'][0] != 'T')}`},
							{fieldname: 'mysql_password', fieldtype: 'Password',
								label: 'MySQL Root Password', reqd: r['message']['condition'][1] != 'T',
								default: r['message']['root_password'],
								depends_on: `eval:${String(r['message']['condition'][1] != 'T')}`}
						]
					});
					dialog.set_primary_action(__('Reinstall'), () => {
						let key = frappe.datetime.get_datetime_as_string();
						console_dialog(key);
						frm.call('console_command', {
							key: key,
							caller: 'reinstall',
							admin_password: dialog.fields_dict.admin_password.value,
							mysql_password: dialog.fields_dict.mysql_password.value
						}, () => {
							dialog.hide();
						});
					});
					dialog.show();
				}
			});
		}, __('Maintenance'));
		
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
								fieldname: 'warning',
								fieldtype: 'HTML',
								options: '<div class="alert alert-danger" style="margin-bottom: 15px;"><strong>⚠️ Warning:</strong> This will permanently delete the site and all its data. This action cannot be undone!</div>'
							},
							{
								fieldname: 'mysql_password',
								fieldtype: 'Password',
								label: 'MySQL Root Password',
								reqd: r['message']['condition'][0] != 'T',
								default: r['message']['root_password'],
								description: 'Enter MySQL root password to confirm site deletion',
								depends_on: `eval:${String(r['message']['condition'][0] != 'T')}`
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
		}, __('Maintenance'));
	}
});