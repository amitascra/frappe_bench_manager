// Copyright (c) 2017, Frappé and contributors
// For license information, please see license.txt

var console_dialog = (key) => {
	// Clean up any existing console dialog
	if (frappe._console_dialog) {
		frappe._console_dialog.hide();
	}
	
	// Remove previous event listener if exists
	if (frappe._console_key) {
		frappe.realtime.off(frappe._console_key);
	}
	
	var dialog = new frappe.ui.Dialog({
		title: 'Console Output',
		fields: [
			{fieldname: 'status', fieldtype: 'HTML'},
			{fieldname: 'console', fieldtype: 'HTML'},
		],
		primary_action_label: 'Copy Output',
		primary_action: function() {
			const output = frappe._output || '';
			navigator.clipboard.writeText(output).then(() => {
				frappe.show_alert({message: 'Output copied to clipboard', indicator: 'green'});
			}).catch(() => {
				frappe.show_alert({message: 'Failed to copy output', indicator: 'red'});
			});
		},
		secondary_action_label: 'Close',
		secondary_action: function() {
			dialog.hide();
		}
	});
	
	// Prevent closing on backdrop click
	dialog.$wrapper.find('.modal').attr('data-backdrop', 'static');
	
	// Add status indicator
	const status_html = `
		<div class="console-status" style="padding: 10px; margin-bottom: 10px; background: #f8f9fa; border-radius: 4px; display: flex; align-items: center; gap: 10px;">
			<div class="status-indicator" style="width: 12px; height: 12px; border-radius: 50%; background: #ffa00a; animation: pulse 1.5s infinite;"></div>
			<span class="status-text" style="font-weight: 500; color: #495057;">Command Running...</span>
		</div>
		<style>
			@keyframes pulse {
				0%, 100% { opacity: 1; }
				50% { opacity: 0.5; }
			}
		</style>
	`;
	dialog.get_field('status').$wrapper.html(status_html);
	
	// Create console output container with auto-scroll
	const console_wrapper = $(`
		<div class="console-wrapper" style="
			max-height: 500px; 
			overflow-y: auto; 
			background: #1e1e1e; 
			border-radius: 4px; 
			padding: 15px;
			font-family: 'Courier New', monospace;
		">
			<pre class="console" style="margin: 0; color: #d4d4d4; font-size: 13px; line-height: 1.5;"><code></code></pre>
		</div>
	`);
	
	frappe._output_target = console_wrapper.find('code').get(0);
	frappe._console_wrapper = console_wrapper.get(0);
	frappe._output = '';
	frappe._in_progress = false;
	frappe._output_target.innerHTML = '';
	frappe._console_dialog = dialog;
	frappe._console_key = key;
	
	dialog.get_field('console').$wrapper.html(console_wrapper);
	dialog.show();
	
	// Responsive width
	const modal_dialog = dialog.$wrapper.find('.modal-dialog');
	modal_dialog.css({
		'width': '90%',
		'max-width': '1200px',
		'margin': '30px auto'
	});
	
	// Auto-scroll function
	const autoScroll = () => {
		if (frappe._console_wrapper) {
			frappe._console_wrapper.scrollTop = frappe._console_wrapper.scrollHeight;
		}
	};
	
	// Update status function
	const updateStatus = (status, color) => {
		const statusIndicator = dialog.$wrapper.find('.status-indicator');
		const statusText = dialog.$wrapper.find('.status-text');
		statusIndicator.css('background', color);
		statusText.text(status);
		if (color !== '#ffa00a') {
			statusIndicator.css('animation', 'none');
		}
	};

	frappe.realtime.on(key, function(output) {
		if (output==='\r') {
			// clear current line, means we are showing some kind of progress indicator
			frappe._in_progress = true;
			if(frappe._output_target.innerHTML != frappe._output) {
				// progress updated... redraw
				frappe._output_target.innerHTML = frappe._output;
				autoScroll();
			}
			frappe._output = frappe._output.split('\n').slice(0, -1).join('\n') + '\n';
			return;
		} else {
			frappe._output += output;
		}

		if (output==='\n') {
			frappe._in_progress = false;
		}

		if (frappe._in_progress) {
			return;
		}

		if (!frappe._last_update) {
			frappe._last_update = setTimeout(() => {
				frappe._last_update = null;
				if(!frappe.in_progress) {
					frappe._output_target.innerHTML = frappe._output;
					autoScroll();
					
					// Check for completion indicators
					if (frappe._output.includes('Success!') || frappe._output.includes('completed')) {
						updateStatus('Command Completed Successfully', '#28a745');
					} else if (frappe._output.includes('Failed!') || frappe._output.includes('Error')) {
						updateStatus('Command Failed', '#dc3545');
					}
				}
			}, 200);
		}
	});
	
	// Cleanup on dialog hide
	dialog.onhide = function() {
		if (frappe._console_key) {
			frappe.realtime.off(frappe._console_key);
			frappe._console_key = null;
		}
		frappe._console_dialog = null;
	};
};