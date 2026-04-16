# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappé and contributors
# For license information, please see license.txt


import os
import re
import shlex
import time
from subprocess import PIPE, STDOUT, Popen, check_output

import frappe
from bench_manager.bench_manager.utils import (
	safe_decode,
	verify_whitelisted_call,
)
from frappe.model.document import Document


class App(Document):
	app_info_fields = [
		"app_title",
		"app_description",
		"app_publisher",
		"app_email",
		"app_icon",
		"app_color",
		"app_license",
	]

	def validate(self):
		if self.get("__islocal"):
			if self.developer_flag == 0:
				frappe.throw("Creation of new apps is not supported at the moment!")
			self.developer_flag = 0
			# Wait for PKG-INFO with timeout (max 30 seconds)
			app_data_path = os.path.join(
				"..",
				"apps",
				self.app_name,
				"{app_name}.egg-info".format(app_name=self.app_name),
				"PKG-INFO",
			)
			wait_time = 0
			max_wait = 30
			while not os.path.isfile(app_data_path) and wait_time < max_wait:
				time.sleep(2)
				wait_time += 2
			self.update_app_details()
		else:
			if self.developer_flag == 0:
				self.update_app_details()

	def onload(self):
		self.update_app_details()

	def get_attr(self, varname):
		return getattr(self, varname)

	def set_attr(self, varname, varval):
		return setattr(self, varname, varval)

	def after_command(self, commands=None):
		frappe.publish_realtime("Bench-Manager:reload-page")

	def on_trash(self):
		# Allow deletion if user has Administrator role
		if self.developer_flag == 0 and 'Administrator' not in frappe.get_roles():
			frappe.throw("Not allowed!")
		else:
			apps_file = "apps.txt"
			with open(apps_file, "r") as f:
				apps = f.readlines()
			try:
				apps.remove(self.app_name)
			except:
				try:
					apps.remove(self.app_name + "\n")
				except:
					pass
			os.remove(apps_file)
			with open(apps_file, "w") as f:
				f.writelines(apps)
			if self.app_name != "":
				# Try to remove app directory if it exists
				app_dir = os.path.join("..", "apps", self.app_name)
				if os.path.exists(app_dir):
					check_output(shlex.split("rm -r ../apps/{app_name}".format(app_name=self.app_name)))

	def update_app_details(self):
		import glob
		import site
		
		# Try multiple locations for PKG-INFO/METADATA
		metadata_file = None
		
		# Location 1: App directory .egg-info
		pkg_info_file = os.path.join(
			"..",
			"apps",
			self.app_name,
			"{app_name}.egg-info".format(app_name=self.app_name),
			"PKG-INFO",
		)
		if os.path.isfile(pkg_info_file):
			metadata_file = pkg_info_file
		else:
			# Location 2: App directory .dist-info
			dist_info_pattern = os.path.join("..", "apps", self.app_name, f"{self.app_name}-*.dist-info")
			dist_info_dirs = glob.glob(dist_info_pattern)
			if dist_info_dirs:
				# Try PKG-INFO first, then METADATA
				pkg_info_path = os.path.join(dist_info_dirs[0], "PKG-INFO")
				metadata_path = os.path.join(dist_info_dirs[0], "METADATA")
				if os.path.isfile(pkg_info_path):
					metadata_file = pkg_info_path
				elif os.path.isfile(metadata_path):
					metadata_file = metadata_path
			
			# Location 3: Virtual environment site-packages
			if not metadata_file:
				site_packages = site.getsitepackages()
				for site_pkg in site_packages:
					# Check egg-info in venv
					venv_pkg_info = os.path.join(site_pkg, f"{self.app_name}.egg-info", "PKG-INFO")
					if os.path.isfile(venv_pkg_info):
						metadata_file = venv_pkg_info
						break
					
					# Check dist-info in venv
					venv_dist_pattern = os.path.join(site_pkg, f"{self.app_name}-*.dist-info")
					venv_dist_dirs = glob.glob(venv_dist_pattern)
					if venv_dist_dirs:
						pkg_info_path = os.path.join(venv_dist_dirs[0], "PKG-INFO")
						metadata_path = os.path.join(venv_dist_dirs[0], "METADATA")
						if os.path.isfile(pkg_info_path):
							metadata_file = pkg_info_path
							break
						elif os.path.isfile(metadata_path):
							metadata_file = metadata_path
							break
		
		if metadata_file:
			with open(metadata_file, "r") as f:
				app_data = f.readlines()
			app_data = frappe.as_unicode("".join(app_data)).split("\n")
			if "" in app_data:
				app_data.remove("")
			app_data = [x + "\n" for x in app_data]
			for data in app_data:
				if "Version:" in data:
					self.version = "".join(re.findall("Version: (.*?)\\n", data))
				elif "Summary:" in data:
					self.app_description = "".join(re.findall("Summary: (.*?)\\n", data))
				elif "Author:" in data:
					self.app_publisher = "".join(re.findall("Author: (.*?)\\n", data))
				elif "Author-email:" in data:
					self.app_email = "".join(re.findall("Author-email: (.*?)\\n", data))
			self.app_title = self.app_name
			self.app_title = self.app_title.replace("-", " ")
			self.app_title = self.app_title.replace("_", " ")
			if os.path.isdir(os.path.join("..", "apps", self.app_name, ".git")):
				self.current_git_branch = safe_decode(
					check_output(
						"git rev-parse --abbrev-ref HEAD".split(),
						cwd=os.path.join("..", "apps", self.app_name),
					)
				).strip("\n")
				self.is_git_repo = True
			else:
				self.current_git_branch = None
				self.is_git_repo = False
		else:
			# Gracefully handle missing metadata - set defaults from app name
			self.app_title = self.app_name.replace("-", " ").replace("_", " ").title()
			self.version = "Unknown"
			self.app_description = f"App: {self.app_name}"
			self.app_publisher = "Unknown"
			self.app_email = ""
			if os.path.isdir(os.path.join("..", "apps", self.app_name, ".git")):
				self.current_git_branch = safe_decode(
					check_output(
						"git rev-parse --abbrev-ref HEAD".split(),
						cwd=os.path.join("..", "apps", self.app_name),
					)
				).strip("\n")
				self.is_git_repo = True
			else:
				self.current_git_branch = None
				self.is_git_repo = False

	@frappe.whitelist()
	def pull_rebase(self, key, remote):
		remote, branch_name = remote.split("/")
		self.console_command(
			key=key, caller="pull-rebase", branch_name=branch_name, remote=remote
		)

	@frappe.whitelist()
	def console_command(self, key, caller, branch_name=None, remote=None, commit_msg=None, force=0):
		# Get git user configuration from Bench Settings
		bench_settings = frappe.get_single("Bench Settings")
		github_username = bench_settings.get("github_username") or ""
		git_user_email = bench_settings.get("git_user_email") or ""
		use_ssh = bench_settings.get("use_ssh_for_git") or 0
		
		# Prepare git config commands if credentials are available
		git_config_commands = []
		if github_username:
			git_config_commands.append(f'git config user.name "{github_username}"')
		if git_user_email:
			git_config_commands.append(f'git config user.email "{git_user_email}"')
		
		# Prepare git push setup commands
		git_push_setup = []
		env_vars = {}
		
		# Check if we should use SSH or HTTPS
		if use_ssh:
			# For SSH, ensure remote is using SSH URL
			import subprocess
			import re
			try:
				app_path = os.path.join("..", "apps", self.name)
				result = subprocess.run(
					['git', 'remote', 'get-url', 'origin'],
					cwd=app_path,
					capture_output=True,
					text=True
				)
				if result.returncode == 0:
					current_url = result.stdout.strip()
					# Convert HTTPS to SSH if needed
					if current_url.startswith('https://github.com/'):
						match = re.search(r'https://github\.com/(.+/.+?)(\.git)?$', current_url)
						if match:
							repo_path = match.group(1)
							if not repo_path.endswith('.git'):
								repo_path += '.git'
							ssh_url = f'git@github.com:{repo_path}'
							git_push_setup.append(f'git remote set-url origin {ssh_url}')
			except:
				pass  # If conversion fails, continue with existing URL
		
		commands = {
			"git_init": git_config_commands + ["git init", "git add .", "git commit -m 'Initial Commit'"],
			"switch_branch": ["git checkout {branch_name}".format(branch_name=branch_name)],
			"new_branch": ["git branch {branch_name}".format(branch_name=branch_name)],
			"delete_branch": ["git branch -D {branch_name}".format(branch_name=branch_name)],
			"git_fetch": ["git fetch --all"],
			"status": ["git status"],
			"track-remote": [
				"git checkout -b {branch_name} -t {remote}".format(
					branch_name=branch_name, remote=remote
				)
			],
			"pull-rebase": [
				"git pull --rebase {remote} {branch_name}".format(
					branch_name=branch_name, remote=remote
				)
			],
			"commit": git_config_commands + [
				"git add .",
				'git commit -m "{commit_msg}"'.format(commit_msg=commit_msg),
			],
			"push": git_push_setup + ["git push"],
			"stash": ["git add .", "git stash"],
			"apply-stash": ["git stash apply"],
			"remove_app": [f"bench remove-app {self.name}" + (" --force" if force else "")],
		}
		frappe.enqueue(
			"bench_manager.bench_manager.utils.run_command",
			commands=commands[caller],
			cwd=os.path.join("..", "apps", self.name),
			doctype=self.doctype,
			key=key,
			docname=self.name,
			env_vars=env_vars if env_vars else None,
		)


@frappe.whitelist()
def get_branches(doctype, docname, current_branch):
	verify_whitelisted_call()
	app_path = os.path.join("..", "apps", docname)  #'../apps/'+docname
	branches = (check_output("git branch".split(), cwd=app_path)).split()
	branches.remove("*")
	branches.remove(current_branch)
	return branches


@frappe.whitelist()
def get_remotes(docname):
	command = "git branch -r"
	remotes = (
		safe_decode(
			check_output(shlex.split(command), cwd=os.path.join("..", "apps", docname))
		)
		.strip("\n")
		.split("\n  ")
	)
	remotes = [remote for remote in remotes if "HEAD" not in remote]
	return remotes
