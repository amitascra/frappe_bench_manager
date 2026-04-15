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
			// Get system info first
			frappe.call({
				method: 'bench_manager.bench_manager.doctype.site.site.get_system_info',
				callback: function(sys_info) {
					const system_data = sys_info.message;
					
					frappe.call({
						method: 'bench_manager.bench_manager.doctype.site.site.pass_exists',
						args: {
							doctype: frm.doctype
						},
						btn: this,
						callback: function(r){
							var dialog = new frappe.ui.Dialog({
								title: __('Create New Site'),
								fields: [
									// System Info Display
									{fieldname: 'system_info', fieldtype: 'HTML',
										options: `
											<div style="padding: 12px; background: #f8f9fa; border-radius: 6px; margin-bottom: 15px; border-left: 4px solid ${system_data.disk_available ? '#28a745' : '#dc3545'};">
												<div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
													<span style="font-weight: 500; color: #495057;"><i class="fa fa-hdd-o"></i> Available Disk Space:</span>
													<span style="font-weight: 600; color: ${system_data.disk_available ? '#28a745' : '#dc3545'}">
														${system_data.disk_space_gb} GB
													</span>
												</div>
												<div style="display: flex; justify-content: space-between;">
													<span style="font-weight: 500; color: #495057;"><i class="fa fa-clock-o"></i> Estimated Time:</span>
													<span id="estimated-time" style="font-weight: 600; color: #6c757d;">${system_data.estimated_time_minutes} minutes</span>
												</div>
												${system_data.warning ? `<div style="color: #dc3545; margin-top: 10px; font-size: 13px;"><i class="fa fa-exclamation-triangle"></i> ${system_data.warning}</div>` : ''}
											</div>
										`},
									
									// Site Name with validation
									{fieldname: 'site_name', fieldtype: 'Data', label: "Site Name", reqd: true,
										description: "e.g., mycompany.localhost (lowercase letters, numbers, dots, hyphens only)"},
									
									// Validation feedback
									{fieldname: 'site_name_feedback', fieldtype: 'HTML',
										options: '<div id="site-name-feedback" style="margin-top: -10px; margin-bottom: 10px;"></div>'},
									
									// Suggestions
									{fieldname: 'suggestions', fieldtype: 'HTML',
										options: '<div id="site-suggestions"></div>'},
									
									// ERPNext checkbox
									{fieldname: 'install_erpnext', fieldtype: 'Check', label: "Install ERPNext"},
									
									// Admin Password
									{fieldname: 'admin_password', fieldtype: 'Password',
										label: 'Administrator Password', reqd: r['message']['condition'][0] != 'T',
										default: (r['message']['admin_password'] ? r['message']['admin_password'] :'admin'),
										depends_on: `eval:${String(r['message']['condition'][0] != 'T')}`},
									
									// Password strength indicator
									{fieldname: 'password_strength', fieldtype: 'HTML',
										options: '<div id="password-strength" style="margin-top: -10px; margin-bottom: 10px;"></div>',
										depends_on: `eval:${String(r['message']['condition'][0] != 'T')}`},
									
									// MySQL Password
									{fieldname: 'mysql_password', fieldtype: 'Password',
										label: 'MySQL Password', reqd: r['message']['condition'][1] != 'T',
										default: r['message']['root_password'], 
										depends_on: `eval:${String(r['message']['condition'][1] != 'T')}`}
								],
							});
							
							// Site name validation on change
							let validation_timeout;
							let site_name_valid = false;
							
							dialog.fields_dict.site_name.$input.on('input', function() {
								const site_name = $(this).val().toLowerCase();
								$(this).val(site_name); // Force lowercase
								
								clearTimeout(validation_timeout);
								
								if (!site_name) {
									$('#site-name-feedback').html('');
									$('#site-suggestions').html('');
									site_name_valid = false;
									return;
								}
								
								// Show checking indicator
								$('#site-name-feedback').html(`
									<div style="color: #6c757d; font-size: 12px;">
										<i class="fa fa-spinner fa-spin"></i> Checking availability...
									</div>
								`);
								
								validation_timeout = setTimeout(() => {
									frappe.call({
										method: 'bench_manager.bench_manager.doctype.site.site.check_site_name_available',
										args: {site_name: site_name},
										callback: function(r) {
											const result = r.message;
											let feedback_html = '';
											let suggestions_html = '';
											
											if (!result.valid) {
												feedback_html = `
													<div style="color: #dc3545; font-size: 12px;">
														<i class="fa fa-times-circle"></i> ${result.message}
													</div>
												`;
												site_name_valid = false;
											} else if (!result.available) {
												feedback_html = `
													<div style="color: #dc3545; font-size: 12px;">
														<i class="fa fa-times-circle"></i> ${result.message}
													</div>
												`;
												site_name_valid = false;
												
												// Show suggestions
												if (result.suggestions.length > 0) {
													suggestions_html = `
														<div style="margin-bottom: 15px; padding: 10px; background: #fff3cd; border-radius: 4px; border-left: 3px solid #ffc107;">
															<div style="font-size: 12px; color: #856404; margin-bottom: 8px;"><strong>Suggestions:</strong></div>
															<div style="display: flex; gap: 8px; flex-wrap: wrap;">
																${result.suggestions.map(s => `
																	<button class="btn btn-xs btn-default" onclick="
																		cur_dialog.set_value('site_name', '${s}');
																		cur_dialog.fields_dict.site_name.$input.trigger('input');
																	" style="font-size: 11px;">${s}</button>
																`).join('')}
															</div>
														</div>
													`;
												}
											} else {
												feedback_html = `
													<div style="color: #28a745; font-size: 12px;">
														<i class="fa fa-check-circle"></i> ${result.message}
													</div>
												`;
												site_name_valid = true;
											}
											
											$('#site-name-feedback').html(feedback_html);
											$('#site-suggestions').html(suggestions_html);
										}
									});
								}, 500);
							});
							
							// Password strength indicator
							if (r['message']['condition'][0] != 'T') {
								dialog.fields_dict.admin_password.$input.on('keyup', function() {
									const password = $(this).val();
									if (!password) {
										$('#password-strength').html('');
										return;
									}
									
									// Calculate strength
									let strength = 0;
									let feedback = [];
									
									if (password.length >= 8) strength++; else feedback.push('at least 8 characters');
									if (/[a-z]/.test(password)) strength++; else feedback.push('lowercase letter');
									if (/[A-Z]/.test(password)) strength++; else feedback.push('uppercase letter');
									if (/[0-9]/.test(password)) strength++; else feedback.push('number');
									if (/[^a-zA-Z0-9]/.test(password)) strength++; else feedback.push('special character');
									
									let color, text, barWidth;
									if (strength <= 2) {
										color = '#dc3545'; text = 'Weak'; barWidth = '33%';
									} else if (strength <= 3) {
										color = '#ffc107'; text = 'Medium'; barWidth = '66%';
									} else {
										color = '#28a745'; text = 'Strong'; barWidth = '100%';
									}
									
									let html = `
										<div style="font-size: 12px; margin-bottom: 5px;">
											<div style="display: flex; justify-content: space-between; align-items: center;">
												<span style="color: #6c757d;">Password Strength:</span>
												<span style="color: ${color}; font-weight: 600;">${text}</span>
											</div>
											<div style="height: 4px; background: #e9ecef; border-radius: 2px; margin-top: 5px; overflow: hidden;">
												<div style="height: 100%; background: ${color}; width: ${barWidth}; transition: width 0.3s;"></div>
											</div>
											${feedback.length > 0 ? `<div style="color: #6c757d; font-size: 11px; margin-top: 5px;">Add: ${feedback.join(', ')}</div>` : ''}
										</div>
									`;
									
									$('#password-strength').html(html);
								});
							}
							
							// Update estimated time when ERPNext checkbox changes
							dialog.fields_dict.install_erpnext.$input.on('change', function() {
								const install = $(this).is(':checked');
								const time = install ? 5 : 2;
								$('#estimated-time').text(time + ' minutes');
							});
							
							dialog.set_primary_action(__("Create"), () => {
								// Validate site name before proceeding
								if (!site_name_valid) {
									frappe.msgprint({
										title: __('Invalid Site Name'),
										message: __('Please enter a valid and available site name'),
										indicator: 'red'
									});
									return;
								}
								
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