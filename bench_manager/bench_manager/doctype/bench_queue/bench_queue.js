// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bench Queue', {
	refresh: function(frm) {
		if (frm.doc.status === 'Failure') {
			frm.add_custom_button('Retry', () => {
				frappe.call({
					method: 'retry_queue_item',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Queue item requeued');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
		}
	}
});
