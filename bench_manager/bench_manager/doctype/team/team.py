# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from datetime import datetime


class Team(Document):
	def before_save(self):
		if not self.created_at:
			self.created_at = datetime.now()
		self.modified = datetime.now()

	def get_servers(self):
		"""Get all servers associated with this team"""
		app_servers = frappe.get_all("Application Server", {"team": self.name})
		db_servers = frappe.get_all("Database Server", {"team": self.name})
		proxy_servers = frappe.get_all("Proxy Server", {"team": self.name})
		
		return {
			"application_servers": app_servers,
			"database_servers": db_servers,
			"proxy_servers": proxy_servers
		}

	def get_cloud_benches(self):
		"""Get all cloud benches associated with this team's servers"""
		benches = frappe.get_all("Cloud Bench", {
			"application_server": ["in", [s.name for s in self.get_servers()["application_servers"]]]
		})
		return benches
