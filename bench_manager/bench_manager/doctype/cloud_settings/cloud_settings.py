# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password


class CloudSettings(Document):
	def validate(self):
		if self.default_cloud_provider:
			# Validate that the cloud provider exists
			cloud_provider = frappe.get_doc("Cloud Provider", self.default_cloud_provider)
			if not cloud_provider.enabled:
				frappe.throw("Default Cloud Provider must be enabled")
		
		if self.docker_registry_url and self.docker_registry_username:
			# Validate Docker registry credentials if provided
			# TODO: Implement Docker registry credential validation
			pass

	@staticmethod
	def get_settings():
		"""Get Cloud Settings document"""
		doc = frappe.get_single("Cloud Settings")
		if not doc:
			doc = frappe.new_doc("Cloud Settings")
			doc.save()
		return doc

	@frappe.whitelist()
	def get_docker_registry_credentials(self):
		"""Get Docker registry credentials"""
		if not self.docker_registry_url:
			return None
		
		return {
			"url": self.docker_registry_url,
			"username": self.docker_registry_username,
			"password": get_decrypted_password("Cloud Settings", self.name, "docker_registry_password")
		}

	@frappe.whitelist()
	def get_default_cloud_provider(self):
		"""Get default cloud provider"""
		if not self.default_cloud_provider:
			return None
		
		return frappe.get_doc("Cloud Provider", self.default_cloud_provider)
