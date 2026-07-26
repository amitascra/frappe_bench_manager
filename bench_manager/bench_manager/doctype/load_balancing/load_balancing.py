# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import random_string
from datetime import datetime
import json


class LoadBalancing(Document):
	def validate(self):
		if self.proxy_server:
			proxy = frappe.get_doc("Proxy Server", self.proxy_server)
			vm = frappe.get_doc("Virtual Machine", proxy.virtual_machine)
			self.cloud_provider = vm.cloud_provider
	
	def before_save(self):
		if not self.created_at:
			self.created_at = datetime.now()
		self.updated_at = datetime.now()

	def get_proxy_server(self):
		"""Get proxy server document"""
		return frappe.get_doc("Proxy Server", self.proxy_server)

	def get_cloud_provider(self):
		"""Get cloud provider document"""
		return frappe.get_doc("Cloud Provider", self.cloud_provider)

	@frappe.whitelist()
	def configure_load_balancer(self):
		"""Configure load balancer on proxy server"""
		try:
			proxy = self.get_proxy_server()
			
			# Ensure proxy server is active
			if proxy.status != "Active":
				frappe.throw("Proxy server must be active before configuring load balancer")
			
			# Generate agent access token if needed
			if not self.agent_access_token:
				self.agent_access_token = random_string(32)
				self.save()
			
			# Prepare load balancer config
			config = {
				"type": self.load_balancer_type,
				"algorithm": self.algorithm,
				"health_check": {
					"enabled": self.health_check_enabled,
					"interval": self.health_check_interval
				}
			}
			
			self.db_set("load_balancer_config", json.dumps(config))
			self.db_set("status", "Configuring")
			
			# TODO: Call Agent to configure Nginx/Traefik load balancer
			# This will be implemented in Phase 2.2 (Agent Communication Module)
			
			return {
				"status": "Configuring",
				"message": "Load balancer configuration initiated"
			}
			
		except Exception as e:
			self.db_set("status", "Broken")
			frappe.throw(f"Failed to configure load balancer: {str(e)}")

	@frappe.whitelist()
	def activate_load_balancer(self):
		"""Activate load balancer after configuration"""
		if self.agent_installed:
			self.db_set("status", "Active")
			return {"status": "Active"}
		else:
			frappe.throw("Load balancer cannot be activated until Agent is installed")

	@frappe.whitelist()
	def add_upstream(self, cloud_bench, port):
		"""Add upstream server to load balancer"""
		try:
			# Confirm the Cloud Bench exists before referencing it below -
			# result unused on purpose, this call is for the side effect of
			# raising if cloud_bench is invalid.
			frappe.get_doc("Cloud Bench", cloud_bench)

			# TODO: Call Agent to add upstream to load balancer config, with
			# {"cloud_bench": cloud_bench,
			#  "server": frappe.get_doc(
			#      "Virtual Machine",
			#      frappe.get_doc("Application Server", bench.application_server).virtual_machine,
			#  ).public_ip,
			#  "port": port}
			
			return {"status": "Success", "message": "Upstream added"}
			
		except Exception as e:
			frappe.throw(f"Failed to add upstream: {str(e)}")

	@frappe.whitelist()
	def remove_upstream(self, cloud_bench):
		"""Remove upstream server from load balancer"""
		try:
			# TODO: Call Agent to remove upstream from load balancer config
			
			return {"status": "Success", "message": "Upstream removed"}
			
		except Exception as e:
			frappe.throw(f"Failed to remove upstream: {str(e)}")
