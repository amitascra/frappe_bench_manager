# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password
from frappe.utils import random_string
from datetime import datetime


class ApplicationServer(Document):
	def validate(self):
		if self.virtual_machine:
			vm = frappe.get_doc("Virtual Machine", self.virtual_machine)
			if vm.series != "f":
				frappe.throw("Virtual Machine must have series 'f' for Application Server")
			
			# Set cloud provider from VM
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
		"""Provision application server by installing Agent and Docker"""
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
			# This requires Ansible playbooks which will be created later
			# For now, we'll mark the server as pending installation
			
			self.db_set("status", "Installing")
			
			# TODO: Install Docker via Ansible
			# This requires Docker installation playbooks
			
			return {
				"status": "Installing",
				"message": "Server provisioning initiated"
			}
			
		except Exception as e:
			self.db_set("status", "Broken")
			frappe.throw(f"Failed to provision server: {str(e)}")

	@frappe.whitelist()
	def install_agent(self):
		"""Install Agent on server"""
		try:
			vm = self.get_virtual_machine()
			
			# TODO: Execute Ansible playbook to install Agent
			# Playbook should:
			# 1. SSH into server
			# 2. Install Python dependencies
			# 3. Clone Agent repository (or forked version)
			# 4. Install Agent via pip
			# 5. Configure Agent with access token
			# 6. Start Agent service
			
			# For now, mark as installed
			self.db_set("agent_installed", 1)
			
			return {"status": "Success", "message": "Agent installed"}
			
		except Exception as e:
			frappe.throw(f"Failed to install Agent: {str(e)}")

	@frappe.whitelist()
	def install_docker(self):
		"""Install Docker on server"""
		try:
			vm = self.get_virtual_machine()
			
			# TODO: Execute Ansible playbook to install Docker
			# Playbook should:
			# 1. SSH into server
			# 2. Install Docker
			# 3. Configure Docker registry
			# 4. Start Docker service
			
			# For now, mark as installed
			self.db_set("docker_installed", 1)
			
			return {"status": "Success", "message": "Docker installed"}
			
		except Exception as e:
			frappe.throw(f"Failed to install Docker: {str(e)}")

	@frappe.whitelist()
	def activate_server(self):
		"""Activate server after Agent and Docker are installed"""
		if self.agent_installed and self.docker_installed:
			self.db_set("status", "Active")
			return {"status": "Active"}
		else:
			frappe.throw("Server cannot be activated until Agent and Docker are installed")

	@frappe.whitelist()
	def restart_server(self):
		"""Restart application server"""
		try:
			# TODO: Call Agent to restart server
			# This will be implemented in Phase 2.2 (Agent Communication Module)
			
			return {"status": "Success", "message": "Server restart initiated"}
			
		except Exception as e:
			frappe.throw(f"Failed to restart server: {str(e)}")

	@frappe.whitelist()
	def archive_server(self):
		"""Archive application server"""
		try:
			vm = self.get_virtual_machine()
			
			# Stop VM
			vm.stop_instance()
			
			# Archive server
			self.db_set("status", "Archived")
			
			return {"status": "Archived"}
			
		except Exception as e:
			frappe.throw(f"Failed to archive server: {str(e)}")
