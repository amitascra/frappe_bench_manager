frappe.listview_settings['Site'] = {
	add_fields: ['site_status'],
	formatters: {
		app_list: function(val) {
			return val.split('\n').join(', ');
		},
		site_alias: function(val) {
			return val.split('\n').join(', ');
		}	
	},
	get_indicator: function(doc) {
		if (doc.site_status === 'Online') {
			return [__('Online'), 'green', 'site_status,=,Online'];
		} else if (doc.site_status === 'Offline') {
			return [__('Offline'), 'red', 'site_status,=,Offline'];
		} else if (doc.site_status === 'Error') {
			return [__('Error'), 'orange', 'site_status,=,Error'];
		} else {
			return [__('Unknown'), 'gray', 'site_status,=,Unknown'];
		}
	},
	refresh: () => {
		setTimeout( () => {
			$("input.list-select-all.hidden-xs").hide()
		}, 500);
		setTimeout( () => {
			$("input.list-row-checkbox.hidden-xs").hide()
		}, 500);
	}
};