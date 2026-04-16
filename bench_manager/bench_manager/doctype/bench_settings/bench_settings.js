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
			// Get system info and available apps
			frappe.call({
				method: 'bench_manager.bench_manager.doctype.site.site.get_system_info',
				callback: function(sys_info) {
					const system_data = sys_info.message;
					
					// Get available apps
					frappe.call({
						method: 'bench_manager.bench_manager.doctype.site.site.get_available_apps',
						callback: function(apps_response) {
							const available_apps = apps_response.message || [];
					
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
									
									// Apps Selection
									{fieldname: 'apps_section', fieldtype: 'Section Break', label: "Select Apps to Install"},
									{fieldname: 'apps_selector', fieldtype: 'HTML',
										options: `
											<div id="apps-selector" style="margin-bottom: 15px;">
												${available_apps.length === 0 ? 
													'<div style="padding: 20px; text-align: center; color: #6c757d;"><i class="fa fa-info-circle"></i> No apps available. Please sync apps first.</div>' :
													`<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 12px;">
														${available_apps.map(app => `
															<div class="app-card" data-app="${app.name}" style="
																border: 2px solid #e9ecef;
																border-radius: 8px;
																padding: 12px;
																cursor: pointer;
																transition: all 0.2s;
																position: relative;
															">
																${app.is_popular ? '<div style="position: absolute; top: 8px; right: 8px; background: #ffc107; color: #000; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: 600;">POPULAR</div>' : ''}
																<div style="display: flex; align-items: start; gap: 10px;">
																	<input type="checkbox" class="app-checkbox" data-app="${app.name}" style="margin-top: 2px;">
																	<div style="flex: 1;">
																		<div style="font-weight: 600; color: #495057; margin-bottom: 4px;">${app.display_name}</div>
																		<div style="font-size: 11px; color: #6c757d; line-height: 1.4;">${app.description.substring(0, 80)}${app.description.length > 80 ? '...' : ''}</div>
																		${app.version ? `<div style="font-size: 10px; color: #28a745; margin-top: 4px;">v${app.version}</div>` : ''}
																	</div>
																</div>
															</div>
														`).join('')}
													</div>
													<style>
														.app-card:hover {
															border-color: #5e64ff !important;
															background: #f8f9ff;
														}
														.app-card.selected {
															border-color: #5e64ff !important;
															background: #f0f1ff;
														}
													</style>`
												}
											</div>
										`},
									{fieldname: 'selected_apps_info', fieldtype: 'HTML',
										options: '<div id="selected-apps-info" style="margin-top: 10px; padding: 10px; background: #e7f3ff; border-radius: 4px; display: none;"></div>'},
									
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
							
							// Handle app selection
							let selected_apps = [];
							
							// Click on card to toggle selection
							$(document).on('click', '.app-card', function(e) {
								if (e.target.type !== 'checkbox') {
									const checkbox = $(this).find('.app-checkbox');
									checkbox.prop('checked', !checkbox.prop('checked')).trigger('change');
								}
							});
							
							// Handle checkbox change
							$(document).on('change', '.app-checkbox', function() {
								const app_name = $(this).data('app');
								const card = $(this).closest('.app-card');
								
								if ($(this).is(':checked')) {
									card.addClass('selected');
									if (!selected_apps.includes(app_name)) {
										selected_apps.push(app_name);
									}
								} else {
									card.removeClass('selected');
									selected_apps = selected_apps.filter(a => a !== app_name);
								}
								
								// Update selected apps info
								if (selected_apps.length > 0) {
									$('#selected-apps-info').html(`
										<div style="font-size: 12px;">
											<strong><i class="fa fa-check-circle" style="color: #28a745;"></i> ${selected_apps.length} app${selected_apps.length > 1 ? 's' : ''} selected:</strong>
											<span style="color: #495057;"> ${selected_apps.join(', ')}</span>
										</div>
									`).show();
								} else {
									$('#selected-apps-info').hide();
								}
								
								// Update estimated time (2 min base + 2 min per app)
								const time = 2 + (selected_apps.length * 2);
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
													apps_to_install: JSON.stringify(selected_apps),
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
			}
		});
	});
		// === BENCH OPERATIONS GROUP ===
	frm.add_custom_button(__('Restart Bench'), function() {
		frappe.confirm(
			__('This will restart all bench services (web, workers, scheduler). Continue?'),
			() => {
				let key = frappe.datetime.get_datetime_as_string();
				console_dialog(key);
				frm.call('console_command', {
					key: key,
					caller: 'bench_restart'
				});
			}
		);
	}, __('Bench Operations'));
	
	frm.add_custom_button(__('Bench Status'), function() {
		let key = frappe.datetime.get_datetime_as_string();
		console_dialog(key);
		frm.call('console_command', {
			key: key,
			caller: 'bench_status'
		});
	}, __('Bench Operations'));
	
	frm.add_custom_button(__('Update Bench'), function() {
			frappe.confirm(
				__('This will update all apps and may take several minutes. Continue?'),
				() => {
					let key = frappe.datetime.get_datetime_as_string();
					console_dialog(key);
					frm.call('console_command', {
						key: key,
						caller: 'bench_update'
					});
				}
			);
		}, __('Bench Operations'));
		
		frm.add_custom_button(__('Clear Cache'), function() {
			let key = frappe.datetime.get_datetime_as_string();
			console_dialog(key);
			frm.call('console_command', {
				key: key,
				caller: 'bench_clear_cache'
			});
		}, __('Bench Operations'));
		
		frm.add_custom_button(__('Setup Requirements'), function() {
			frappe.confirm(
				__('This will install/update Python dependencies. Continue?'),
				() => {
					let key = frappe.datetime.get_datetime_as_string();
					console_dialog(key);
					frm.call('console_command', {
						key: key,
						caller: 'bench_setup_requirements'
					});
				}
			);
		}, __('Bench Operations'));
		
		frm.add_custom_button(__('Build Assets'), function() {
			let key = frappe.datetime.get_datetime_as_string();
			console_dialog(key);
			frm.call('console_command', {
				key: key,
				caller: 'bench_build'
			});
		}, __('Bench Operations'));
		
		// === CONFIGURATION GROUP ===
		// Generate SSH Keys Button
		frm.add_custom_button(__('Generate SSH Keys'), () => {
			frappe.confirm(
				__('This will generate new SSH keys for GitHub authentication. Continue?'),
				() => {
					frappe.call({
						method: 'bench_manager.bench_manager.doctype.bench_settings.bench_settings.generate_ssh_keys',
						freeze: true,
						freeze_message: __('Generating SSH keys...'),
						callback: function(r) {
							if (r.message && r.message.success) {
								frappe.msgprint({
									title: __('SSH Keys Generated'),
									message: `<div style="margin-bottom: 15px;">
										<strong>✓ ${r.message.message}</strong>
									</div>
									<div style="padding: 10px; background: #f8f9fa; border-radius: 4px; margin-bottom: 10px;">
										<strong>Public Key:</strong><br>
										<textarea readonly style="width: 100%; height: 80px; font-family: monospace; font-size: 11px; margin-top: 5px;">${r.message.public_key}</textarea>
									</div>
									<div style="padding: 10px; background: #fff3cd; border-radius: 4px;">
										<strong>Next Steps:</strong>
										<ol style="margin: 5px 0 0 20px; padding-left: 0;">
											<li>Copy the public key above</li>
											<li>Go to <a href="https://github.com/settings/ssh/new" target="_blank">GitHub SSH Settings</a></li>
											<li>Add the public key</li>
											<li>Click "Test SSH Connection" to verify</li>
										</ol>
									</div>`,
									indicator: 'green',
									primary_action: {
										label: __('Reload'),
										action: () => frm.reload_doc()
									}
								});
							} else {
								frappe.msgprint({
									title: __('Error'),
									message: r.message.error,
									indicator: 'red'
								});
							}
						}
					});
				}
			);
		}, __('Configuration'));
		
		// Test SSH Connection Button
		frm.add_custom_button(__('Test SSH Connection'), () => {
			frappe.call({
				method: 'bench_manager.bench_manager.doctype.bench_settings.bench_settings.test_ssh_connection',
				freeze: true,
				freeze_message: __('Testing SSH connection...'),
				callback: function(r) {
					if (r.message && r.message.success) {
						frappe.msgprint({
							title: __('Connection Successful'),
							message: `<div style="color: #28a745; margin-bottom: 10px;">
								<strong>✓ ${r.message.message}</strong>
							</div>
							<div style="padding: 10px; background: #f8f9fa; border-radius: 4px; font-family: monospace; font-size: 11px;">
								${r.message.output}
							</div>`,
							indicator: 'green',
							primary_action: {
								label: __('Reload'),
								action: () => frm.reload_doc()
							}
						});
					} else {
						frappe.msgprint({
							title: __('Connection Failed'),
							message: `<div style="color: #dc3545; margin-bottom: 10px;">
								<strong>✗ ${r.message.error}</strong>
							</div>
							${r.message.output ? `<div style="padding: 10px; background: #f8f9fa; border-radius: 4px; font-family: monospace; font-size: 11px;">${r.message.output}</div>` : ''}`,
							indicator: 'red'
						});
					}
				}
			});
		}, __('Configuration'));
		
		// Search GitHub Repos Button
		frm.add_custom_button(__('Search GitHub Repos'), () => {
			let currentPage = 1;
			let allRepositories = [];
			let totalCount = 0;
			let currentKeyword = '';
			
			const dialog = new frappe.ui.Dialog({
				title: __('Search GitHub Repositories'),
				size: 'large',
				fields: [
					{
						fieldname: 'keyword',
						fieldtype: 'Data',
						label: __('Search Keyword'),
						reqd: 1,
						description: __('Enter keyword to search repositories (e.g., frappe, ecommerce, python)')
					},
					{
						fieldname: 'language',
						fieldtype: 'Select',
						label: __('Language (Optional)'),
						options: '',
						description: __('Filter by programming language')
					},
					{
						fieldname: 'sort_by',
						fieldtype: 'Select',
						label: __('Sort By'),
						options: 'stars\nforks\nupdated',
						default: 'stars'
					},
					{
						fieldname: 'results_area',
						fieldtype: 'HTML',
						options: '<div id="github-search-results" style="max-height: 500px; overflow-y: auto; padding-right: 10px;"></div>'
					}
				],
				primary_action_label: __('Search'),
				primary_action: (values) => {
					// Reset for new search
					currentPage = 1;
					allRepositories = [];
					currentKeyword = values.keyword;
					
					$('#github-search-results').html(`
						<div style="padding: 20px; text-align: center;">
							<i class="fa fa-spinner fa-spin" style="font-size: 24px;"></i>
							<div style="margin-top: 10px; color: #6c757d;">Searching GitHub repositories...</div>
						</div>
					`);
					
					loadPage(values, 1);
				}
			});
			
			function loadPage(values, page) {
				frappe.call({
					method: 'bench_manager.bench_manager.doctype.bench_settings.bench_settings.search_github_repos',
					args: {
						keyword: values.keyword,
						language: values.language || null,
						sort: values.sort_by || 'stars',
						page: page
					},
					callback: function(r) {
						if (r.message && r.message.success) {
							const repos = r.message.repositories;
							totalCount = r.message.total_count;
							
							// Append new results
							allRepositories = allRepositories.concat(repos);
							
							renderResults();
						} else {
							$('#github-search-results').html(`
								<div style="padding: 20px; background: #f8d7da; border-radius: 6px; color: #721c24;">
									<strong>Error:</strong> ${r.message.error}
								</div>
							`);
						}
					}
				});
			}
			
			function renderResults() {
				let resultsHTML = `
					<div style="padding: 15px; background: #e7f3ff; border-radius: 6px; margin-bottom: 15px;">
						<strong>Found ${totalCount.toLocaleString()} repositories for "${currentKeyword}"</strong>
						<div style="font-size: 12px; color: #6c757d; margin-top: 5px;">Showing ${allRepositories.length} results</div>
					</div>
				`;
				
				allRepositories.forEach(repo => {
					const stars = repo.stars.toLocaleString();
					const forks = repo.forks.toLocaleString();
					const updated = new Date(repo.updated_at).toLocaleDateString();
					const languageColors = {
						'Python': '#3572A5', 'JavaScript': '#f1e05a', 'TypeScript': '#2b7489',
						'PHP': '#4F5D95', 'Ruby': '#701516', 'Go': '#00ADD8',
						'Java': '#b07219', 'C++': '#f34b7d', 'C#': '#239120',
						'HTML': '#e34c26', 'CSS': '#563d7c', 'Shell': '#89e051',
						'Vue': '#41b883', 'React': '#61dafb', 'Rust': '#dea584'
					};
					const languageBadge = repo.language !== 'Unknown' 
						? `<span style="background: ${languageColors[repo.language] || '#6c757d'}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-right: 5px;">${repo.language}</span>` 
						: '';
					
					resultsHTML += `
						<div style="padding: 15px; background: #f8f9fa; border-radius: 6px; margin-bottom: 10px; border-left: 4px solid #5e64ff;">
							<div style="display: flex; justify-content: space-between; align-items: flex-start;">
								<div style="flex: 1;">
									<a href="${repo.url}" target="_blank" style="font-size: 16px; font-weight: 600; color: #5e64ff; text-decoration: none;">
										${repo.full_name}
									</a>
									<div style="margin-top: 5px; color: #6c757d; font-size: 13px;">${repo.description}</div>
									<div style="margin-top: 10px; display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
										${languageBadge}
										<span style="font-size: 12px; color: #6c757d;">
											<i class="fa fa-star" style="color: #ffc107;"></i> ${stars}
										</span>
										<span style="font-size: 12px; color: #6c757d;">
											<i class="fa fa-code-fork" style="color: #6c757d;"></i> ${forks}
										</span>
										<span style="font-size: 12px; color: #6c757d;">
											<i class="fa fa-clock-o" style="color: #6c757d;"></i> Updated: ${updated}
										</span>
									</div>
									<div style="margin-top: 10px; padding: 8px; background: #f8f9fa; border-radius: 4px; border: 1px solid #dee2e6;">
										<div style="display: flex; align-items: center; gap: 10px;">
											<span style="font-size: 11px; color: #6c757d; font-weight: 600;">Clone URL:</span>
											<input type="text" readonly value="https://github.com/${repo.full_name}.git" id="clone-url-${repo.name}" style="flex: 1; padding: 4px 8px; border: 1px solid #ced4da; border-radius: 4px; font-size: 11px; background: white; font-family: monospace;">
											<button class="copy-clone-btn" data-clone-url="https://github.com/${repo.full_name}.git" style="padding: 4px 12px; background: #5e64ff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 11px;">
												<i class="fa fa-copy"></i> Copy
											</button>
										</div>
									</div>
								</div>
							</div>
						</div>
					`;
				});
				
				// Add Load More button if more results available
				if (allRepositories.length < totalCount) {
					resultsHTML += `
						<div style="text-align: center; padding: 20px;">
							<button id="load-more-btn" style="padding: 10px 30px; background: #5e64ff; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600;">
								Load More (${allRepositories.length + 100} / ${totalCount.toLocaleString()})
							</button>
						</div>
					`;
				}
				
				$('#github-search-results').html(resultsHTML);
				
				// Attach click handler to Load More button
				$('#load-more-btn').on('click', function() {
					currentPage++;
					$(this).html('<i class="fa fa-spinner fa-spin"></i> Loading...');
					loadPage(dialog.get_values(), currentPage);
				});
				
				// Attach click handler to copy buttons
				$('.copy-clone-btn').on('click', function() {
					const cloneUrl = $(this).data('clone-url');
					navigator.clipboard.writeText(cloneUrl).then(() => {
						const originalHTML = $(this).html();
						$(this).html('<i class="fa fa-check"></i> Copied!');
						setTimeout(() => {
							$(this).html(originalHTML);
						}, 2000);
					}).catch(err => {
						console.error('Failed to copy:', err);
						frappe.msgprint(__('Failed to copy to clipboard'));
					});
				});
			}
			
			dialog.show();
		}, __('Configuration'));
		
		// Setup GitHub Button (Enhanced)
		frm.add_custom_button(__('Setup GitHub'), () => {
			const dialog = new frappe.ui.Dialog({
				title: __('GitHub Configuration'),
				fields: [
					{
						fieldname: 'info',
						fieldtype: 'HTML',
						options: `
							<div style="padding: 15px; background: #f8f9fa; border-radius: 6px; margin-bottom: 20px; border-left: 4px solid #5e64ff;">
								<div style="font-weight: 600; color: #495057; margin-bottom: 10px;">
									<i class="fa fa-github" style="font-size: 18px;"></i> Complete GitHub Integration Setup
								</div>
								<div style="font-size: 13px; color: #6c757d; line-height: 1.6; margin-bottom: 10px;">
									Configure your GitHub credentials and git identity. We recommend using SSH for secure authentication.
								</div>
								<div style="padding: 10px; background: #e7f3ff; border-radius: 4px; border-left: 3px solid #5e64ff;">
									<div style="font-size: 12px; color: #495057;">
										<strong>💡 Recommended:</strong> Use "Generate SSH Keys" button first for secure, passwordless authentication.
									</div>
								</div>
								<div style="margin-top: 10px; padding: 10px; background: #fff; border-radius: 4px;">
									<div style="font-size: 12px; color: #495057;">
										<strong>For HTTPS (fallback):</strong>
										<a href="https://github.com/settings/tokens" target="_blank" style="margin-left: 5px;">Generate GitHub Token</a>
										→ Select <code>repo</code> scope
									</div>
								</div>
							</div>
						`
					},
					{
						fieldname: 'github_username',
						fieldtype: 'Data',
						label: __('GitHub Username'),
						reqd: 1,
						default: frm.doc.github_username || '',
						description: __('Used for GitHub API and git commits (e.g., amitascra)')
					},
					{
						fieldname: 'github_token',
						fieldtype: 'Password',
						label: __('GitHub Personal Access Token'),
						reqd: 1,
						default: frm.doc.github_password || '',
						description: __('Token with repo scope for private repositories')
					},
					{
						fieldname: 'git_user_email',
						fieldtype: 'Data',
						label: __('Git User Email'),
						reqd: 1,
						default: frm.doc.git_user_email || '',
						description: __('Email for git commits (e.g., amit@example.com)')
					},
					{
						fieldname: 'test_result',
						fieldtype: 'HTML',
						options: '<div id="github-test-result"></div>'
					}
				],
				primary_action_label: __('Test & Save'),
				primary_action: (values) => {
					// Test connection first
					$('#github-test-result').html(`
						<div style="padding: 10px; background: #e7f3ff; border-radius: 4px; margin-top: 10px;">
							<i class="fa fa-spinner fa-spin"></i> Testing GitHub connection...
						</div>
					`);
					
					frappe.call({
						method: "bench_manager.bench_manager.doctype.bench_settings.bench_settings.test_github_connection",
						args: {
							username: values.github_username,
							token: values.github_token
						},
						callback: function(r) {
							if (r.message && r.message.success) {
								// Auto-populate email if available from GitHub and not already set
								if (r.message.email && !values.git_user_email) {
									dialog.set_value('git_user_email', r.message.email);
								}
								
								// Show success
								$('#github-test-result').html(`
									<div style="padding: 15px; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 4px; margin-top: 10px;">
										<div style="color: #155724; font-weight: 600; margin-bottom: 10px;">
											<i class="fa fa-check-circle"></i> Connection Successful!
										</div>
										<div style="font-size: 13px; color: #155724;">
											<div><strong>Username:</strong> ${r.message.login}</div>
											<div><strong>Name:</strong> ${r.message.name || 'N/A'}</div>
											<div><strong>Email:</strong> ${r.message.email || 'Not public'}</div>
											<div><strong>Public Repos:</strong> ${r.message.public_repos || 0}</div>
											<div><strong>Private Repos:</strong> ${r.message.total_private_repos || 0}</div>
										</div>
									</div>
								`);
								
								// Save to form
								frm.set_value('github_username', values.github_username);
								frm.set_value('github_password', values.github_token);
								frm.set_value('git_user_email', values.git_user_email);
								
								// Save form
								frm.save().then(() => {
									frappe.show_alert({
										message: __('GitHub credentials saved successfully'),
										indicator: 'green'
									});
									dialog.hide();
								});
							} else {
								// Show error
								$('#github-test-result').html(`
									<div style="padding: 15px; background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 4px; margin-top: 10px;">
										<div style="color: #721c24; font-weight: 600; margin-bottom: 10px;">
											<i class="fa fa-times-circle"></i> Connection Failed
										</div>
										<div style="font-size: 13px; color: #721c24; margin-bottom: 10px;">
											<strong>Error:</strong> ${r.message.error}
										</div>
										<div style="padding: 10px; background: #fff3cd; border-radius: 4px;">
											<div style="font-size: 12px; color: #856404;">
												<strong>Troubleshooting:</strong>
												<ul style="margin: 5px 0 0 20px; padding-left: 0; list-style-position: inside;">
													<li>Verify GitHub username is correct</li>
													<li>Ensure token is valid and not expired</li>
													<li>Token must have <code>repo</code> scope</li>
												</ul>
											</div>
										</div>
									</div>
								`);
							}
						}
					});
				},
				secondary_action_label: __('Cancel')
			});
			
			dialog.show();
		}, __('Configuration'));
		
		frm.add_custom_button(__('Reload Nginx'), () => {
			let root_password = frm.doc.password_root;
			
			if (!root_password) {
				frappe.msgprint({
					title: __('Password Required'),
					message: __('Please set Root User Password in Bench Settings > Password Settings > Password Root field'),
					indicator: 'red'
				});
				return;
			}
			
			frappe.call({
				method: "bench_manager.bench_manager.doctype.bench_settings.bench_settings.setup_and_restart_nginx",
				args: {
					"root_password": root_password
				},
				freeze: true,
				freeze_message: __("Reloading Nginx...")
			});
		}, __('Configuration'));
		
		// === SYNC GROUP ===
		frm.add_custom_button(__('Sync Sites & Apps'), () => {
			frappe.call({
				method: 'bench_manager.bench_manager.doctype.bench_settings.bench_settings.sync_all',
				callback: function(r) {
					frappe.show_alert({
						message: __('Sites and Apps synced successfully'),
						indicator: 'green'
					});
					frm.reload_doc();
				}
			});
		}, __('Sync'));
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