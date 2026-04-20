// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Agent Job', {
	refresh: function(frm) {
		if (frm.doc.status === 'Pending') {
			frm.add_custom_button('Execute Job', () => {
				frappe.call({
					method: 'execute_job',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Job executed successfully');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
		}
	}
});
