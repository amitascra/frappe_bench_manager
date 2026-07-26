# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe and contributors
# For license information, please see license.txt



from frappe.model.document import Document


class BenchManagerCommand(Document):
	def validate(self):
		# Set bench_node to Local Bench for commands
		if self.get("__islocal"):
			self.bench_node = "Local Bench"
