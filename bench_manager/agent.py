# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

import json
import requests
from frappe.utils.password import get_decrypted_password


class Agent:
	def __init__(self, server, server_type="Virtual Machine"):
		self.server = server
		self.server_type = server_type
		self.port = 25052  # Agent default port

	def _get_request_url(self, path):
		"""Get the full URL for agent API endpoint"""
		server_ip = self._get_server_ip()
		return f"https://{server_ip}:{self.port}/agent/{path}"

	def _get_server_ip(self):
		"""Get the IP address of the server"""
		if self.server_type == "Virtual Machine":
			from frappe.db import get_value
			ip = get_value("Virtual Machine", self.server, "public_ip")
			if not ip:
				ip = get_value("Virtual Machine", self.server, "private_ip")
			return ip
		return self.server

	def _get_auth_headers(self):
		"""Get authentication headers with bearer token"""
		password = get_decrypted_password(self.server_type, self.server, "agent_password")
		return {"Authorization": f"bearer {password}"}

	def get(self, path, raises=True):
		"""Make a GET request to the agent"""
		return self.request("GET", path, raises=raises)

	def post(self, path, data=None, raises=True):
		"""Make a POST request to the agent"""
		return self.request("POST", path, data, raises=raises)

	def delete(self, path, data=None, raises=True):
		"""Make a DELETE request to the agent"""
		return self.request("DELETE", path, data, raises=raises)

	def request(self, method, path, data=None, raises=True):
		"""Make an HTTP request to the agent"""
		url = self._get_request_url(path)
		headers = self._get_auth_headers()
		
		try:
			if method == "GET":
				response = requests.get(url, headers=headers, timeout=(10, 30), verify=False)
			elif method == "POST":
				response = requests.post(url, headers=headers, json=data, timeout=(10, 30), verify=False)
			elif method == "DELETE":
				response = requests.delete(url, headers=headers, json=data, timeout=(10, 30), verify=False)
			
			if raises and response.status_code >= 400:
				try:
					error_data = response.json()
					output = "\n\n".join([
						error_data.get("output", ""),
						error_data.get("traceback", "")
					])
					if output == "\n\n":
						output = json.dumps(error_data, indent=2, sort_keys=True)
				except Exception:
					output = response.text
				raise Exception(f"{response.status_code} {response.reason}\n\n{output}")
			
			return response.json()
		except requests.exceptions.RequestException as e:
			raise Exception(f"Failed to connect to agent: {str(e)}")

	def ping(self):
		"""Ping the agent to check if it's running"""
		return self.get("ping", raises=False)

	def get_bench(self, bench_name):
		"""Get information about a bench"""
		return self.get(f"benches/{bench_name}")

	def new_bench(self, bench_name, bench_config=None, common_site_config=None):
		"""Create a new bench on the agent"""
		data = {
			"name": bench_name,
			"bench_config": bench_config or {},
			"common_site_config": common_site_config or {},
		}
		return self.post("benches", data=data)

	def new_site(self, bench_name, site_name, config=None, apps=None, admin_password=None):
		"""Create a new site on the agent"""
		data = {
			"name": site_name,
			"config": config or {},
			"apps": apps or [],
			"admin_password": admin_password,
		}
		return self.post(f"benches/{bench_name}/sites", data=data)

	def execute_bench_command(self, bench_name, command):
		"""Execute a command on a bench"""
		data = {"command": command}
		return self.post(f"benches/{bench_name}/execute", data=data)

	def get_site_status(self, bench_name, site_name):
		"""Get status of a site"""
		return self.get(f"benches/{bench_name}/sites/{site_name}/status")
