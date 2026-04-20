# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from datetime import datetime


class ServerPlan(Document):
	def before_save(self):
		if not self.created_at:
			self.created_at = datetime.now()
		self.modified = datetime.now()

	def get_servers(self):
		"""Get all servers using this plan"""
		if self.plan_type == "Application Server":
			servers = frappe.get_all("Application Server", {"plan": self.name})
		elif self.plan_type == "Database Server":
			servers = frappe.get_all("Database Server", {"plan": self.name})
		elif self.plan_type == "Proxy Server":
			servers = frappe.get_all("Proxy Server", {"plan": self.name})
		else:
			servers = []
		
		return servers
