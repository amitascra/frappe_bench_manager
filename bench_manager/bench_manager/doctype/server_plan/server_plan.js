// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Server Plan', {
	refresh: function(frm) {
		frm.add_custom_button('View Servers', () => {
			frappe.call({
				method: 'get_servers',
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
