# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappé and contributors
# For license information, please see license.txt


import json
import os
import re
import shlex
import time
from subprocess import PIPE, Popen, check_output

import frappe
import pymysql
from bench_manager.bench_manager.utils import (
	safe_decode,
	verify_whitelisted_call,
)
from frappe.model.document import Document
from bench_manager.bench_manager.doctype.bench_settings.bench_settings import sync_sites
class Site(Document):
	site_config_fields = [
		"maintenance_mode",
		"pause_scheduler",
		"db_name",
		"db_password",
		"developer_mode",
		"disable_website_cache" "limits",
	]
	limits_fields = ["emails", "expiry", "space", "space_usage"]
	space_usage_fields = ["backup_size", "database_size", "files_size", "total"]

	def get_attr(self, varname):
		return getattr(self, varname)

	def set_attr(self, varname, varval):
		return setattr(self, varname, varval)

	def validate(self):
		# Auto-populate site_url if empty
		if not self.site_url and self.site_name:
			self.site_url = f"http://{self.site_name}"
		
		if self.get("__islocal"):
			if self.developer_flag == 0:
				self.create_site(self.key)
			site_config_path = self.site_name + "/site_config.json"
			while not os.path.isfile(site_config_path):
				time.sleep(2)
			self.sync_site_config()
			self.app_list = "frappe"
		else:
			if self.developer_flag == 0:
				self.update_site_config()
				self.sync_site_config()

	def after_command(self, commands=None):
		frappe.publish_realtime("Bench-Manager:reload-page")

	@frappe.whitelist()
	def populate_site_url(self):
		"""Populate site_url from site_name if empty"""
		if not self.site_url and self.site_name:
			self.site_url = f"http://{self.site_name}"
			self.save()
			return {"success": True, "site_url": self.site_url}
		return {"success": False, "message": "Site URL already populated or site name missing"}

	@frappe.whitelist()
	def update_app_alias(self):
		self.update_app_list()
		self.update_site_alias()

	def update_app_list(self):
		# self.set_attr("app_list", '\n'.join(self.get_installed_apps()))
		self.db_set("app_list", "\n".join(self.get_installed_apps()))

	def update_site_alias(self):
		alias_list = ""
		for link in os.listdir("."):
			if os.path.islink(link) and self.name in os.path.realpath(link):
				alias_list += link + "\n"
		self.db_set("site_alias", alias_list)

	def get_installed_apps(self):
		all_sites = safe_decode(check_output("ls")).strip("\n").split("\n")

		if self.site_name not in all_sites:
			list_apps = "frappe"
		else:
			list_apps = check_output(
				shlex.split("bench --site {site_name} list-apps".format(site_name=self.site_name)),
				cwd="..",
			)

		if "frappe" not in safe_decode(list_apps):
			list_apps = "frappe"
		return safe_decode(list_apps).strip("\n").split("\n")

	def update_site_config(self):
		site_config_path = os.path.join(self.site_name, "site_config.json")
		common_site_config_path = os.path.join("common_site_config.json")

		with open(site_config_path, "r") as f:
			site_config_data = json.load(f)
		with open(common_site_config_path, "r") as f:
			common_site_config_data = json.load(f)

		editable_site_config_fields = [
			"maintenance_mode",
			"pause_scheduler",
			"developer_mode",
			"disable_website_cache",
		]

		for site_config_field in editable_site_config_fields:
			if (
				self.get_attr(site_config_field) == None or self.get_attr(site_config_field) == ""
			):
				if site_config_data.get(site_config_field) != None:
					site_config_data.pop(site_config_field)
				self.set_attr(site_config_field, common_site_config_data.get(site_config_field))

			elif (
				not common_site_config_data.get(site_config_field)
				or self.get_attr(site_config_field) != common_site_config_data[site_config_field]
			):
				site_config_data[site_config_field] = self.get_attr(site_config_field)

			elif self.get_attr(site_config_field) == common_site_config_data[site_config_field]:
				if site_config_data.get(site_config_field) != None:
					site_config_data.pop(site_config_field)

			os.remove(site_config_path)
			with open(site_config_path, "w") as f:
				json.dump(site_config_data, f, indent=4)

	def sync_site_config(self):
		if os.path.isfile(self.site_name + "/site_config.json"):
			site_config_path = self.site_name + "/site_config.json"
			with open(site_config_path, "r") as f:
				site_config_data = json.load(f)
				for site_config_field in self.site_config_fields:
					if site_config_data.get(site_config_field):
						self.set_attr(site_config_field, site_config_data[site_config_field])

				if site_config_data.get("limits"):
					for limits_field in self.limits_fields:
						if site_config_data.get("limits").get(limits_field):
							self.set_attr(limits_field, site_config_data["limits"][limits_field])

					if site_config_data.get("limits").get("space_usage"):
						for space_usage_field in self.space_usage_fields:
							if site_config_data.get("limits").get("space_usage").get(space_usage_field):
								self.set_attr(
									space_usage_field, site_config_data["limits"]["space_usage"][space_usage_field]
								)
		else:
			frappe.throw("The site you're trying to access doesn't actually exist.")

	@frappe.whitelist()
	def create_alias(self, key, alias):
		files = check_output("ls")
		if alias in files:
			frappe.throw("Sitename already exists")
		else:
			self.console_command(key=key, caller="create-alias", alias=alias)

	@frappe.whitelist()
	def check_site_status(self):
		"""Check if site is up and running"""
		import requests
		from datetime import datetime
		
		if not self.site_url:
			# Auto-detect URL from site_name
			self.site_url = f"http://{self.site_name}"
		
		try:
			start_time = datetime.now()
			response = requests.get(self.site_url, timeout=10, allow_redirects=True)
			end_time = datetime.now()
			
			response_time = (end_time - start_time).total_seconds() * 1000  # Convert to milliseconds
			
			if response.status_code == 200:
				self.db_set('site_status', 'Online')
				self.db_set('response_time', response_time)
			else:
				self.db_set('site_status', 'Error')
				self.db_set('response_time', response_time)
				
			self.db_set('last_checked', datetime.now())
			
			return {
				'status': self.site_status,
				'response_time': response_time,
				'status_code': response.status_code
			}
			
		except requests.exceptions.Timeout:
			self.db_set('site_status', 'Offline')
			self.db_set('last_checked', datetime.now())
			return {'status': 'Offline', 'error': 'Timeout'}
			
		except requests.exceptions.ConnectionError:
			self.db_set('site_status', 'Offline')
			self.db_set('last_checked', datetime.now())
			return {'status': 'Offline', 'error': 'Connection Error'}
			
		except Exception as e:
			self.db_set('site_status', 'Error')
			self.db_set('last_checked', datetime.now())
			frappe.log_error(f"Site monitoring error for {self.site_name}: {str(e)}")
			return {'status': 'Error', 'error': str(e)}

	@frappe.whitelist()
	def console_command(
		self, key, caller, alias=None, app_name=None, admin_password=None, mysql_password=None
	):
		# Use Bench Settings passwords instead of hardcoded dev_config
		bench_settings = frappe.get_single("Bench Settings")
		
		# Get passwords with fallback
		if not admin_password:
			admin_password = bench_settings.get("admin_password") or ""
		if not mysql_password:
			mysql_password = bench_settings.get("mysql_root_password") or ""
		
		# Log for debugging (without exposing actual passwords)
		frappe.log_error(
			f"console_command called: caller={caller}, admin_pwd_set={bool(admin_password)}, mysql_pwd_set={bool(mysql_password)}",
			"Bench Manager Password Debug"
		)
		
		# Validate passwords for operations that need them
		if caller in ["reinstall", "drop_site"]:
			if not mysql_password:
				frappe.throw("MySQL Root Password is required. Please set it in Bench Settings > Password Settings > MySQL Root Password")
			if caller == "reinstall" and not admin_password:
				frappe.throw("Admin Password is required. Please set it in Bench Settings > Password Settings > Default Admin Password")
		
		site_abspath = None
		if alias:
			site_abspath = os.path.abspath(os.path.join(self.name))
		commands = {
			"migrate": ["bench --site {site_name} migrate".format(site_name=self.name)],
			"create-alias": [
				"ln -s {site_abspath} sites/{alias}".format(site_abspath=site_abspath, alias=alias)
			],
			"delete-alias": ["rm sites/{alias}".format(alias=alias)],
			"backup": [
				"bench --site {site_name} backup --with-files".format(site_name=self.name)
			],
			"reinstall": [
				"bench --site {site_name} reinstall --yes --admin-password '{admin_password}' --mariadb-root-password '{mysql_password}'".format(
					site_name=self.name, admin_password=admin_password, mysql_password=mysql_password
				)
			],
			"install_app": [
				"bench --site {site_name} install-app {app_name}".format(
					site_name=self.name, app_name=app_name
				)
			],
			"uninstall_app": [
				"bench --site {site_name} uninstall-app {app_name} --yes".format(
					site_name=self.name, app_name=app_name
				)
			],
			"drop_site": [
				"bench drop-site {site_name} --root-password {mysql_password}".format(
					site_name=self.name, mysql_password=mysql_password
				)
			],
		}
		frappe.enqueue(
			"bench_manager.bench_manager.utils.run_command",
			commands=commands[caller],
			doctype=self.doctype,
			key=key,
			docname=self.name,
		)
		return "executed"


@frappe.whitelist()
def get_installable_apps(doctype, docname):
	verify_whitelisted_call()
	app_list_file = "apps.txt"
	with open(app_list_file, "r") as f:
		apps = f.read().split("\n")
	installed_apps = frappe.get_doc(doctype, docname).app_list.split("\n")
	installable_apps = set(apps) - set(installed_apps)
	return [x for x in installable_apps]


@frappe.whitelist()
def get_removable_apps(doctype, docname):
	verify_whitelisted_call()
	removable_apps = frappe.get_doc(doctype, docname).app_list.split("\n")
	
	# Extract only app names (first word before version/branch info)
	app_names = []
	for app in removable_apps:
		if app.strip():
			# Split by whitespace and take first part (app name only)
			app_name = app.strip().split()[0]
			if app_name and app_name != "frappe":
				app_names.append(app_name)
	
	return app_names


@frappe.whitelist()
def pass_exists(doctype, docname=""):
	verify_whitelisted_call()
	# return string convention 'TT',<root_password>,<admin_password>
	ret = {"condition": "", "root_password": "", "admin_password": ""}
	common_site_config_path = "common_site_config.json"
	with open(common_site_config_path, "r") as f:
		common_site_config_data = json.load(f)

	# Get passwords from common_site_config, fallback to Bench Settings
	root_password = common_site_config_data.get("root_password")
	admin_password = common_site_config_data.get("admin_password")
	
	# If not in common_site_config, get from Bench Settings
	if not root_password or not admin_password:
		try:
			bench_settings = frappe.get_single("Bench Settings")
			if not root_password:
				root_password = bench_settings.get("mysql_root_password") or ""
			if not admin_password:
				admin_password = bench_settings.get("admin_password") or ""
		except Exception:
			pass

	ret["condition"] += "T" if root_password else "F"
	ret["root_password"] = root_password

	ret["condition"] += "T" if admin_password else "F"
	ret["admin_password"] = admin_password

	if docname == "":  # Prompt reached here on new-site
		return ret

	site_config_path = docname + "/site_config.json"
	
	# Check if site config file exists before trying to read it
	if not os.path.isfile(site_config_path):
		# Site doesn't exist or already deleted, return defaults
		return ret
	
	try:
		with open(site_config_path, "r") as f:
			site_config_data = json.load(f)
		# FF FT TF
		if ret["condition"][1] == "F":
			ret["condition"] = (
				ret["condition"][0] + "T" if site_config_data.get("admin_password") else "F"
			)
			ret["admin_password"] = site_config_data.get("admin_password")
		else:
			if site_config_data.get("admin_password"):
				ret["condition"] = ret["condition"][0] + "T"
				ret["admin_password"] = site_config_data.get("admin_password")
	except (FileNotFoundError, json.JSONDecodeError):
		# If file doesn't exist or is corrupted, return defaults
		pass
	
	return ret


@frappe.whitelist()
def get_bench_settings_passwords():
	"""Debug method to check what passwords are stored in Bench Settings"""
	verify_whitelisted_call()
	try:
		bench_settings = frappe.get_single("Bench Settings")
		return {
			"admin_password_set": bool(bench_settings.get("admin_password")),
			"mysql_root_password_set": bool(bench_settings.get("mysql_root_password")),
			"password_root_set": bool(bench_settings.get("password_root")),
			"admin_password_length": len(bench_settings.get("admin_password") or ""),
			"mysql_root_password_length": len(bench_settings.get("mysql_root_password") or ""),
			"password_root_length": len(bench_settings.get("password_root") or "")
		}
	except Exception as e:
		return {"error": str(e)}


@frappe.whitelist()
def verify_password(site_name, mysql_password):
	verify_whitelisted_call()
	
	# If no password provided, try to get from Bench Settings
	if not mysql_password:
		try:
			bench_settings = frappe.get_single("Bench Settings")
			mysql_password = bench_settings.get("mysql_root_password") or ""
			if not mysql_password:
				frappe.throw("MySQL Root Password not set in Bench Settings. Please set it in Bench Settings > Password Settings > MySQL Root Password")
		except Exception as e:
			frappe.log_error(f"Error getting MySQL password from Bench Settings: {str(e)}")
			frappe.throw("Could not retrieve MySQL password from Bench Settings")
	
	try:
		db = pymysql.connect(
			host=frappe.conf.db_host or "localhost", user="root", passwd=mysql_password
		)
		db.close()
	except Exception as e:
		frappe.log_error(f"MySQL connection failed: {str(e)}")
		frappe.throw(f"MySQL password is incorrect. Please verify the password in Bench Settings > Password Settings > MySQL Root Password. Error: {str(e)}")
	return "console"


@frappe.whitelist()
def check_site_name_available(site_name):
	"""Check if site name is available and valid"""
	verify_whitelisted_call()
	import re
	
	checks = {
		"available": True,
		"valid": True,
		"message": "",
		"suggestions": []
	}
	
	# Format validation (lowercase alphanumeric, dots, hyphens)
	if not re.match(r'^[a-z0-9.-]+$', site_name):
		checks["valid"] = False
		checks["message"] = "Site name can only contain lowercase letters, numbers, dots (.) and hyphens (-)"
		return checks
	
	# Length validation (3-63 characters)
	if len(site_name) < 3:
		checks["valid"] = False
		checks["message"] = "Site name must be at least 3 characters long"
		return checks
	
	if len(site_name) > 63:
		checks["valid"] = False
		checks["message"] = "Site name must not exceed 63 characters"
		return checks
	
	# Start/end validation
	if site_name.startswith(('-', '.')) or site_name.endswith(('-', '.')):
		checks["valid"] = False
		checks["message"] = "Site name cannot start or end with hyphen or dot"
		return checks
	
	# Check if site exists
	try:
		sites = safe_decode(check_output("ls")).strip("\n").split("\n")
		if site_name in sites:
			checks["available"] = False
			checks["message"] = "Site already exists"
			
			# Generate suggestions
			for i in range(1, 4):
				suggestion = f"{site_name}{i}"
				if suggestion not in sites:
					checks["suggestions"].append(suggestion)
			
			return checks
	except:
		pass
	
	checks["message"] = "Site name is available"
	return checks


@frappe.whitelist()
def get_system_info():
	"""Get system information for site creation"""
	verify_whitelisted_call()
	import shutil
	
	info = {
		"disk_space_gb": 0,
		"disk_available": True,
		"estimated_time_minutes": 2,
		"warning": ""
	}
	
	try:
		# Get disk space
		stat = shutil.disk_usage(".")
		info["disk_space_gb"] = round(stat.free / (1024**3), 2)
		
		# Check if enough space (need at least 1GB)
		if info["disk_space_gb"] < 1:
			info["disk_available"] = False
			info["warning"] = f"Low disk space: {info['disk_space_gb']} GB available. Need at least 1 GB."
		
	except Exception as e:
		frappe.log_error(f"Error getting disk space: {str(e)}")
		info["warning"] = "Could not check disk space"
	
	return info


@frappe.whitelist()
def get_available_apps():
	"""Get all available apps for installation"""
	verify_whitelisted_call()
	
	try:
		# Get all apps from App DocType
		apps = frappe.get_all('App', 
			fields=['name', 'app_title', 'app_description', 'app_publisher', 'version'],
			order_by='app_title')
		
		# frappe is always installed, exclude it
		apps = [app for app in apps if app.name != 'frappe']
		
		# Add metadata for popular apps
		popular_apps = ['erpnext', 'hrms', 'healthcare', 'education']
		
		for app in apps:
			app['is_popular'] = app.name in popular_apps
			app['display_name'] = app.app_title or app.name.replace('_', ' ').title()
			app['description'] = app.app_description or f"{app.display_name} application"
		
		return apps
		
	except Exception as e:
		frappe.log_error(f"Error getting available apps: {str(e)}")
		return []


@frappe.whitelist()
def create_site(site_name, install_erpnext=None, apps_to_install=None, mysql_password=None, admin_password=None, key=None, a_async=True):
	verify_whitelisted_call()
	import json
	
	# Get passwords from Bench Settings if not provided
	if not mysql_password or not admin_password:
		bench_settings = frappe.get_single("Bench Settings")
		if not mysql_password:
			mysql_password = bench_settings.get("mysql_root_password") or "root"
		if not admin_password:
			admin_password = bench_settings.get("admin_password") or "admin"
	
	commands = [
		"bench new-site --mariadb-root-password {mysql_password} --admin-password {admin_password} --no-mariadb-socket {site_name}".format(
			site_name=site_name, admin_password=admin_password, mysql_password=mysql_password
		)
	]
	
	# Handle multiple apps installation
	if apps_to_install:
		try:
			# Parse JSON string to list
			if isinstance(apps_to_install, str):
				apps_list = json.loads(apps_to_install)
			else:
				apps_list = apps_to_install
			
			if apps_list:
				# Install each selected app
				for app_name in apps_list:
					commands.append(
						"bench --site {site_name} install-app {app_name}".format(
							site_name=site_name, app_name=app_name
						)
					)
				# Run migrate after all apps installed
				commands.append(f"bench --site {site_name} migrate")
		except Exception as e:
			frappe.log_error(f"Error parsing apps_to_install: {str(e)}")
	
	# Legacy support for install_erpnext parameter
	elif install_erpnext == "true":
		with open("apps.txt", "r") as f:
			app_list = f.read()
		if "erpnext" not in app_list:
			commands.append("bench get-app erpnext")
		commands.append(
			"bench --site {site_name} install-app erpnext".format(site_name=site_name)
		)
		commands.append(f"bench --site {site_name} migrate")
	
	frappe.enqueue(
		"bench_manager.bench_manager.doctype.site.site.jop_site_creation",
		commands=commands,
		doctype="Bench Settings",
		key=key,
		site_name = site_name,
		is_async = a_async
	)

def jop_site_creation(commands, doctype, key,site_name):
    from bench_manager.bench_manager.utils import run_command
    run_command(commands=commands,doctype="Bench Settings",key=key)
    sync_sites()
    site = frappe.get_doc("Site",site_name)
    if site.developer_flag == 1:
            site.update_app_list()
    site.save()
    frappe.db.commit()


def check_all_sites():
	"""Scheduler task to check all sites"""
	sites = frappe.get_all('Site', fields=['name', 'site_url'])
	
	for site in sites:
		try:
			site_doc = frappe.get_doc('Site', site.name)
			site_doc.check_site_status()
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(f"Error checking site {site.name}: {str(e)}", "Site Monitoring")
			continue