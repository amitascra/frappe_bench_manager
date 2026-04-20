# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from datetime import datetime
import json


class CloudBench(Document):
	def validate(self):
		if self.application_server:
			app_server = frappe.get_doc("Application Server", self.application_server)
			if app_server.status != "Active":
				frappe.throw("Application Server must be Active to create a Cloud Bench")
			
			self.cloud_provider = app_server.cloud_provider
	
	def before_save(self):
		if not self.created_at:
			self.created_at = datetime.now()
		self.updated_at = datetime.now()

	def get_application_server(self):
		"""Get application server document"""
		return frappe.get_doc("Application Server", self.application_server)

	def get_cloud_provider(self):
		"""Get cloud provider document"""
		return frappe.get_doc("Cloud Provider", self.cloud_provider)

	@frappe.whitelist()
	def deploy_bench(self):
		"""Deploy bench to application server via Agent"""
		try:
			app_server = self.get_application_server()
			
			if not app_server.agent_installed:
				frappe.throw("Agent is not installed on Application Server")
			
			if not app_server.docker_installed:
				frappe.throw("Docker is not installed on Application Server")
			
			# Prepare bench data
			apps_data = []
			for app in self.apps:
				apps_data.append({
					"name": app.app,
					"repo": app.repo,
					"branch": app.branch,
					"hash": app.hash
				})
			
			bench_config = json.loads(self.bench_config) if self.bench_config else {}
			config = json.loads(self.config) if self.config else {}
			
			# TODO: Call Agent to create bench
			# This will be implemented in Phase 2.2 (Agent Communication Module)
			# For now, mark as pending installation
			
			self.db_set("status", "Installing")
			
			# TODO: Create Agent Job to track deployment
			# This will be implemented in Phase 2.2
			
			return {
				"status": "Installing",
				"message": "Bench deployment initiated"
			}
			
		except Exception as e:
			self.db_set("status", "Broken")
			frappe.throw(f"Failed to deploy bench: {str(e)}")

	@frappe.whitelist()
	def restart_bench(self):
		"""Restart bench via Agent"""
		try:
			# TODO: Call Agent to restart bench
			# This will be implemented in Phase 2.2
			
			return {"status": "Success", "message": "Bench restart initiated"}
			
		except Exception as e:
			frappe.throw(f"Failed to restart bench: {str(e)}")

	@frappe.whitelist()
	def rebuild_bench(self):
		"""Rebuild bench assets via Agent"""
		try:
			# TODO: Call Agent to rebuild bench
			# This will be implemented in Phase 2.2
			
			return {"status": "Success", "message": "Bench rebuild initiated"}
			
		except Exception as e:
			frappe.throw(f"Failed to rebuild bench: {str(e)}")

	@frappe.whitelist()
	def archive_bench(self):
		"""Archive bench via Agent"""
		try:
			# TODO: Call Agent to archive bench
			# This will be implemented in Phase 2.2
			
			self.db_set("status", "Archived")
			
			return {"status": "Archived"}
			
		except Exception as e:
			frappe.throw(f"Failed to archive bench: {str(e)}")
