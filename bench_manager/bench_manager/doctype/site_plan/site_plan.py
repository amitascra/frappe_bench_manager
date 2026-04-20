# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from datetime import datetime


class SitePlan(Document):
	def before_save(self):
		if not self.created_at:
			self.created_at = datetime.now()
		self.modified = datetime.now()

	def get_benches(self):
		"""Get all cloud benches using this plan"""
		benches = frappe.get_all("Cloud Bench", {"site_plan": self.name})
		return benches
