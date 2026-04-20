// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('SSL Certificate', {
	refresh: function(frm) {
		if (frm.doc.status === 'Pending') {
			frm.add_custom_button('Issue Certificate', () => {
				frappe.call({
					method: 'issue_certificate',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Certificate issuance initiated');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Active' && frm.doc.auto_renew === 0) {
			frm.add_custom_button('Renew Certificate', () => {
				frappe.call({
					method: 'renew_certificate',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Certificate renewal initiated');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
		}
		
		if (frm.doc.status === 'Active') {
			frm.add_custom_button('Revoke Certificate', () => {
				frappe.call({
					method: 'revoke_certificate',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint('Certificate revoked');
							frm.reload_doc();
						}
					}
				});
			}, 'Actions');
		}
	}
});
