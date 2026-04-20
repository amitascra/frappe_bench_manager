// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Docker Build', {
	refresh: function(frm) {
		if (frm.doc.status === 'Pending') {
			frm.add_custom_button('Start Build', () => {
				frappe.call({
					method: 'start_build',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Docker build started');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
		}
	}
});
