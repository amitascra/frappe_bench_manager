# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import requests
from frappe.utils.password import get_decrypted_password
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from requests import Response


class AgentCommunication:
	"""HTTP client for communicating with Agent on remote servers"""
	
	def __init__(self, server, server_type="Application Server"):
		self.server = server
		self.server_type = server_type
		self.timeout = 300  # 5 minutes default timeout
	
	def get_server_url(self):
		"""Get the base URL for the Agent API"""
		import frappe
		
		if self.server_type == "Application Server":
			app_server = frappe.get_doc("Application Server", self.server)
			vm = frappe.get_doc("Virtual Machine", app_server.virtual_machine)
			return f"https://{vm.public_ip}"
		else:
			# Add other server types as needed
			raise ValueError(f"Unsupported server type: {self.server_type}")
	
	def get_access_token(self):
		"""Get the access token for Agent authentication"""
		import frappe
		
		if self.server_type == "Application Server":
			app_server = frappe.get_doc("Application Server", self.server)
			return app_server.agent_access_token
		else:
			raise ValueError(f"Unsupported server type: {self.server_type}")
	
	def get_headers(self):
		"""Get HTTP headers for Agent API requests"""
		access_token = self.get_access_token()
		return {
			"Authorization": f"Bearer {access_token}",
			"Content-Type": "application/json"
		}
	
	def post(self, endpoint, data=None):
		"""Send POST request to Agent"""
		url = f"{self.get_server_url()}/{endpoint}"
		headers = self.get_headers()
		
		try:
			response = requests.post(
				url,
				json=data,
				headers=headers,
				timeout=self.timeout,
				verify=False  # TODO: Add SSL verification
			)
			response.raise_for_status()
			return response.json()
		except requests.exceptions.RequestException as e:
			raise Exception(f"Agent communication error: {str(e)}")
	
	def get(self, endpoint):
		"""Send GET request to Agent"""
		url = f"{self.get_server_url()}/{endpoint}"
		headers = self.get_headers()
		
		try:
			response = requests.get(
				url,
				headers=headers,
				timeout=self.timeout,
				verify=False  # TODO: Add SSL verification
			)
			response.raise_for_status()
			return response.json()
		except requests.exceptions.RequestException as e:
			raise Exception(f"Agent communication error: {str(e)}")
	
	def delete(self, endpoint):
		"""Send DELETE request to Agent"""
		url = f"{self.get_server_url()}/{endpoint}"
		headers = self.get_headers()
		
		try:
			response = requests.delete(
				url,
				headers=headers,
				timeout=self.timeout,
				verify=False  # TODO: Add SSL verification
			)
			response.raise_for_status()
			return response.json()
		except requests.exceptions.RequestException as e:
			raise Exception(f"Agent communication error: {str(e)}")


class Agent:
	"""Agent class for executing operations on remote servers"""
	
	def __init__(self, server, server_type="Application Server"):
		self.server = server
		self.server_type = server_type
		self.comm = AgentCommunication(server, server_type)
	
	def new_bench(self, bench_name, frappe_version, apps, bench_config=None, config=None):
		"""Create new bench on remote server"""
		data = {
			"name": bench_name,
			"frappe_version": frappe_version,
			"apps": apps,
		}
		
		if bench_config:
			data["bench_config"] = bench_config
		if config:
			data["config"] = config
		
		return self.comm.post("benches", data)
	
	def restart_bench(self, bench_name, web_only=False):
		"""Restart bench on remote server"""
		data = {"web_only": web_only}
		return self.comm.post(f"benches/{bench_name}/restart", data)
	
	def rebuild_bench(self, bench_name):
		"""Rebuild bench assets on remote server"""
		return self.comm.post(f"benches/{bench_name}/rebuild")
	
	def archive_bench(self, bench_name):
		"""Archive bench on remote server"""
		return self.comm.post(f"benches/{bench_name}/archive")
	
	def get_bench_status(self, bench_name):
		"""Get bench status from remote server"""
		return self.comm.get(f"benches/{bench_name}/status")
