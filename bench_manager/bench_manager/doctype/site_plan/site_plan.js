// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Site Plan', {
	refresh: function(frm) {
		frm.add_custom_button('View Benches', () => {
			frappe.call({
				method: 'get_benches',
				doc: frm.doc,
				callback: function(r) {
					if (r.message) {
						frappe.msgprint(JSON.stringify(r.message));
					}
				}
			});
		}, 'Actions');
	}
});
