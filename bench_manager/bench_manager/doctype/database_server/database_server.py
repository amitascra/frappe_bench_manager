# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password
from frappe.utils import random_string
from datetime import datetime


class DatabaseServer(Document):
	def validate(self):
		if self.virtual_machine:
			vm = frappe.get_doc("Virtual Machine", self.virtual_machine)
			if vm.series != "m":
				frappe.throw("Virtual Machine must have series 'm' for Database Server")
			
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
		"""Provision database server by installing Agent and MariaDB"""
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
			
			# Generate MariaDB root password
			if not self.mariadb_root_password:
				self.mariadb_root_password = random_string(32)
				self.save()
			
			# TODO: Install Agent via Ansible
			# TODO: Install MariaDB via Ansible
			# TODO: Configure MariaDB for remote access
			
			self.db_set("status", "Installing")
			
			return {
				"status": "Installing",
				"message": "Database server provisioning initiated"
			}
			
		except Exception as e:
			self.db_set("status", "Broken")
			frappe.throw(f"Failed to provision server: {str(e)}")

	@frappe.whitelist()
	def activate_server(self):
		"""Activate database server after Agent and MariaDB are installed"""
		if self.agent_installed:
			self.db_set("status", "Active")
			return {"status": "Active"}
		else:
			frappe.throw("Server cannot be activated until Agent is installed")

	@frappe.whitelist()
	def create_database(self, database_name, user, password):
		"""Create database on MariaDB server"""
		try:
			# TODO: Call Agent to create database
			# This will be implemented in Phase 2.2 (Agent Communication Module)
			
			return {"status": "Success", "message": "Database created"}
			
		except Exception as e:
			frappe.throw(f"Failed to create database: {str(e)}")

	@frappe.whitelist()
	def create_database_user(self, database_name, user, password):
		"""Create database user on MariaDB server"""
		try:
			# TODO: Call Agent to create database user
			
			return {"status": "Success", "message": "Database user created"}
			
		except Exception as e:
			frappe.throw(f"Failed to create database user: {str(e)}")
