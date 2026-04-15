// Grouped button additions for Bench Settings
// Add these buttons in the refresh function

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
