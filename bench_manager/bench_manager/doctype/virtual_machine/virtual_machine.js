// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Virtual Machine', {
	refresh: function(frm) {
		// Deploy Agent button
		if (frm.doc.instance_id && !frm.doc.agent_installed) {
			frm.add_custom_button('Deploy Agent', () => {
				// Show initial progress
				frm.dashboard.show_progress('Agent Deployment', 10, 'Starting agent deployment...');
				frm.page.set_indicator(__('In Progress'), 'orange');
				
				// Listen for progress updates before calling the method
				frappe.realtime.on(`agent_deployment_${frm.doc.name}`, (data) => {
					if (data.status === 'failed') {
						frm.dashboard.hide_progress('Agent Deployment');
						frappe.msgprint({
							title: 'Deployment Failed',
							message: data.message,
							indicator: 'red'
						});
						frappe.realtime.off(`agent_deployment_${frm.doc.name}`);
					} else if (data.status === 'completed') {
						frm.dashboard.hide_progress('Agent Deployment');
						frappe.msgprint({
							title: 'Deployment Completed',
							message: data.message,
							indicator: 'green'
						});
						frappe.realtime.off(`agent_deployment_${frm.doc.name}`);
						frm.reload_doc();
					} else if (data.status === 'running') {
						// Update progress bar
						frm.dashboard.show_progress('Agent Deployment', data.progress || 0, data.message);
						frm.page.set_indicator(__('In Progress'), 'orange');
					}
				});
				
				// Call the deploy method
				frappe.call({
					method: 'deploy_agent',
					doc: frm.doc,
					freeze: true,
					freeze_message: 'Deploying agent...',
					callback: function(r) {
						if (r.message) {
							// Success handled by realtime event
						}
					},
					error: function(err) {
						frm.dashboard.hide_progress('Agent Deployment');
						frappe.msgprint({
							title: 'Error',
							message: err.message,
							indicator: 'red'
						});
					}
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Draft') {
			frm.add_custom_button('Provision Instance', () => {
				frm.dashboard.show_progress('Provisioning Instance', 10, 'Starting instance provisioning...');
				frm.page.set_indicator(__('In Progress'), 'orange');
				
				frappe.call({
					method: 'provision_instance',
					doc: frm.doc,
					freeze: true,
					freeze_message: 'Provisioning instance...',
					callback: function(r) {
						frm.dashboard.hide_progress('Provisioning Instance');
						if (r.message) {
							frappe.msgprint('Instance provisioned successfully');
							frm.reload_doc();
						}
					},
					error: function(err) {
						frm.dashboard.hide_progress('Provisioning Instance');
						frappe.msgprint({
							title: 'Error',
							message: err.message,
							indicator: 'red'
						});
					}
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Stopped') {
			frm.add_custom_button('Start Instance', () => {
				frm.dashboard.show_progress('Starting Instance', 10, 'Starting instance...');
				frm.page.set_indicator(__('In Progress'), 'orange');
				
				frappe.call({
					method: 'start_instance',
					doc: frm.doc,
					freeze: true,
					freeze_message: 'Starting instance...',
					callback: function(r) {
						frm.dashboard.hide_progress('Starting Instance');
						if (r.message) {
							frappe.msgprint('Instance started successfully');
							frm.reload_doc();
						}
					},
					error: function(err) {
						frm.dashboard.hide_progress('Starting Instance');
						frappe.msgprint({
							title: 'Error',
							message: err.message,
							indicator: 'red'
						});
					}
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Running') {
			frm.add_custom_button('Stop Instance', () => {
				frappe.confirm('Are you sure you want to stop this instance?', () => {
					frm.dashboard.show_progress('Stopping Instance', 10, 'Stopping instance...');
					frm.page.set_indicator(__('In Progress'), 'orange');
					
					frappe.call({
						method: 'stop_instance',
						doc: frm.doc,
						freeze: true,
						freeze_message: 'Stopping instance...',
						callback: function(r) {
							frm.dashboard.hide_progress('Stopping Instance');
							if (r.message) {
								frappe.msgprint('Instance stopped successfully');
								frm.reload_doc();
							}
						},
						error: function(err) {
							frm.dashboard.hide_progress('Stopping Instance');
							frappe.msgprint({
								title: 'Error',
								message: err.message,
								indicator: 'red'
							});
						}
					});
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Running' || frm.doc.status === 'Stopped') {
			frm.add_custom_button('Terminate Instance', () => {
				frappe.confirm('Are you sure you want to terminate this instance? This action cannot be undone.', () => {
					frm.dashboard.show_progress('Terminating Instance', 10, 'Terminating instance...');
					frm.page.set_indicator(__('In Progress'), 'orange');
					
					frappe.call({
						method: 'terminate_instance',
						doc: frm.doc,
						freeze: true,
						freeze_message: 'Terminating instance...',
						callback: function(r) {
							frm.dashboard.hide_progress('Terminating Instance');
							if (r.message) {
								frappe.msgprint('Instance terminated successfully');
								frm.reload_doc();
							}
						},
						error: function(err) {
							frm.dashboard.hide_progress('Terminating Instance');
							frappe.msgprint({
								title: 'Error',
								message: err.message,
								indicator: 'red'
							});
						}
					});
				});
			}, 'Actions');
		}
		
		if (frm.doc.instance_id) {
			frm.add_custom_button('Refresh Status', () => {
				frm.dashboard.show_progress('Refreshing Status', 10, 'Refreshing instance status...');
				
				frappe.call({
					method: 'get_instance_status',
					doc: frm.doc,
					freeze: true,
					freeze_message: 'Refreshing status...',
					callback: function(r) {
						frm.dashboard.hide_progress('Refreshing Status');
						if (r.message) {
							frm.reload_doc();
						}
					},
					error: function(err) {
						frm.dashboard.hide_progress('Refreshing Status');
						frappe.msgprint({
							title: 'Error',
							message: err.message,
							indicator: 'red'
						});
					}
				});
			}, 'Actions');
		}
		
		// Associate Public IP button (if no public IP)
		if (frm.doc.instance_id && !frm.doc.public_ip) {
			frm.add_custom_button('Associate Public IP', () => {
				frappe.confirm('This will allocate and associate an Elastic IP to the instance. Continue?', () => {
					frm.dashboard.show_progress('Associating Public IP', 10, 'Allocating Elastic IP...');
					frm.page.set_indicator(__('In Progress'), 'orange');
					
					frappe.call({
						method: 'associate_public_ip',
						doc: frm.doc,
						freeze: true,
						freeze_message: 'Allocating Elastic IP...',
						callback: function(r) {
							frm.dashboard.hide_progress('Associating Public IP');
							if (r.message) {
								frappe.msgprint(`Public IP allocated: ${r.message.public_ip}`);
								frm.reload_doc();
							}
						},
						error: function(err) {
							frm.dashboard.hide_progress('Associating Public IP');
							frappe.msgprint({
								title: 'Error',
								message: err.message,
								indicator: 'red'
							});
						}
					});
				});
			}, 'Actions');
		}
		
		// Configure SSH button (if instance exists)
		if (frm.doc.instance_id && frm.doc.status === 'Running') {
			frm.add_custom_button('Configure SSH', () => {
				frappe.confirm('This will configure SSH access using AWS Systems Manager. Continue?', () => {
					frm.dashboard.show_progress('Configuring SSH', 10, 'Configuring SSH access...');
					frm.page.set_indicator(__('In Progress'), 'orange');
					
					frappe.call({
						method: 'bench_manager.bench_manager.doctype.cloud_provider.cloud_provider.configure_instance_ssh',
						args: {
							cloud_provider_name: frm.doc.cloud_provider,
							instance_id: frm.doc.instance_id
						},
						freeze: true,
						freeze_message: 'Configuring SSH...',
						callback: function(r) {
							frm.dashboard.hide_progress('Configuring SSH');
							if (r.message) {
								frappe.msgprint(r.message);
							}
						},
						error: function(err) {
							frm.dashboard.hide_progress('Configuring SSH');
							frappe.msgprint({
								title: 'Error',
								message: err.message,
								indicator: 'red'
							});
						}
					});
				});
			}, 'Actions');
		}
	},
	
	onload: function(frm) {
		// Clean up realtime listeners when form is unloaded
		frm.cscript.on_form_unload = function() {
			if (frm.doc.name) {
				frappe.realtime.off(`agent_deployment_${frm.doc.name}`);
			}
		};
	},
	
	cloud_provider: function(frm) {
		if (frm.doc.cloud_provider) {
			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					doctype: 'Cloud Provider',
					name: frm.doc.cloud_provider,
					fieldname: ['region', 'name']
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('region', r.message.region);
						// Fetch AMI from Cloud Provider
						frappe.call({
							method: 'bench_manager.bench_manager.doctype.cloud_provider.cloud_provider.get_ami_for_region',
							args: {
								cloud_provider_name: frm.doc.cloud_provider
							},
							callback: function(ami_r) {
								if (ami_r.message) {
									frm.set_value('ami_id', ami_r.message);
								}
							}
						});
					}
				}
			});
		}
	},
	
	instance_type: function(frm) {
		// vCPU and RAM will be set automatically in Python validate
	}
});
