# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import random_string
from datetime import datetime


class ProxyServer(Document):
	def validate(self):
		if self.virtual_machine:
			vm = frappe.get_doc("Virtual Machine", self.virtual_machine)
			if vm.series != "m":
				frappe.throw("Virtual Machine must have series 'm' for Proxy Server")
			
			self.cloud_provider = vm.cloud_provider
	
	def before_save(self):
		if not self.created_at:
			self.created_at = datetime.now()
		self.updated_at = datetime.now()

	def get_virtual_machine(self):
		"""Get virtual machine document"""
		return frappe.get_doc("Virtual Machine", self.virtual_machine)

	def get_cloud_provider(self):
		"""Get cloud provider document"""
		return frappe.get_doc("Cloud Provider", self.cloud_provider)

	@frappe.whitelist()
	def provision_server(self):
		"""Provision proxy server by installing Agent and Proxy (Nginx/Traefik)"""
		try:
			vm = self.get_virtual_machine()
			cloud_provider = self.get_cloud_provider()
			
			# Ensure VM is running
			if vm.status != "Running":
				vm.provision_instance()
				vm.reload()
			
			# Generate agent access token
			if not self.agent_access_token:
				self.agent_access_token = random_string(32)
				self.save()
			
			# TODO: Install Agent via Ansible
			# TODO: Install Nginx/Traefik via Ansible
			# TODO: Configure Proxy for reverse proxy
			
			self.db_set("status", "Installing")
			
			return {
				"status": "Installing",
				"message": "Proxy server provisioning initiated"
			}
			
		except Exception as e:
			self.db_set("status", "Broken")
			frappe.throw(f"Failed to provision server: {str(e)}")

	@frappe.whitelist()
	def activate_server(self):
		"""Activate proxy server after Agent and Proxy are installed"""
		if self.agent_installed:
			self.db_set("status", "Active")
			return {"status": "Active"}
		else:
			frappe.throw("Server cannot be activated until Agent is installed")

	@frappe.whitelist()
	def configure_proxy(self, domain, upstream_server, upstream_port):
		"""Configure proxy for a domain"""
		try:
			# TODO: Call Agent to configure Nginx/Traefik for domain
			
			return {"status": "Success", "message": "Proxy configured"}
			
		except Exception as e:
			frappe.throw(f"Failed to configure proxy: {str(e)}")
