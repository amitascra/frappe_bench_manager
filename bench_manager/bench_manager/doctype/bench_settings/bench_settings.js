// Copyright (c) 2017, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bench Settings', {
	onload: function(frm) {
		if (frm.doc.__islocal != 1) frm.save();
		let site_config_fields = ["background_workers", "shallow_clone", "admin_password",
			"auto_email_id", "auto_update", "frappe_user", "global_help_setup",
			"gunicorn_workers", "github_username",
			"github_password", "mail_login", "mail_password", "mail_port", "mail_server",
			"use_tls", "rebase_on_pull", "redis_cache", "redis_queue", "redis_socketio",
			"restart_supervisor_on_update", "root_password", "serve_default_site",
			"socketio_port", "update_bench_on_update", "webserver_port", "developer_mode",
			"file_watcher_port"];
		site_config_fields.forEach(function(val){
			frm.toggle_display(val, frm.doc[val] != undefined);
		});
	},
	refresh: function(frm) {
		frm.add_custom_button(__("Get App"), function(){
			var dialog = new frappe.ui.Dialog({
				title: 'App Name',
				fields: [
					{fieldname: 'app_name', fieldtype: 'Data', reqd:true, label: 'Name of the frappe repo hosted on github'}
				]
			});
			dialog.set_primary_action(__("Get App"), () => {
				let key = frappe.datetime.get_datetime_as_string();
				console_dialog(key);
				frm.call("console_command", {
					key: key,
					caller: 'get-app',
					app_name: dialog.fields_dict.app_name.value
				}, () => {
					dialog.hide();
				});
			});
			dialog.show();
		});
		frm.add_custom_button(__('New Site'), function(){
			frappe.call({
				method: 'bench_manager.bench_manager.doctype.site.site.pass_exists',
				args: {
					doctype: frm.doctype
				},
				btn: this,
				callback: function(r){
					var dialog = new frappe.ui.Dialog({
						fields: [
							{fieldname: 'site_name', fieldtype: 'Data', label: "Site Name", reqd: true},
							{fieldname: 'install_erpnext', fieldtype: 'Check', label: "Install ERPNext"},
							{fieldname: 'admin_password', fieldtype: 'Password',
								label: 'Administrator Password', reqd: r['message']['condition'][0] != 'T',
								default: (r['message']['admin_password'] ? r['message']['admin_password'] :'admin'),
								depends_on: `eval:${String(r['message']['condition'][0] != 'T')}`},
							{fieldname: 'mysql_password', fieldtype: 'Password',
								label: 'MySQL Password', reqd: r['message']['condition'][1] != 'T',
								default: r['message']['root_password'], depends_on: `eval:${String(r['message']['condition'][1] != 'T')}`}
						],
					});
					dialog.set_primary_action(__("Create"), () => {
						let key = frappe.datetime.get_datetime_as_string();
						let install_erpnext;
						if (dialog.fields_dict.install_erpnext.last_value != 1){
							install_erpnext = "false";
						} else {
							install_erpnext = "true";
						}
						frappe.call({
							method: 'bench_manager.bench_manager.doctype.site.site.verify_password',
							args: {
								site_name: dialog.fields_dict.site_name.value,
								mysql_password: dialog.fields_dict.mysql_password.value
							},
							callback: function(r){
								if (r.message == "console"){
									console_dialog(key);
									frappe.call({
										method: 'bench_manager.bench_manager.doctype.site.site.create_site',
										args: {
											site_name: dialog.fields_dict.site_name.value,
											admin_password: dialog.fields_dict.admin_password.value,
											mysql_password: dialog.fields_dict.mysql_password.value,
											install_erpnext: install_erpnext,
											key: key
										}
									});
									dialog.hide();
								} 
							}
						});
					});
					dialog.show();
				}
			});
		});
		frm.add_custom_button(__("Update"), function(){
			let key = frappe.datetime.get_datetime_as_string();
			console_dialog(key);
			frm.call("console_command", {
				key: key,
				caller: "bench_update"
			});
		});
		frm.add_custom_button(__('Sync'), () => {
			frappe.call({
				method: 'bench_manager.bench_manager.doctype.bench_settings.bench_settings.sync_all'
			});
		});
		frm.add_custom_button(__('App Debugger'), () => {
			show_app_debugger_dialog();
		});
		frm.add_custom_button("Reload", () => {
			frappe.prompt([
	  {
		  label: 'Root Password',
		  fieldname: 'password',
		  fieldtype: 'Password'
	  },
		  ], (values) => {
		  frappe.call({
				  method: "bench_manager.bench_manager.doctype.bench_settings.bench_settings.setup_and_restart_nginx",
				  args: {
					  "root_password": values.password
				  }
			  });
		  })
		});
	},
	allow_dropbox_access: function(frm) {
		if (frm.doc.app_access_key && frm.doc.app_secret_key) {
			frappe.call({
				method: "bench_manager.bench_manager.doctype.bench_settings.bench_settings.get_dropbox_authorize_url",
				freeze: true,
				callback: function(r) {
					if(!r.exc) {
						window.open(r.message.auth_url);
					}
				}
			})
		}
		else if (frm.doc.__onload && frm.doc.__onload.dropbox_setup_via_site_config) {
			frappe.call({
				method: "bench_manager.bench_manager.doctype.bench_settings.bench_settings.get_redirect_url",
				freeze: true,
				callback: function(r) {
					if(!r.exc) {
						window.open(r.message.auth_url);
					}
				}
			})
		}
		else {
			frappe.msgprint(__("Please enter values for App Access Key and App Secret Key"))
		}
	}
});

window.show_app_debugger_dialog = function() {
	frappe.call({
		method: 'bench_manager.bench_manager.doctype.bench_settings.bench_settings.get_app_debug_info',
		freeze: true,
		freeze_message: __('Scanning apps...'),
		callback: function(r) {
			if (!r.exc && r.message) {
				let data = r.message;
				
				// Create dialog
				let dialog = new frappe.ui.Dialog({
					title: __('App Debugger - PKG-INFO Status'),
					size: 'extra-large',
					fields: [
						{
							fieldtype: 'HTML',
							fieldname: 'summary_html'
						},
						{
							fieldtype: 'HTML',
							fieldname: 'apps_html'
						}
					],
					primary_action_label: __('Fix All Missing'),
					primary_action: function() {
						fix_all_missing_pkg_info(dialog, data);
					}
				});
				
				// Summary section
				let summary_html = `
					<div class="app-debugger-summary" style="margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px;">
						<h4 style="margin-top: 0;">Summary</h4>
						<div class="row">
							<div class="col-md-4">
								<div style="text-align: center; padding: 10px;">
									<div style="font-size: 32px; font-weight: bold; color: #5e64ff;">${data.total_apps}</div>
									<div style="color: #6c757d;">Total Apps</div>
								</div>
							</div>
							<div class="col-md-4">
								<div style="text-align: center; padding: 10px;">
									<div style="font-size: 32px; font-weight: bold; color: #28a745;">${data.apps_with_pkg_info}</div>
									<div style="color: #6c757d;">With PKG-INFO</div>
								</div>
							</div>
							<div class="col-md-4">
								<div style="text-align: center; padding: 10px;">
									<div style="font-size: 32px; font-weight: bold; color: #dc3545;">${data.apps_missing_pkg_info}</div>
									<div style="color: #6c757d;">Missing PKG-INFO</div>
								</div>
							</div>
						</div>
					</div>
				`;
				
				// Apps table
				let apps_html = `
					<div class="app-debugger-apps">
						<h4>App Details</h4>
						<table class="table table-bordered" style="margin-top: 10px;">
							<thead>
								<tr>
									<th style="width: 20%;">App Name</th>
									<th style="width: 15%;">Status</th>
									<th style="width: 15%;">Version</th>
									<th style="width: 35%;">Details</th>
									<th style="width: 15%;">Action</th>
								</tr>
							</thead>
							<tbody>
				`;
				
				data.apps.forEach(app => {
					let status_badge = '';
					let action_btn = '';
					
					if (app.status === 'OK') {
						status_badge = '<span class="badge badge-success">OK</span>';
						action_btn = '<span class="text-muted">No action needed</span>';
					} else if (app.status === 'Missing PKG-INFO') {
						status_badge = '<span class="badge badge-warning">Missing PKG-INFO</span>';
						action_btn = `<button class="btn btn-xs btn-primary" onclick="window.fix_single_app('${app.app_name}')">Generate PKG-INFO</button>`;
					} else {
						status_badge = '<span class="badge badge-danger">Missing egg-info</span>';
						action_btn = `<button class="btn btn-xs btn-primary" onclick="window.fix_single_app('${app.app_name}')">Generate PKG-INFO</button>`;
					}
					
					apps_html += `
						<tr>
							<td><strong>${app.app_name}</strong></td>
							<td>${status_badge}</td>
							<td>${app.version || '<span class="text-muted">N/A</span>'}</td>
							<td><small>${app.details}</small></td>
							<td>${action_btn}</td>
						</tr>
					`;
				});
				
				apps_html += `
							</tbody>
						</table>
					</div>
				`;
				
				dialog.fields_dict.summary_html.$wrapper.html(summary_html);
				dialog.fields_dict.apps_html.$wrapper.html(apps_html);
				
				// Hide primary action if no missing apps
				if (data.apps_missing_pkg_info === 0) {
					dialog.set_primary_action_label(__('Close'));
					dialog.set_primary_action(function() {
						dialog.hide();
					});
				}
				
				dialog.show();
			}
		}
	});
}

window.fix_single_app = function(app_name) {
	frappe.call({
		method: 'bench_manager.bench_manager.doctype.bench_settings.bench_settings.generate_pkg_info',
		args: {
			app_name: app_name
		},
		freeze: true,
		freeze_message: __('Generating PKG-INFO for {0}...', [app_name]),
		callback: function(r) {
			if (!r.exc && r.message) {
				if (r.message.success) {
					frappe.show_alert({
						message: r.message.message,
						indicator: 'green'
					}, 5);
					// Refresh the dialog
					setTimeout(() => {
						show_app_debugger_dialog();
					}, 1000);
				} else {
					frappe.msgprint({
						title: __('Error'),
						message: r.message.message + '<br><br>' + 
							(r.message.error ? '<pre>' + r.message.error + '</pre>' : ''),
						indicator: 'red'
					});
				}
			}
		}
	});
}

window.fix_all_missing_pkg_info = function(dialog, data) {
	frappe.confirm(
		__('This will run "pip install -e ." for all apps missing PKG-INFO. Continue?'),
		function() {
			frappe.call({
				method: 'bench_manager.bench_manager.doctype.bench_settings.bench_settings.generate_all_missing_pkg_info',
				freeze: true,
				freeze_message: __('Generating PKG-INFO for all missing apps...'),
				callback: function(r) {
					if (!r.exc && r.message) {
						let success_count = 0;
						let fail_count = 0;
						
						r.message.results.forEach(result => {
							if (result.result.success) {
								success_count++;
							} else {
								fail_count++;
							}
						});
						
						let message = `
							<div>
								<p><strong>PKG-INFO Generation Complete</strong></p>
								<p>✓ Success: ${success_count}</p>
								<p>✗ Failed: ${fail_count}</p>
							</div>
						`;
						
						frappe.msgprint({
							title: __('Results'),
							message: message,
							indicator: fail_count === 0 ? 'green' : 'orange'
						});
						
						dialog.hide();
						
						// Refresh the dialog after a moment
						setTimeout(() => {
							show_app_debugger_dialog();
						}, 1500);
					}
				}
			});
		}
	);
}