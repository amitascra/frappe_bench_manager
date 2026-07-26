# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe and contributors
# For license information, please see license.txt

import json
import os
import re
import shlex
import sys
from datetime import datetime, timedelta
from io import StringIO
from subprocess import PIPE, STDOUT, Popen, check_output
from urllib.parse import parse_qs, urlparse
import traceback

import dropbox
import frappe
import paramiko
import psutil
from frappe import _
from frappe.integrations.offsite_backup_utils import (
	get_chunk_site,
	send_email,
)
from frappe.integrations.utils import make_post_request
from frappe.model.document import Document
from frappe.utils import (
	cint,
	encode,
	get_request_site_address,
	get_url,
)
from frappe.utils.background_jobs import enqueue
from frappe.utils.password import get_decrypted_password
from rq.timeouts import JobTimeoutException

from bench_manager.bench_manager.utils import (
	_close_the_doc,
	safe_decode,
	verify_whitelisted_call,
)
import threading

ignore_list = [".DS_Store"]

# Global SSH connection pool
_ssh_connection_pool = {}
_pool_lock = threading.Lock()
_pool_max_idle_time = 300  # 5 minutes


class SSHConnectionPool:
	"""Thread-safe SSH connection pool for bench_manager"""
	
	@staticmethod
	def get_connection(doc):
		"""Get or create SSH connection from pool"""
		with _pool_lock:
			pool_key = f"{doc.name}_{doc.server_ip}_{doc.ssh_port}"
			
			# Check if connection exists and is alive
			if pool_key in _ssh_connection_pool:
				conn_info = _ssh_connection_pool[pool_key]
				ssh = conn_info['connection']
				
				# Check if connection is still alive
				try:
					transport = ssh.get_transport()
					if transport and transport.is_active():
						# Update last used time
						conn_info['last_used'] = datetime.now()
						frappe.logger().debug(f"Reusing SSH connection for {pool_key}")
						return ssh
					else:
						# Connection dead, remove from pool
						del _ssh_connection_pool[pool_key]
				except:
					# Connection error, remove from pool
					if pool_key in _ssh_connection_pool:
						del _ssh_connection_pool[pool_key]
			
			# Create new connection
			ssh = doc._create_ssh_connection()
			
			# Store in pool
			_ssh_connection_pool[pool_key] = {
				'connection': ssh,
				'created_at': datetime.now(),
				'last_used': datetime.now(),
				'doc_name': doc.name
			}
			
			frappe.logger().info(f"Created new SSH connection for {pool_key}")
			return ssh
	
	@staticmethod
	def cleanup_idle_connections():
		"""Remove idle connections from pool"""
		with _pool_lock:
			current_time = datetime.now()
			idle_keys = []
			
			for pool_key, conn_info in _ssh_connection_pool.items():
				idle_time = (current_time - conn_info['last_used']).total_seconds()
				if idle_time > _pool_max_idle_time:
					idle_keys.append(pool_key)
			
			for pool_key in idle_keys:
				try:
					_ssh_connection_pool[pool_key]['connection'].close()
				except:
					pass
				del _ssh_connection_pool[pool_key]
				frappe.logger().info(f"Cleaned up idle SSH connection: {pool_key}")
			
			return len(idle_keys)
	
	@staticmethod
	def close_connection(doc):
		"""Close specific connection"""
		with _pool_lock:
			pool_key = f"{doc.name}_{doc.server_ip}_{doc.ssh_port}"
			if pool_key in _ssh_connection_pool:
				try:
					_ssh_connection_pool[pool_key]['connection'].close()
				except:
					pass
				del _ssh_connection_pool[pool_key]
				frappe.logger().info(f"Closed SSH connection: {pool_key}")
				return True
			return False
	
	@staticmethod
	def close_all_connections():
		"""Close all connections in pool"""
		with _pool_lock:
			for pool_key, conn_info in list(_ssh_connection_pool.items()):
				try:
					conn_info['connection'].close()
				except:
					pass
			_ssh_connection_pool.clear()
			frappe.logger().info("Closed all SSH connections")
	
	@staticmethod
	def get_pool_stats():
		"""Get connection pool statistics"""
		with _pool_lock:
			stats = {
				'total_connections': len(_ssh_connection_pool),
				'connections': []
			}
			
			for pool_key, conn_info in _ssh_connection_pool.items():
				idle_time = (datetime.now() - conn_info['last_used']).total_seconds()
				stats['connections'].append({
					'key': pool_key,
					'doc_name': conn_info['doc_name'],
					'created_at': str(conn_info['created_at']),
					'last_used': str(conn_info['last_used']),
					'idle_seconds': int(idle_time)
				})
			
			return stats


@frappe.whitelist()
def get_site_domain_details(domain_name):
	"""Fetch Site Domain details for validation"""
	try:
		domain = frappe.get_doc("Site Domain", domain_name)
		return {
			"name": domain.name,
			"domain_name": domain.domain_name,
			"status": domain.status,
			"verified": domain.verified,
			"verification_method": domain.verification_method,
			"verification_token": domain.verification_token,
			"current_sites": domain.current_sites,
			"max_sites": domain.max_sites,
			"dns_provider": domain.dns_provider,
		}
	except Exception as e:
		frappe.log_error(f"Error fetching domain details: {str(e)}", "Site Domain Fetch Error")
		return None


@frappe.whitelist()
def execute_remote_command(command, realtime_key=None, name=None, user=None):
	"""Execute command on remote bench via SSH with real-time output streaming"""
	if name:
		doc = frappe.get_doc("Bench Node Manager", name)
	else:
		return {"success": False, "message": "Document name is required"}

	if doc.node_type != "Remote Node":
		return {"success": False, "message": "Only Remote Nodes can execute commands"}

	try:
		ssh = doc._get_ssh_connection()

		# Update connection status and timestamp when SSH connection succeeds
		doc.db_set("status", "Connected")
		doc.db_set("last_connected", frappe.utils.now())

		# Use bash -c to execute command with proper directory change
		full_command = f'cd "{doc.bench_path}" && {command}'
		stdin, stdout, stderr = ssh.exec_command(f'bash -c {shlex.quote(full_command)}', get_pty=True)

		output = ""
		error = ""

		if realtime_key:
			# Real-time streaming using channel
			channel = stdout.channel
			import time
			start_time = time.time()
			timeout = 300  # 5 minutes timeout
			no_data_count = 0

			while not channel.exit_status_ready():
				if time.time() - start_time > timeout:
					frappe.publish_realtime(realtime_key, "\nCommand timed out after 5 minutes", user=user or frappe.session.user)
					break

				has_data = False
				if channel.recv_ready():
					data = channel.recv(1024).decode()
					if data:
						output += data
						frappe.publish_realtime(realtime_key, data, user=user or frappe.session.user)
						has_data = True
				if channel.recv_stderr_ready():
					data = channel.recv_stderr(1024).decode()
					if data:
						error += data
						frappe.publish_realtime(realtime_key, f"ERROR: {data}", user=user or frappe.session.user)
						has_data = True

				if has_data:
					no_data_count = 0
				else:
					no_data_count += 1
					# If no data for 3 seconds and exit status not ready, assume done
					if no_data_count > 30:
						break

				time.sleep(0.1)

			# Read any remaining data after command completes
			while channel.recv_ready():
				data = channel.recv(1024).decode()
				if data:
					output += data
					frappe.publish_realtime(realtime_key, data, user=user or frappe.session.user)
			while channel.recv_stderr_ready():
				data = channel.recv_stderr(1024).decode()
				if data:
					error += data
					frappe.publish_realtime(realtime_key, f"ERROR: {data}", user=user or frappe.session.user)
		else:
			# Non-real-time: read all at once
			output = stdout.read().decode()
			error = stderr.read().decode()

		# Don't close - connection is pooled and reused
		return {"success": True, "output": output, "error": error}

	except Exception as e:
		# Update connection status to Error on failure
		if name:
			doc.db_set("status", "Error")
		return {"success": False, "message": str(e)}


class BenchNodeManager(Document):
	site_config_fields = [
		"background_workers",
		"shallow_clone",
		"admin_password",
		"auto_email_id",
		"auto_update",
		"frappe_user",
		"global_help_setup",
		"dropbox_access_key",
		"dropbox_secret_key",
		"gunicorn_workers",
		"github_username",
		"github_password",
		"mail_login",
		"mail_password",
		"mail_port",
		"mail_server",
		"use_tls",
		"rebase_on_pull",
		"redis_cache",
		"redis_queue",
		"redis_socketio",
		"restart_supervisor_on_update",
		"root_password",
		"serve_default_site",
		"socketio_port",
		"update_bench_on_update",
		"webserver_port",
		"file_watcher_port",
		"local_server_ip",
	]

	def autoname(self):
		"""Auto-generate name and node_id"""
		if self.node_type == "Local Node":
			# Only one local bench should exist
			existing = frappe.db.get_value("Bench Node Manager", {"node_type": "Local Node"}, "name")
			if existing and existing != self.name:
				frappe.throw("A Local Bench already exists. You can only have one local bench node.")
			self.name = "Local Bench"
		else:
			# For remote, use node_name or generate from server_ip
			if self.node_name:
				self.name = self.node_name
			else:
				self.name = f"Remote-{self.server_ip}"

		# Generate node_id if not set
		if not self.node_id:
			import uuid
			prefix = "LOCAL" if self.node_type == "Local Node" else "REMOTE"
			self.node_id = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"

	def set_attr(self, varname, varval):
		return setattr(self, varname, varval)

	def validate(self):
		# Validation is handled by mandatory_depends_on in JSON
		# Additional custom validation can be added here if needed
		if self.node_type == "Local Node":
			self.sync_site_config()
			self.update_git_details()
			# Auto-set status to Connected for Local Node
			if self.status != "Connected":
				self.status = "Connected"

	@frappe.whitelist()
	def render_related_resources(self):
		"""Populate HTML fields with related sites and apps"""
		if not self.name:
			return

		# Get related sites
		sites = frappe.get_all("Site", filters={"bench_node": self.name}, fields=["name", "site_name", "status"])
		sites_html = "<h4>Sites ({})</h4>".format(len(sites))
		if sites:
			sites_html += "<ul>"
			for site in sites:
				sites_html += f'<li><a href="#app/Site/{site.name}">{site.site_name}</a> - {site.status}</li>'
			sites_html += "</ul>"
		else:
			sites_html += "<p>No sites linked to this bench node.</p>"

		# Get related apps
		apps = frappe.get_all("App", filters={"bench_node": self.name}, fields=["name", "app_name", "app_title"])
		apps_html = "<h4>Apps ({})</h4>".format(len(apps))
		if apps:
			apps_html += "<ul>"
			for app in apps:
				apps_html += f'<li><a href="#app/App/{app.name}">{app.app_title} ({app.app_name})</a></li>'
			apps_html += "</ul>"
		else:
			apps_html += "<p>No apps linked to this bench node.</p>"

		self.sites_html = sites_html
		self.apps_html = apps_html

	def sync_site_config(self):
		"""Only sync for local nodes"""
		if self.node_type != "Local Node":
			return

		common_site_config_path = "common_site_config.json"
		with open(common_site_config_path, "r") as f:
			common_site_config_data = json.load(f)
		for site_config_field in self.site_config_fields:
			try:
				self.set_attr(site_config_field, common_site_config_data[site_config_field])
			except Exception:
				pass

	def update_git_details(self):
		"""Only update for local nodes"""
		if self.node_type != "Local Node":
			return

		self.frappe_git_branch = safe_decode(
			check_output(
				"git rev-parse --abbrev-ref HEAD".split(),
				cwd=os.path.join("..", "apps", "frappe"),
			)
		).strip("\n")

		# Get server IP address
		self.local_server_ip = self.get_server_ip()

	def get_server_ip(self):
		"""Get server's public IP address"""
		import socket

		try:
			import requests
			response = requests.get("https://api.ipify.org?format=json", timeout=5)
			if response.status_code == 200:
				return response.json().get("ip")
		except Exception:
			pass

		try:
			hostname = socket.gethostname()
			return socket.gethostbyname(hostname)
		except Exception:
			return None

	def _create_ssh_connection(self):
		"""Create new SSH connection based on auth method (called by pool)"""
		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

		if self.ssh_auth_method == "Private Key":
			private_key = get_decrypted_password("Bench Node Manager", self.name, "remote_ssh_private_key")
			if private_key:
				key = paramiko.RSAKey.from_private_key(StringIO(private_key))
				ssh.connect(self.server_ip, port=self.ssh_port, username=self.ssh_user, pkey=key)
			else:
				frappe.throw("SSH Private Key is required for Private Key authentication")
		else:  # Password
			password = get_decrypted_password("Bench Node Manager", self.name, "ssh_password")
			ssh.connect(self.server_ip, port=self.ssh_port, username=self.ssh_user, password=password)

		return ssh
	
	def _get_ssh_connection(self):
		"""Get SSH connection from pool (reuses existing connections)"""
		return SSHConnectionPool.get_connection(self)

	@frappe.whitelist()
	def generate_remote_key_pair(self):
		"""Generate RSA key pair for remote SSH authentication"""
		if self.node_type != "Remote Node":
			return {"success": False, "message": "Only Remote Nodes can generate SSH keys"}

		try:
			from cryptography.hazmat.backends import default_backend
			from cryptography.hazmat.primitives import serialization
			from cryptography.hazmat.primitives.asymmetric import rsa

			private_key = rsa.generate_private_key(
				public_exponent=65537,
				key_size=2048,
				backend=default_backend(),
			)
			public_key = private_key.public_key()

			private_key_pem = private_key.private_bytes(
				encoding=serialization.Encoding.PEM,
				format=serialization.PrivateFormat.TraditionalOpenSSL,
				encryption_algorithm=serialization.NoEncryption(),
			).decode("utf-8")

			public_key_openssh = public_key.public_bytes(
				encoding=serialization.Encoding.OpenSSH,
				format=serialization.PublicFormat.OpenSSH,
			).decode("utf-8")

			self.db_set("remote_ssh_private_key", private_key_pem)
			self.db_set("remote_ssh_public_key", public_key_openssh)

			return {
				"success": True,
				"public_key": public_key_openssh,
				"message": "Key pair generated. Add the public key to your remote server's ~/.ssh/authorized_keys file.",
			}

		except Exception as e:
			frappe.log_error(f"SSH key generation failed: {str(e)}", "SSH Key Generation Error")
			return {"success": False, "message": f"Failed to generate key pair: {str(e)}"}

	@frappe.whitelist()
	def discover_benches(self):
		"""Run bench doctor on remote server"""
		if self.node_type != "Remote Node":
			return {"success": False, "message": "Only Remote Nodes can run bench doctor"}

		try:
			ssh = self._get_ssh_connection()

			# Run bench doctor in the bench directory
			command = f"cd {self.bench_path} && bench doctor"
			stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)

			output = stdout.read().decode()
			error = stderr.read().decode()

			# Connection pooled - don't close
			
			return {"success": True, "output": output, "error": error}

		except Exception as e:
			return {"success": False, "message": str(e)}

	@frappe.whitelist()
	def run_remote_command(self, command):
		"""Run a command on remote bench via SSH"""
		if self.node_type != "Remote Node":
			return {"success": False, "message": "Only Remote Nodes can run commands"}

		try:
			ssh = self._get_ssh_connection()

			# Update connection status and timestamp when SSH connection succeeds
			self.db_set("status", "Connected")
			self.db_set("last_connected", frappe.utils.now())

			full_command = f"cd {self.bench_path} && {command}"
			stdin, stdout, stderr = ssh.exec_command(full_command, get_pty=True)

			output = stdout.read().decode()
			error = stderr.read().decode()

			# Connection pooled - don't close
			
			return {"success": True, "output": output, "error": error}

		except Exception as e:
			self.db_set("status", "Error")
			return {"success": False, "message": str(e)}

	@frappe.whitelist()
	def get_remote_sites(self):
		"""Fetch list of sites from remote bench"""
		if self.node_type != "Remote Node":
			return {"success": False, "message": "Only Remote Nodes can fetch sites"}

		try:
			ssh = self._get_ssh_connection()

			# Find all site directories
			command = f"find {self.bench_path}/sites -maxdepth 1 -type d ! -name 'sites' ! -name 'apps' -printf '%f\\n'"
			stdin, stdout, stderr = ssh.exec_command(command)

			sites = stdout.read().decode().strip().split("\n")
			sites = [s for s in sites if s]  # Filter empty strings

			# Connection pooled - don't close
			
			return {"success": True, "sites": sites}

		except Exception as e:
			return {"success": False, "message": str(e)}

	@frappe.whitelist()
	def get_remote_apps(self):
		"""Fetch list of apps from remote bench"""
		if self.node_type != "Remote Node":
			return {"success": False, "message": "Only Remote Nodes can fetch apps"}

		try:
			ssh = self._get_ssh_connection()

			# Find all app directories in the apps folder
			command = f"find {self.bench_path}/apps -maxdepth 1 -type d ! -name 'apps' -printf '%f\\n'"
			stdin, stdout, stderr = ssh.exec_command(command)

			apps = stdout.read().decode().strip().split("\n")
			apps = [a for a in apps if a]  # Filter empty strings

			# Connection pooled - don't close
			
			return {"success": True, "apps": apps}

		except Exception as e:
			return {"success": False, "message": str(e)}

	@frappe.whitelist()
	def test_connection(self):
		"""Test SSH connection and verify bench exists"""
		if self.node_type != "Remote Node":
			return {"success": False, "message": "Only Remote Nodes can test connection"}

		try:
			ssh = self._get_ssh_connection()

			stdin, stdout, stderr = ssh.exec_command("echo 'Connection successful'")
			output = stdout.read().decode().strip()

			if output != "Connection successful":
				# Connection pooled - don't close
				return {"success": False, "message": "SSH connection failed"}

			if self.bench_path:
				stdin, stdout, stderr = ssh.exec_command(f"test -d {self.bench_path} && echo 'EXISTS'")
				if stdout.read().decode().strip() != "EXISTS":
					# Connection pooled - don't close
					return {"success": False, "message": f"Bench path does not exist: {self.bench_path}"}

				stdin, stdout, stderr = ssh.exec_command(f"test -f {self.bench_path}/apps.txt && echo 'VALID'")
				if stdout.read().decode().strip() != "VALID":
					# Connection pooled - don't close
					return {"success": False, "message": f"Path is not a valid Frappe bench: {self.bench_path}"}

			# Connection pooled - don't close
			self.db_set("status", "Connected")
			return {"success": True, "message": "Connection successful and bench verified"}

		except Exception as e:
			self.db_set("status", "Error")
			return {"success": False, "message": str(e)}

	@frappe.whitelist()
	def ping_remote_bench(self):
		"""Test SSH connection to remote server"""
		if self.node_type != "Remote Node":
			return {"success": False, "message": "Only Remote Nodes can be pinged"}
		
		try:
			ssh = self._get_ssh_connection()
			
			# Test connection with a simple command
			stdin, stdout, stderr = ssh.exec_command("echo 'Connection successful'")
			output = stdout.read().decode()
			error = stderr.read().decode()
			
			# Connection pooled - don't close
			
			if output and "Connection successful" in output:
				# Update connection status and timestamp
				self.status = "Connected"
				self.last_connected = frappe.utils.now()
				self.save()
				return {"success": True, "message": "Successfully connected to remote server"}
			else:
				# Only set to Error if explicit connection test fails
				self.status = "Error"
				self.save()
				return {"success": False, "message": f"Connection test failed: {error}"}
			
		except Exception as e:
			self.status = "Error"
			self.save()
			return {"success": False, "message": f"Connection failed: {str(e)}"}

	@frappe.whitelist()
	def sync_remote_sites(self):
		"""Sync sites from remote bench by parsing filesystem"""
		if self.node_type != "Remote Node":
			return {"success": False, "message": "Only Remote Nodes can sync sites"}

		try:
			ssh = self._get_ssh_connection()

			command = f"find {self.bench_path} -name 'site_config.json' -type f"
			stdin, stdout, stderr = ssh.exec_command(command)

			site_paths = stdout.read().decode().strip().split("\n")
			sites_synced = 0

			for site_path in site_paths:
				if not site_path:
					continue

				site_name = site_path.split("/")[-2]

				existing_site = frappe.db.exists("Site", site_name)
				if existing_site:
					site_doc = frappe.get_doc("Site", existing_site)
				else:
					site_doc = frappe.new_doc("Site")
					site_doc.site_name = site_name
					site_doc.bench_node = self.name

				site_doc.save()
				sites_synced += 1

			# Connection pooled - don't close
			self.db_set("last_sync", frappe.utils.now())

			return {"success": True, "sites_synced": sites_synced}

		except Exception as e:
			return {"success": False, "message": str(e)}

	@frappe.whitelist()
	def sync_remote_sites_to_child_table(self):
		"""Sync remote sites to child table with detailed site information"""
		if self.node_type != "Remote Node":
			return {"success": False, "message": "Only Remote Nodes can sync sites"}

		try:
			ssh = self._get_ssh_connection()

			# Get list of sites directly from sites directory
			command = f"ls -d {self.bench_path}/sites/*/site_config.json 2>/dev/null"
			stdin, stdout, stderr = ssh.exec_command(command)
			site_paths = stdout.read().decode().strip().split("\n")

			# Clear existing child records
			self.set("remote_sites", [])

			sites_synced = 0
			sites_skipped = 0
			skipped_names = []

			# Domain validation regex (valid domain/subdomain format)
			import re
			# Must have at least one dot and valid domain characters
			domain_pattern = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]*[a-zA-Z0-9]\.[a-zA-Z]{2,}$')

			for site_path in site_paths:
				if not site_path:
					continue

				site_name = site_path.split("/")[-2]

				# Explicit validation checks
				# 1. Must contain at least one dot
				if '.' not in site_name:
					sites_skipped += 1
					skipped_names.append(site_name)
					continue

				# 2. Must not be empty or just dots
				if not site_name.replace('.', '').replace('-', '').isalnum():
					sites_skipped += 1
					skipped_names.append(site_name)
					continue

				# 3. Must match domain pattern
				if not domain_pattern.match(site_name):
					sites_skipped += 1
					skipped_names.append(site_name)
					continue

				# Read site_config.json
				command = f"cat {site_path}"
				stdin, stdout, stderr = ssh.exec_command(command)
				site_config_content = stdout.read().decode()

				try:
					import json
					site_config = json.loads(site_config_content)
				except:
					site_config = {}

				# Get installed apps for the site
				apps_command = f"cd {self.bench_path}/sites/{site_name} && bench --site {site_name} list-apps 2>/dev/null || echo '[]'"
				stdin, stdout, stderr = ssh.exec_command(apps_command)
				apps_output = stdout.read().decode().strip()

				# Parse apps list
				try:
					apps_list = [app.strip() for app in apps_output.split('\n') if app.strip() and not app.startswith('Installed')]
				except:
					apps_list = []

				# Create child record
				child = self.append("remote_sites", {})
				child.site_url = site_name
				child.status = "Online"  # Default to Online if we can connect
				child.app_list = "<br>".join(apps_list) if apps_list else ""
				child.db_name = site_config.get("db_name", "")
				child.db_password = site_config.get("db_password", "")
				child.developer_mode = site_config.get("developer_mode", 0) == 1
				child.pause_scheduler = site_config.get("pause_scheduler", 0) == 1
				child.ignore_csrf = site_config.get("ignore_csrf", 0) == 1
				child.disable_website_cache = site_config.get("disable_website_cache", 0) == 1
				child.maintenance_mode = site_config.get("maintenance_mode", 0) == 1
				child.auto_backup = site_config.get("auto_backup", 0) == 1

				sites_synced += 1

			self.save()
			# Connection pooled - don't close
			self.db_set("last_sync", frappe.utils.now())

			message = f"Successfully synced {sites_synced} sites"
			if sites_skipped > 0:
				message += f" (skipped {sites_skipped} invalid site names: {', '.join(skipped_names[:5])}{'...' if len(skipped_names) > 5 else ''})"

			return {"success": True, "sites_synced": sites_synced, "sites_skipped": sites_skipped, "skipped_names": skipped_names, "message": message}

		except Exception as e:
			return {"success": False, "message": str(e)}

	@frappe.whitelist()
	def sync_remote_apps(self):
		"""Sync apps from remote bench by parsing apps.txt"""
		if self.node_type != "Remote Node":
			return {"success": False, "message": "Only Remote Nodes can sync apps"}

		try:
			ssh = self._get_ssh_connection()

			# Read apps.txt from remote bench
			command = f"cat {self.bench_path}/apps.txt"
			stdin, stdout, stderr = ssh.exec_command(command)

			apps_content = stdout.read().decode().strip()
			remote_apps = [app for app in apps_content.split("\n") if app]
			
			app_entries = [x["app_name"] for x in frappe.get_all("App")]
			create_apps = [a for a in list(set(remote_apps) - set(app_entries)) if a]
			delete_apps = [a for a in list(set(app_entries) - set(remote_apps)) if a]

			apps_synced = 0

			for app in create_apps:
				existing_app = frappe.db.exists("App", app)
				if existing_app:
					app_doc = frappe.get_doc("App", existing_app)
				else:
					app_doc = frappe.new_doc("App")
					app_doc.app_name = app
					app_doc.app_description = "Synced from remote bench"
					app_doc.app_publisher = "Remote Bench"
					app_doc.app_email = "remote@bench"
					app_doc.bench_node = self.name

				app_doc.save()
				apps_synced += 1

			# Connection pooled - don't close
			self.db_set("last_sync", frappe.utils.now())

			return {"success": True, "apps_synced": apps_synced}

		except Exception as e:
			return {"success": False, "message": str(e)}

	@frappe.whitelist()
	def get_node_overview(self):
		"""Get system monitoring overview for both Local and Remote nodes"""
		try:
			if self.node_type == "Local Node":
				return self._get_local_node_overview()
			else:
				return self._get_remote_node_overview()
		except Exception as e:
			frappe.log_error(f"Node Overview Error: {str(e)}", "Node Overview")
			return {"success": False, "message": str(e)}

	def _get_local_node_overview(self):
		"""Get system monitoring data for local node using psutil"""
		try:
			# System Info
			import platform
			import socket
			
			system_info = {
				"hostname": socket.gethostname(),
				"os": f"{platform.system()} {platform.release()}",
				"architecture": platform.machine(),
				"uptime": self._format_uptime(psutil.boot_time())
			}
			
			# CPU Info
			cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
			cpu_info = {
				"usage_percent": round(psutil.cpu_percent(interval=0.5), 2),
				"core_count": psutil.cpu_count(logical=False),
				"thread_count": psutil.cpu_count(logical=True),
				"per_core_usage": [round(p, 2) for p in cpu_percent],
				"load_average": [round(x, 2) for x in psutil.getloadavg()]
			}
			
			# Memory Info
			mem = psutil.virtual_memory()
			swap = psutil.swap_memory()
			memory_info = {
				"total_gb": round(mem.total / (1024**3), 2),
				"used_gb": round(mem.used / (1024**3), 2),
				"available_gb": round(mem.available / (1024**3), 2),
				"percent": round(mem.percent, 2),
				"swap_total_gb": round(swap.total / (1024**3), 2),
				"swap_used_gb": round(swap.used / (1024**3), 2),
				"swap_percent": round(swap.percent, 2)
			}
			
			# Disk Info
			disk_info = []
			for partition in psutil.disk_partitions():
				try:
					usage = psutil.disk_usage(partition.mountpoint)
					disk_info.append({
						"device": partition.device,
						"mountpoint": partition.mountpoint,
						"fstype": partition.fstype,
						"total_gb": round(usage.total / (1024**3), 2),
						"used_gb": round(usage.used / (1024**3), 2),
						"free_gb": round(usage.free / (1024**3), 2),
						"percent": round(usage.percent, 2)
					})
				except:
					pass
			
			# Top Processes by CPU
			processes = []
			for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
				try:
					processes.append(proc.info)
				except (psutil.NoSuchProcess, psutil.AccessDenied):
					pass
			
			top_cpu = sorted(processes, key=lambda x: x.get('cpu_percent', 0), reverse=True)[:10]
			top_memory = sorted(processes, key=lambda x: x.get('memory_percent', 0), reverse=True)[:10]
			
			# Bench Services Status (if supervisor is available)
			bench_services = self._get_supervisor_status()
			
			return {
				"success": True,
				"node_type": "Local Node",
				"system_info": system_info,
				"cpu": cpu_info,
				"memory": memory_info,
				"disk": disk_info,
				"top_cpu_processes": top_cpu,
				"top_memory_processes": top_memory,
				"bench_services": bench_services
			}
			
		except Exception as e:
			return {"success": False, "message": str(e)}

	def _get_remote_node_overview(self):
		"""Get system monitoring data for remote node via SSH"""
		try:
			ssh = self._get_ssh_connection()
			
			# System Info
			stdin, stdout, stderr = ssh.exec_command("uname -a && uptime && hostname")
			uname_output = stdout.read().decode().strip().split('\n')
			
			system_info = {
				"hostname": uname_output[2] if len(uname_output) > 2 else "Unknown",
				"os": uname_output[0] if len(uname_output) > 0 else "Unknown",
				"uptime": uname_output[1] if len(uname_output) > 1 else "Unknown"
			}
			
			# CPU Info
			stdin, stdout, stderr = ssh.exec_command("nproc && cat /proc/loadavg && top -bn1 | grep 'Cpu(s)'")
			cpu_output = stdout.read().decode().strip().split('\n')
			
			cpu_info = {
				"core_count": int(cpu_output[0]) if cpu_output else 0,
				"load_average": cpu_output[1].split()[:3] if len(cpu_output) > 1 else [],
				"usage_info": cpu_output[2] if len(cpu_output) > 2 else ""
			}
			
			# Memory Info
			stdin, stdout, stderr = ssh.exec_command("free -g")
			mem_output = stdout.read().decode().strip().split('\n')
			
			memory_info = {"raw_output": mem_output}
			if len(mem_output) > 1:
				mem_line = mem_output[1].split()
				if len(mem_line) >= 3:
					memory_info.update({
						"total_gb": mem_line[1],
						"used_gb": mem_line[2],
						"free_gb": mem_line[3] if len(mem_line) > 3 else "0"
					})
			
			# Disk Info
			stdin, stdout, stderr = ssh.exec_command("df -h")
			disk_output = stdout.read().decode().strip().split('\n')
			
			disk_info = []
			for line in disk_output[1:]:  # Skip header
				parts = line.split()
				if len(parts) >= 6:
					disk_info.append({
						"filesystem": parts[0],
						"size": parts[1],
						"used": parts[2],
						"available": parts[3],
						"percent": parts[4],
						"mountpoint": parts[5]
					})
			
			# Top Processes by CPU
			stdin, stdout, stderr = ssh.exec_command("ps aux --sort=-%cpu | head -11")
			top_cpu_output = stdout.read().decode().strip().split('\n')
			
			# Top Processes by Memory
			stdin, stdout, stderr = ssh.exec_command("ps aux --sort=-%mem | head -11")
			top_mem_output = stdout.read().decode().strip().split('\n')
			
			# Bench Services Status
			bench_services = []
			if self.bench_path:
				stdin, stdout, stderr = ssh.exec_command("sudo -n supervisorctl status all 2>/dev/null || echo 'No supervisor access'")
				services_output = stdout.read().decode().strip()
				bench_services = services_output.split('\n') if services_output else []
			
			return {
				"success": True,
				"node_type": "Remote Node",
				"system_info": system_info,
				"cpu": cpu_info,
				"memory": memory_info,
				"disk": disk_info,
				"top_cpu_processes": top_cpu_output,
				"top_memory_processes": top_mem_output,
				"bench_services": bench_services
			}
			
		except Exception as e:
			return {"success": False, "message": str(e)}

	def _format_uptime(self, boot_time):
		"""Format uptime from boot timestamp"""
		uptime_seconds = datetime.now().timestamp() - boot_time
		days = int(uptime_seconds // 86400)
		hours = int((uptime_seconds % 86400) // 3600)
		minutes = int((uptime_seconds % 3600) // 60)
		return f"{days}d {hours}h {minutes}m"

	def _get_supervisor_status(self):
		"""Get supervisor status for bench services"""
		try:
			result = check_output(['sudo', '-n', 'supervisorctl', 'status', 'all'], stderr=STDOUT)
			services = []
			for line in result.decode().strip().split('\n'):
				if line:
					services.append(line)
			return services
		except:
			return []

	@frappe.whitelist()
	def reboot_node(self):
		"""Reboot the node (local or remote)"""
		try:
			if self.node_type == "Local Node":
				# Reboot local node
				import subprocess
				subprocess.Popen(['sudo', 'reboot', 'now'])
				return {
					"success": True,
					"message": "Local node reboot initiated. System will restart shortly."
				}
			else:
				# Reboot remote node via SSH
				ssh = self._get_ssh_connection()
				stdin, stdout, stderr = ssh.exec_command("sudo reboot now")
				
				return {
					"success": True,
					"message": "Remote node reboot initiated. System will restart shortly."
				}
		except Exception as e:
			frappe.log_error(f"Reboot Node Error: {str(e)}", "Node Reboot")
			return {
				"success": False,
				"message": f"Failed to reboot node: {str(e)}"
			}

	@frappe.whitelist()
	def console_command(self, key, caller, app_name=None, branch_name=None, name=None, site_name=None, mysql_root_password=None, admin_password=None):
		# Build commands dynamically based on caller
		if caller == "delete_site":
			if mysql_root_password:
				commands = ["bench drop-site {site_name} --db-root-password {mysql_root_password}".format(site_name=site_name, mysql_root_password=mysql_root_password)]
			else:
				commands = ["bench drop-site {site_name}".format(site_name=site_name)]
		elif caller == "delete_site_force":
			if mysql_root_password:
				commands = ["bench drop-site {site_name} --force --db-root-password {mysql_root_password}".format(site_name=site_name, mysql_root_password=mysql_root_password)]
			else:
				commands = ["bench drop-site {site_name} --force".format(site_name=site_name)]
		elif caller == "new_site":
			commands = ["bench new-site {site_name} --db-root-password {mysql_root_password} --admin-password {admin_password}".format(site_name=site_name, mysql_root_password=mysql_root_password, admin_password=admin_password)]
		elif caller == "install_app":
			commands = ["bench --site {site_name} install-app {app_name}".format(site_name=site_name, app_name=app_name)]
		elif caller == "uninstall_app":
			commands = ["bench --site {site_name} uninstall-app {app_name}".format(site_name=site_name, app_name=app_name)]
		elif caller == "bench_clear_cache":
			if site_name:
				commands = ["bench --site {site_name} clear-cache".format(site_name=site_name)]
			else:
				commands = ["bench clear-cache"]
		elif caller == "get-app" or caller == "add_app":
			commands = ["bench get-app {app_name}".format(app_name=app_name)]
		elif caller == "remove_app":
			commands = ["bench remove-app {app_name}".format(app_name=app_name)]
		elif caller == "bench_pip_install":
			commands = ["bench pip install {app_name}".format(app_name=app_name)]
		else:
			commands = {
				"bench_update": ["bench update"],
				"bench_restart": ["sudo -n supervisorctl restart all"],
				"bench_status": ["sudo -n supervisorctl status all"],
				"bench_setup_requirements": ["bench setup requirements"],
				"bench_build": ["bench build"],
				"switch_branch": [""],
			}.get(caller, [""])

		if self.node_type == "Remote Node":
			full_command = " && ".join(commands)
			# Call directly for synchronous execution and reliable realtime
			return execute_remote_command(command=full_command, realtime_key=key, name=self.name, user=frappe.session.user)
		else:
			frappe.enqueue(
				"bench_manager.bench_manager.utils.run_command",
				commands=commands,
				doctype=self.doctype,
				key=key,
				docname=self.name,
			)


# ---------------------------------------------------------------------------
# Module-level wrappers for instance methods
# frm.call() sends 'doctype' and 'name' in form_dict, not 'docname'.
# ---------------------------------------------------------------------------

def _get_bench_node_doc(name=None):
	if not name:
		name = frappe.form_dict.get("name") or frappe.form_dict.get("docname")
	if not name:
		# Last resort: if there's only one Bench Node Manager, use it
		records = frappe.get_all("Bench Node Manager", limit=2)
		if len(records) == 1:
			return frappe.get_doc("Bench Node Manager", records[0].name)
		frappe.throw("Document name is required")
	return frappe.get_doc("Bench Node Manager", name)

@frappe.whitelist()
def ping_remote_bench(name=None):
	verify_whitelisted_call()
	return _get_bench_node_doc(name).ping_remote_bench()

@frappe.whitelist()
def run_remote_command(command=None, name=None):
	verify_whitelisted_call()
	return _get_bench_node_doc(name).run_remote_command(command)

@frappe.whitelist()
def get_remote_sites(name=None):
	verify_whitelisted_call()
	return _get_bench_node_doc(name).get_remote_sites()

@frappe.whitelist()
def get_remote_apps(name=None):
	verify_whitelisted_call()
	return _get_bench_node_doc(name).get_remote_apps()

@frappe.whitelist()
def test_connection(name=None, **kwargs):
	return _get_bench_node_doc(name).test_connection()

@frappe.whitelist()
def discover_benches(name=None, **kwargs):
	return _get_bench_node_doc(name).discover_benches()


@frappe.whitelist()
def sync_remote_sites(name=None, **kwargs):
	return _get_bench_node_doc(name).sync_remote_sites()

@frappe.whitelist()
def sync_remote_sites_to_child_table(name=None, **kwargs):
	return _get_bench_node_doc(name).sync_remote_sites_to_child_table()

@frappe.whitelist()
def generate_remote_key_pair(name=None, **kwargs):
	return _get_bench_node_doc(name).generate_remote_key_pair()

@frappe.whitelist()
def render_related_resources(name=None, **kwargs):
	return _get_bench_node_doc(name).render_related_resources()

@frappe.whitelist()
def console_command(key=None, caller=None, app_name=None, branch_name=None, name=None, site_name=None, mysql_root_password=None, admin_password=None, **kwargs):
	return _get_bench_node_doc(name).console_command(key=key, caller=caller, app_name=app_name, branch_name=branch_name, name=name, site_name=site_name, mysql_root_password=mysql_root_password, admin_password=admin_password)


# ---------------------------------------------------------------------------
# Module-level whitelisted functions
# ---------------------------------------------------------------------------

@frappe.whitelist()
def sync_sites(bench_node=None):
	verify_whitelisted_call()
	# If no bench_node specified, sync from local bench
	if not bench_node:
		bench_node = frappe.db.get_value("Bench Node Manager", {"node_type": "Local Node"}, "name")
	if not bench_node:
		return

	bench_doc = frappe.get_doc("Bench Node Manager", bench_node)
	
	# For remote nodes, use SSH to sync sites
	if bench_doc.node_type == "Remote Node":
		return bench_doc.sync_remote_sites()
	
	# For local nodes, use filesystem scanning
	site_dirs = update_site_list()
	site_entries = [x["name"] for x in frappe.get_all("Site")]
	create_sites = list(set(site_dirs) - set(site_entries))
	delete_sites = list(set(site_entries) - set(site_dirs))

	for site in create_sites:
		doc = frappe.get_doc({
			"doctype": "Site",
			"site_name": site,
			"developer_flag": 1,
			"bench_node": bench_node,
		})
		doc.insert()
		frappe.db.commit()

	for site in delete_sites:
		doc = frappe.get_doc("Site", site)
		doc.developer_flag = 1
		doc.save()
		doc.delete()
		frappe.db.commit()


@frappe.whitelist()
def sync_apps(bench_node=None):
	verify_whitelisted_call()
	# If no bench_node specified, sync from local bench
	if not bench_node:
		bench_node = frappe.db.get_value("Bench Node Manager", {"node_type": "Local Node"}, "name")
	if not bench_node:
		return

	bench_doc = frappe.get_doc("Bench Node Manager", bench_node)
	
	# For remote nodes, use SSH to sync apps
	if bench_doc.node_type == "Remote Node":
		return bench_doc.sync_remote_apps()
	
	# For local nodes, use filesystem scanning
	app_dirs = update_app_list()
	app_entries = [x["name"] for x in frappe.get_all("App")]
	create_apps = [a for a in list(set(app_dirs) - set(app_entries)) if a]
	delete_apps = [a for a in list(set(app_entries) - set(app_dirs)) if a]

	for app in create_apps:
		doc = frappe.get_doc({
			"doctype": "App",
			"app_name": app,
			"app_description": "lorem ipsum",
			"app_publisher": "lorem ipsum",
			"app_email": "lorem ipsum",
			"developer_flag": 1,
			"bench_node": bench_node,
		})
		doc.insert()
		frappe.db.commit()

	for app in delete_apps:
		doc = frappe.get_doc("App", app)
		doc.developer_flag = 1
		doc.save()
		doc.delete()
		frappe.db.commit()


def update_app_list():
	with open("apps.txt", "r") as f:
		return f.read().split("\n")


def update_site_list():
	site_list = []
	for root, dirs, files in os.walk(".", topdown=True):
		for name in files:
			if name == "site_config.json":
				site_list.append(str(root).strip("./"))
				break
	if "" in site_list:
		site_list.remove("")
	return site_list


@frappe.whitelist()
def get_local_sites():
	"""Fetch list of sites from local bench"""
	try:
		site_list = update_site_list()
		return {"success": True, "sites": site_list}
	except Exception as e:
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def sync_backups():
	verify_whitelisted_call()
	backup_dirs_data = update_backup_list()
	backup_entries = [x["name"] for x in frappe.get_all("Site Backup")]
	backup_dirs = [
		x["date"] + " " + x["time"] + " " + x["site_name"] + " " + x["stored_location"]
		for x in backup_dirs_data
	]
	create_backups = list(set(backup_dirs) - set(backup_entries))
	delete_backups = list(set(backup_entries) - set(backup_dirs))

	for date_time_sitename_loc in create_backups:
		parts = date_time_sitename_loc.split(" ")
		backup = {}
		for x in backup_dirs_data:
			if (
				x["date"] == parts[0]
				and x["time"] == parts[1]
				and x["site_name"] == parts[2]
				and x["stored_location"] == parts[3]
			):
				backup = x
				break
		doc = frappe.get_doc({
			"doctype": "Site Backup",
			"site_name": backup["site_name"],
			"date": backup["date"],
			"time": backup["time"],
			"stored_location": backup["stored_location"],
			"public_file_backup": backup["public_file_backup"],
			"private_file_backup": backup["private_file_backup"],
			"hash": backup["hash"],
			"file_path": backup["file_path"],
			"developer_flag": 1,
		})
		doc.insert()
		frappe.db.commit()

	for backup in delete_backups:
		doc = frappe.get_doc("Site Backup", backup)
		doc.developer_flag = 1
		doc.save()
		frappe.db.commit()
		doc.delete()
		frappe.db.commit()


def update_backup_list():
	all_sites = []

	archived_sites = []
	for root, dirs, files in os.walk("../archived_sites/", topdown=True):
		archived_sites.extend(dirs)
		break
	all_sites.extend(["../archived_sites/" + x for x in archived_sites])

	sites = []
	for root, dirs, files in os.walk("../sites/", topdown=True):
		for site in dirs:
			if os.path.isfile("../sites/{}/site_config.json".format(site)):
				sites.append(site)
		break
	all_sites.extend(["../sites/" + x for x in sites])

	response = []

	for site in all_sites:
		backup_path = os.path.join(site, "private", "backups")
		backup_files = (
			safe_decode(
				check_output(shlex.split("ls ./{backup_path}".format(backup_path=backup_path)))
			)
			.strip("\n")
			.split("\n")
		)
		backup_files = [f for f in backup_files if "database.sql" in f]

		for backup_file in backup_files:
			inner_response = {}
			date_time_hash = backup_file.rsplit("-", 1)[0]
			file_path = backup_path + "/" + date_time_hash
			inner_response["site_name"] = site.split("/")[2]
			inner_response["stored_location"] = site.split("/")[1]
			inner_response["private_file_backup"] = os.path.isfile(
				backup_path + "/" + date_time_hash + "_private_files.tar"
			)
			inner_response["public_file_backup"] = os.path.isfile(
				backup_path + "/" + date_time_hash + "_files.tar"
			)
			inner_response["file_path"] = file_path[3:]
			try:
				inner_response["date"] = get_date(date_time_hash)
				inner_response["time"] = get_time(date_time_hash)
				inner_response["hash"] = get_hash(date_time_hash)
			except IndexError:
				inner_response["date"] = str(datetime.now().date())
				inner_response["time"] = str(datetime.now().time())
				inner_response["hash"] = " "
				traceback.print_exception(*sys.exc_info())
			response.append(inner_response)

	return response


def get_date(date_time_hash):
	return date_time_hash[:4] + "-" + date_time_hash[4:6] + "-" + date_time_hash[6:8]


def get_time(date_time_hash):
	time = date_time_hash.split("_")[1]
	return time[0:2] + ":" + time[2:4] + ":" + time[4:6]


def get_hash(date_time_hash):
	return date_time_hash.split("-")[1]


@frappe.whitelist()
def test_github_connection(username, token):
	"""Test GitHub connection with provided credentials"""
	verify_whitelisted_call()
	import requests

	try:
		headers = {
			"Authorization": f"Bearer {token}",
			"Accept": "application/vnd.github.v3+json",
		}
		response = requests.get("https://api.github.com/user", headers=headers, timeout=10)

		if response.status_code == 200:
			user_data = response.json()
			return {
				"success": True,
				"name": user_data.get("name") or user_data.get("login"),
				"login": user_data.get("login"),
				"public_repos": user_data.get("public_repos", 0),
				"total_private_repos": user_data.get("total_private_repos", 0),
				"email": user_data.get("email"),
			}
		elif response.status_code == 401:
			return {"success": False, "error": "Invalid credentials. Please check your Personal Access Token."}
		elif response.status_code == 403:
			return {"success": False, "error": "Access forbidden. Token may not have required permissions (needs 'repo' scope)."}
		else:
			return {"success": False, "error": f"GitHub API error: {response.status_code}"}

	except requests.exceptions.Timeout:
		return {"success": False, "error": "Connection timeout. Please check your internet connection."}
	except requests.exceptions.RequestException as e:
		frappe.log_error(f"GitHub connection test failed: {str(e)}", "GitHub Test Error")
		return {"success": False, "error": f"Connection error: {str(e)}"}
	except Exception as e:
		frappe.log_error(f"Unexpected error testing GitHub: {str(e)}", "GitHub Test Error")
		return {"success": False, "error": "Unexpected error occurred. Please check error logs."}


@frappe.whitelist()
def generate_ssh_keys(git_user_email=None):
	"""Generate SSH keys for GitHub authentication.

	NOTE: Previously referenced `self` — converted to accept email as a parameter.
	The caller should pass the email from the doc before calling this whitelisted fn.
	"""
	verify_whitelisted_call()
	import subprocess

	try:
		home_dir = os.path.expanduser("~")
		ssh_dir = os.path.join(home_dir, ".ssh")

		if not os.path.exists(ssh_dir):
			os.makedirs(ssh_dir, mode=0o700)

		key_path = os.path.join(ssh_dir, "github_bench_manager")
		email = git_user_email or "bench@example.com"

		result = subprocess.run(
			["ssh-keygen", "-t", "ed25519", "-C", email, "-f", key_path, "-N", ""],
			capture_output=True,
			text=True,
		)

		if result.returncode != 0:
			return {"success": False, "error": f"SSH key generation failed: {result.stderr}"}

		with open(f"{key_path}.pub", "r") as f:
			public_key = f.read().strip()

		with open(key_path, "r") as f:
			private_key = f.read().strip()

		# Configure SSH config file
		ssh_config_path = os.path.join(ssh_dir, "config")
		ssh_config_content = (
			"\n# GitHub Bench Manager Configuration\n"
			"Host github.com\n"
			"    HostName github.com\n"
			"    User git\n"
			f"    IdentityFile {key_path}\n"
			"    StrictHostKeyChecking no\n"
		)

		if os.path.exists(ssh_config_path):
			with open(ssh_config_path, "r") as f:
				existing_config = f.read()
			if "GitHub Bench Manager Configuration" not in existing_config:
				with open(ssh_config_path, "a") as f:
					f.write(ssh_config_content)
		else:
			with open(ssh_config_path, "w") as f:
				f.write(ssh_config_content)
		os.chmod(ssh_config_path, 0o600)

		return {
			"success": True,
			"public_key": public_key,
			"private_key": private_key,
			"message": "SSH keys generated successfully! Add the public key to your GitHub account.",
		}

	except Exception as e:
		frappe.log_error(f"SSH key generation failed: {str(e)}", "SSH Key Generation Error")
		return {"success": False, "error": f"Error: {str(e)}"}


@frappe.whitelist()
def test_ssh_connection():
	"""Test SSH connection to GitHub.

	NOTE: Previously referenced `self` — connection status update removed from here;
	caller should update the doc field based on the returned result.
	"""
	verify_whitelisted_call()
	import subprocess

	try:
		result = subprocess.run(
			["ssh", "-T", "git@github.com"],
			capture_output=True,
			text=True,
			timeout=10,
		)

		if "successfully authenticated" in result.stderr.lower():
			return {
				"success": True,
				"message": "SSH connection to GitHub successful!",
				"output": result.stderr,
			}
		else:
			return {
				"success": False,
				"error": "SSH connection failed. Make sure you have added the public key to GitHub.",
				"output": result.stderr,
			}

	except subprocess.TimeoutExpired:
		return {"success": False, "error": "Connection timeout. Please check your internet connection."}
	except Exception as e:
		frappe.log_error(f"SSH connection test failed: {str(e)}", "SSH Test Error")
		return {"success": False, "error": f"Error: {str(e)}"}


@frappe.whitelist()
def setup_git_remote_ssh(app_name):
	"""Convert app's git remote from HTTPS to SSH"""
	verify_whitelisted_call()
	import subprocess

	try:
		app_path = os.path.join("..", "apps", app_name)

		result = subprocess.run(
			["git", "remote", "get-url", "origin"],
			cwd=app_path,
			capture_output=True,
			text=True,
		)

		if result.returncode != 0:
			return {"success": False, "error": "Failed to get remote URL"}

		current_url = result.stdout.strip()

		if current_url.startswith("https://github.com/"):
			match = re.search(r"https://github\.com/(.+/.+?)(\.git)?$", current_url)
			if match:
				repo_path = match.group(1)
				if not repo_path.endswith(".git"):
					repo_path += ".git"
				ssh_url = f"git@github.com:{repo_path}"

				result = subprocess.run(
					["git", "remote", "set-url", "origin", ssh_url],
					cwd=app_path,
					capture_output=True,
					text=True,
				)

				if result.returncode == 0:
					return {"success": True, "message": f"Remote URL changed to SSH: {ssh_url}"}
				else:
					return {"success": False, "error": result.stderr}
		elif current_url.startswith("git@github.com:"):
			return {"success": True, "message": "Already using SSH"}
		else:
			return {"success": False, "error": "Unknown remote URL format"}

	except Exception as e:
		frappe.log_error(f"Git remote setup failed: {str(e)}", "Git Remote Setup Error")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def search_github_repos(keyword, language=None, sort="stars", order="desc", per_page=100, page=1):
	"""Search GitHub repositories by keyword"""
	verify_whitelisted_call()
	import requests

	try:
		local_bench = frappe.db.get_value("Bench Node Manager", {"node_type": "Local Node"}, "name")
		github_token = ""
		if local_bench:
			github_token = frappe.db.get_value("Bench Node Manager", local_bench, "github_password") or ""

		query = keyword
		if language:
			query += f" language:{language}"

		url = "https://api.github.com/search/repositories"
		params = {"q": query, "sort": sort, "order": order, "per_page": per_page, "page": page}
		headers = {"Accept": "application/vnd.github.v3+json"}

		if github_token:
			headers["Authorization"] = f"Bearer {github_token}"

		response = requests.get(url, params=params, headers=headers, timeout=10)

		# Retry without auth on 401
		if response.status_code == 401 and github_token:
			headers.pop("Authorization", None)
			response = requests.get(url, params=params, headers=headers, timeout=10)

		if response.status_code == 200:
			data = response.json()
			repositories = [
				{
					"name": repo.get("name"),
					"full_name": repo.get("full_name"),
					"description": repo.get("description", "") or "No description",
					"url": repo.get("html_url"),
					"stars": repo.get("stargazers_count", 0),
					"forks": repo.get("forks_count", 0),
					"language": repo.get("language", "Unknown"),
					"updated_at": repo.get("updated_at"),
					"topics": repo.get("topics", []),
				}
				for repo in data.get("items", [])
			]
			return {
				"success": True,
				"repositories": repositories,
				"total_count": data.get("total_count", 0),
				"keyword": keyword,
			}
		elif response.status_code == 403:
			return {"success": False, "error": "Rate limit exceeded. Please try again later or add a GitHub token."}
		elif response.status_code == 422:
			return {"success": False, "error": "Invalid search query. Please check your keyword."}
		else:
			return {"success": False, "error": f"GitHub API error: {response.status_code}"}

	except requests.exceptions.Timeout:
		return {"success": False, "error": "Connection timeout. Please check your internet connection."}
	except requests.exceptions.RequestException as e:
		frappe.log_error(f"GitHub search failed: {str(e)}", "GitHub Search Error")
		return {"success": False, "error": f"Connection error: {str(e)}"}
	except Exception as e:
		frappe.log_error(f"Unexpected error searching GitHub: {str(e)}", "GitHub Search Error")
		return {"success": False, "error": "Unexpected error occurred. Please check error logs."}


@frappe.whitelist()
def sync_all(bench_node=None, in_background=False):
	if not in_background:
		frappe.msgprint("Sync has started and will run in the background...")
	verify_whitelisted_call()
	
	# If no bench_node specified, sync from local bench
	if not bench_node:
		bench_node = frappe.db.get_value("Bench Node Manager", {"node_type": "Local Node"}, "name")
	
	frappe.enqueue(
		"bench_manager.bench_manager.doctype.bench_node_manager.bench_node_manager.sync_sites",
		bench_node=bench_node,
		queue="long",
	)
	frappe.enqueue(
		"bench_manager.bench_manager.doctype.bench_node_manager.bench_node_manager.sync_apps",
		bench_node=bench_node,
		queue="long",
	)
	frappe.enqueue(
		"bench_manager.bench_manager.doctype.bench_node_manager.bench_node_manager.sync_backups",
		queue="long",
	)
	
	# Update last_sync_timestamp on the bench being synced
	if bench_node:
		frappe.set_value(
			"Bench Node Manager", bench_node, "last_sync_timestamp", frappe.utils.time.time()
		)


def auto_sync_all():
	"""Automatic sync for scheduler — runs hourly without user interaction"""
	try:
		local_bench = frappe.db.get_value("Bench Node Manager", {"node_type": "Local Node"}, "name")
		frappe.enqueue(
			"bench_manager.bench_manager.doctype.bench_node_manager.bench_node_manager.sync_sites",
			bench_node=local_bench,
			queue="long",
		)
		frappe.enqueue(
			"bench_manager.bench_manager.doctype.bench_node_manager.bench_node_manager.sync_apps",
			bench_node=local_bench,
			queue="long",
		)
		frappe.enqueue(
			"bench_manager.bench_manager.doctype.bench_node_manager.bench_node_manager.sync_backups",
			queue="long",
		)
		if local_bench:
			frappe.set_value(
				"Bench Node Manager", local_bench, "last_sync_timestamp", frappe.utils.time.time()
			)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(f"Auto sync failed: {str(e)}", "Bench Manager Auto Sync")


@frappe.whitelist()
def setup_and_restart_nginx(root_password):
	now = datetime.now()
	dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
	commands = ["bench setup nginx --yes"]
	commands.append(f"echo '{root_password}' | sudo -S service nginx restart")
	run_command(commands, "Bench Node Manager", dt_string)


def run_command(commands, doctype, key, cwd="..", docname=" ", after_command=None):
	start_time = frappe.utils.time.time()
	console_dump = ""
	logged_command = " && ".join(commands)
	logged_command += " "  # ensure trailing password is also hidden

	sensitive_data = ["--mariadb-root-password", "--admin-password", "--root-password"]
	for password in sensitive_data:
		logged_command = re.sub(
			"{password} .*? ".format(password=password), "", logged_command, flags=re.DOTALL
		)

	# Mask sudo password from echo '...' | sudo -S ...
	parts = logged_command.split("'")
	if len(parts) >= 3:
		the_password = parts[1]
		logged_command = logged_command.replace(the_password, "******")

	doc = frappe.get_doc({
		"doctype": "Bench Manager Command",
		"key": key,
		"source": doctype + ": " + docname,
		"command": logged_command,
		"status": "Ongoing",
	})
	doc.insert()
	frappe.db.commit()

	frappe.publish_realtime(
		key,
		"Executing Command:\n{logged_command}\n\n".format(logged_command=logged_command),
		user=frappe.session.user,
	)

	try:
		for command in commands:
			terminal = Popen(
				shlex.split(command), stdin=PIPE, stdout=PIPE, stderr=STDOUT, cwd=cwd
			)
			for c in iter(lambda: safe_decode(terminal.stdout.read(1)), ""):
				frappe.publish_realtime(key, c, user=frappe.session.user)
			if terminal.wait():
				_close_the_doc(start_time, key, console_dump, status="Failed", user=frappe.session.user)
			else:
				_close_the_doc(start_time, key, console_dump, status="Success", user=frappe.session.user)
	except Exception:
		_close_the_doc(start_time, key, console_dump, status="Failed", user=frappe.session.user)
	finally:
		frappe.db.commit()
		frappe.enqueue(
			"bench_manager.bench_manager.utils._refresh",
			doctype=doctype,
			docname=docname,
			commands=commands,
		)


# ---------------------------------------------------------------------------
# Backup scheduler hooks
# ---------------------------------------------------------------------------

def backup_sites_with_daily_option():
	site_list = frappe.get_list("Site", filters={"frequency": "Daily", "auto_backup": 1, "dropbox_backup": 0})
	if site_list:
		create_backup(site_list)


def backup_sites_with_weekly_option():
	site_list = frappe.get_list("Site", filters={"frequency": "Weekly", "auto_backup": 1, "dropbox_backup": 0})
	if site_list:
		create_backup(site_list)


def backup_sites_with_monthly_option():
	site_list = frappe.get_list("Site", filters={"frequency": "Monthly", "auto_backup": 1, "dropbox_backup": 0})
	if site_list:
		create_backup(site_list)


def dropbox_backup_sites_with_daily_option():
	site_list = frappe.get_list("Site", filters={"frequency": "Daily", "auto_backup": 1, "dropbox_backup": 1})
	if site_list:
		take_dropbox_backup(site_list)


def dropbox_backup_sites_with_weekly_option():
	site_list = frappe.get_list("Site", filters={"frequency": "Weekly", "auto_backup": 1, "dropbox_backup": 1})
	if site_list:
		take_dropbox_backup(site_list)


def dropbox_backup_sites_with_monthly_option():
	site_list = frappe.get_list("Site", filters={"frequency": "Monthly", "auto_backup": 1, "dropbox_backup": 1})
	if site_list:
		take_dropbox_backup(site_list)


def create_backup(site_list):
	from bench_manager.bench_manager.utils import run_command as _run_command
	for i in site_list:
		site_doc = frappe.get_doc("Site", i.name)
		key = (datetime.now() + timedelta(seconds=1)).strftime("%Y/%m/%d, %H:%M:%S")
		commands = ["bench --site {site_name} backup --with-files".format(site_name=i.name)]
		_run_command(commands, site_doc.doctype, key, docname=i.name)


def take_dropbox_backup(site_list):
	"""Enqueue long job for taking backup to Dropbox"""
	enqueue(
		"bench_manager.bench_manager.doctype.bench_node_manager.bench_node_manager.take_backup_to_dropbox",
		site_list=site_list,
		queue="long",
		timeout=1500,
	)
	frappe.msgprint(_("Queued for backup. It may take a few minutes to an hour."))


def take_backup_to_dropbox(site_list, retry_count=0, upload_db_backup=True):
	try:
		backup_to_dropbox(site_list, upload_db_backup)
		if cint(frappe.db.get_value("Bench Node Manager", None, "send_email_for_successful_backup")):
			send_email(True, "Dropbox", "Bench Node Manager", "send_notifications_to")
	except JobTimeoutException:
		if retry_count < 2:
			enqueue(
				"bench_manager.bench_manager.doctype.bench_node_manager.bench_node_manager.take_backup_to_dropbox",
				queue="long",
				timeout=1500,
				retry_count=retry_count + 1,
				upload_db_backup=False,
			)
	except Exception:
		error_message = frappe.get_traceback()
		send_email(False, "Dropbox", "Bench Node Manager", "send_notifications_to", error_message)


# ---------------------------------------------------------------------------
# Dropbox helpers
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_dropbox_authorize_url():
	app_details = get_dropbox_settings(redirect_uri=True)
	dropbox_oauth_flow = dropbox.DropboxOAuth2Flow(
		consumer_key=app_details["app_key"],
		redirect_uri=app_details["redirect_uri"],
		session={},
		csrf_token_session_key="dropbox-auth-csrf-token",
		consumer_secret=app_details["app_secret"],
	)
	auth_url = dropbox_oauth_flow.start()
	return {"auth_url": auth_url, "args": parse_qs(urlparse(auth_url).query)}


@frappe.whitelist()
def get_redirect_url():
	if not frappe.conf.dropbox_broker_site:
		frappe.conf.dropbox_broker_site = "https://dropbox.erpnext.com"
	url = "{0}/api/method/dropbox_erpnext_broker.www.setup_dropbox.get_authotize_url".format(
		frappe.conf.dropbox_broker_site
	)
	try:
		response = make_post_request(url, data={"site": get_url()})
		if response.get("message"):
			return response["message"]
	except Exception:
		frappe.log_error()
		frappe.throw(
			_(
				"Something went wrong while generating dropbox access token. "
				"Please check error log for more details."
			)
		)


def backup_to_dropbox(site_list, upload_db_backup=True):
	if not frappe.db:
		frappe.connect()

	dropbox_settings = get_dropbox_settings()

	if not dropbox_settings["access_token"]:
		access_token = generate_oauth2_access_token_from_oauth1_token(dropbox_settings)
		if not access_token.get("oauth2_token"):
			return (
				"Failed backup upload",
				"No Access Token exists! Please generate the access token for Dropbox.",
			)
		dropbox_settings["access_token"] = access_token["oauth2_token"]
		set_dropbox_access_token(access_token["oauth2_token"])

	dropbox_client = dropbox.Dropbox(
		oauth2_access_token=dropbox_settings["access_token"], timeout=None
	)

	if upload_db_backup and site_list:
		create_backup(site_list)
		sync_backups()
		for i in site_list:
			last_doc = frappe.get_list(
				"Site Backup",
				filters={"site_name": i.name},
				fields=["file_path"],
				order_by="creation desc",
				limit=1,
			)[0]
			parts = last_doc.file_path.split("/")
			parts.pop(0)
			parts.insert(0, ".")
			base_path = "/".join(parts)
			upload_file_to_dropbox(base_path + "-database.sql.gz", f"/{i.name}", dropbox_client)
			upload_file_to_dropbox(base_path + "-site_config_backup.json", f"/{i.name}", dropbox_client)
			upload_file_to_dropbox(base_path + "-private-files.tar", f"/{i.name}", dropbox_client)
			upload_file_to_dropbox(base_path + "-files.tar", f"/{i.name}", dropbox_client)


def upload_file_to_dropbox(filename, folder, dropbox_client):
	"""Upload files in 15 MB chunks to reduce session append calls"""
	if not os.path.exists(filename):
		return

	create_folder_if_not_exists(folder, dropbox_client)
	file_size = os.path.getsize(encode(filename))
	chunk_size = get_chunk_site(file_size)
	mode = dropbox.files.WriteMode.overwrite

	f = open(encode(filename), "rb")
	path = "{0}/{1}".format(folder, os.path.basename(filename))

	try:
		if file_size <= chunk_size:
			dropbox_client.files_upload(f.read(), path, mode)
		else:
			upload_session_start_result = dropbox_client.files_upload_session_start(f.read(chunk_size))
			cursor = dropbox.files.UploadSessionCursor(
				session_id=upload_session_start_result.session_id, offset=f.tell()
			)
			commit = dropbox.files.CommitInfo(path=path, mode=mode)

			while f.tell() < file_size:
				if (file_size - f.tell()) <= chunk_size:
					dropbox_client.files_upload_session_finish(f.read(chunk_size), cursor, commit)
				else:
					dropbox_client.files_upload_session_append(
						f.read(chunk_size), cursor.session_id, cursor.offset
					)
					cursor.offset = f.tell()
	except dropbox.exceptions.ApiError as e:
		if isinstance(e.error, dropbox.files.UploadError):
			error = "File Path: {path}\n".format(path=path)
			error += frappe.get_traceback()
			frappe.log_error(error)
		else:
			raise


def create_folder_if_not_exists(folder, dropbox_client):
	try:
		dropbox_client.files_get_metadata(folder)
	except dropbox.exceptions.ApiError as e:
		if isinstance(e.error, dropbox.files.GetMetadataError):
			dropbox_client.files_create_folder(folder)
		else:
			raise


def get_dropbox_settings(redirect_uri=False):
	if not frappe.conf.dropbox_broker_site:
		frappe.conf.dropbox_broker_site = "https://dropbox.erpnext.com"
	settings = frappe.get_doc("Bench Node Manager")
	app_details = {
		"app_key": settings.app_access_key or frappe.conf.dropbox_access_key,
		"app_secret": settings.get_password(fieldname="app_secret_key", raise_exception=False)
		if settings.app_secret_key
		else frappe.conf.dropbox_secret_key,
		"access_token": settings.get_password("dropbox_access_token", raise_exception=False)
		if settings.dropbox_access_token
		else "",
		"access_key": settings.get_password("dropbox_access_key", raise_exception=False),
		"access_secret": settings.get_password("dropbox_access_secret", raise_exception=False),
		"file_backup": settings.file_backup,
	}

	if redirect_uri:
		app_details.update({
			"redirect_uri": get_request_site_address(True)
			+ "/api/method/bench_manager.bench_manager.doctype.bench_node_manager.bench_node_manager.dropbox_auth_finish"
			if settings.app_secret_key
			else frappe.conf.dropbox_broker_site
			+ "/api/method/dropbox_erpnext_broker.www.setup_dropbox.generate_dropbox_access_token",
		})

	if not app_details["app_key"] or not app_details["app_secret"]:
		raise Exception(_("Please set Dropbox access keys in your site config"))

	return app_details


@frappe.whitelist()
def dropbox_auth_finish(return_access_token=False):
	app_details = get_dropbox_settings(redirect_uri=True)
	callback = frappe.form_dict
	close = '<p class="text-muted">' + _("Please close this window") + "</p>"

	dropbox_oauth_flow = dropbox.DropboxOAuth2Flow(
		consumer_key=app_details["app_key"],
		redirect_uri=app_details["redirect_uri"],
		session={"dropbox-auth-csrf-token": callback.state},
		csrf_token_session_key="dropbox-auth-csrf-token",
		consumer_secret=app_details["app_secret"],
	)

	if callback.state or callback.code:
		token = dropbox_oauth_flow.finish({"state": callback.state, "code": callback.code})
		if return_access_token and token.access_token:
			return token.access_token, callback.state
		set_dropbox_access_token(token.access_token)
	else:
		frappe.respond_as_web_page(
			_("Dropbox Setup"),
			_("Illegal Access Token. Please try again") + close,
			indicator_color="red",
			http_status_code=frappe.AuthenticationError.http_status_code,
		)

	frappe.respond_as_web_page(
		_("Dropbox Setup"),
		_("Dropbox access is approved!") + close,
		indicator_color="green",
	)


def set_dropbox_access_token(access_token):
	frappe.db.set_value("Bench Node Manager", None, "dropbox_access_token", access_token)
	frappe.db.commit()


def generate_oauth2_access_token_from_oauth1_token(dropbox_settings=None):
	if not dropbox_settings.get("access_key") or not dropbox_settings.get("access_secret"):
		return {}


# ---------------------------------------------------------------------------
# SSH Connection Pool for AsyncSSH
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# WebSocket Handler for Real-time SSH Terminal
# ---------------------------------------------------------------------------

@frappe.whitelist()
def cleanup_idle_ssh_connections():
	"""Scheduled job to cleanup idle SSH connections."""
	SSHConnectionPool.cleanup_idle_connections()


@frappe.whitelist()
def cleanup_ssh_pool():
	"""Cleanup idle SSH connections from pool"""
	verify_whitelisted_call()
	cleaned = SSHConnectionPool.cleanup_idle_connections()
	return {
		"success": True,
		"message": f"Cleaned up {cleaned} idle connections",
		"cleaned_count": cleaned
	}


@frappe.whitelist()
def get_ssh_pool_stats():
	"""Get SSH connection pool statistics"""
	verify_whitelisted_call()
	return {
		"success": True,
		"stats": SSHConnectionPool.get_pool_stats()
	}


@frappe.whitelist()
def close_ssh_connection(name=None):
	"""Close SSH connection for specific node"""
	verify_whitelisted_call()
	doc = _get_bench_node_doc(name)
	closed = SSHConnectionPool.close_connection(doc)
	return {
		"success": closed,
		"message": "Connection closed" if closed else "No active connection found"
	}


@frappe.whitelist()
def close_all_ssh_connections():
	"""Close all SSH connections in pool"""
	verify_whitelisted_call()
	SSHConnectionPool.close_all_connections()
	return {
		"success": True,
		"message": "All SSH connections closed"
	}


@frappe.whitelist()
def test_ssh_websocket_connection(name: str):
	"""
	Test SSH connection pool and WebSocket functionality.
	This verifies if AsyncSSH connection pool is working correctly.
	
	Args:
		name: Bench Node Manager document name
	
	Returns:
		dict with test results
	"""
	doc = frappe.get_doc("Bench Node Manager", name)
	
	if doc.node_type != "Remote Node":
		return {"success": False, "message": "Only Remote Nodes can be tested"}
	
	try:
		# Test connection pool
		ssh = doc._get_ssh_connection()
		
		# Test simple command
		stdin, stdout, stderr = ssh.exec_command("echo 'SSH Connection Test Successful'")
		output = stdout.read().decode().strip()
		error = stderr.read().decode().strip()
		
		# Get pool stats
		pool_stats = SSHConnectionPool.get_pool_stats()
		
		return {
			"success": True,
			"message": "SSH Connection Pool Test Successful",
			"output": output,
			"error": error if error else None,
			"pool_stats": pool_stats
		}
		
	except Exception as e:
		doc.db_set("status", "Error")
		return {
			"success": False,
			"message": f"SSH Connection Test Failed: {str(e)}",
			"error_type": type(e).__name__
		}