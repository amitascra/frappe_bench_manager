# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

import os
import re
import shlex
import time
from subprocess import PIPE, STDOUT, Popen, check_output
from datetime import datetime

import frappe
from bench_manager.bench_manager.utils import (
	safe_decode,
	verify_whitelisted_call,
)
from bench_manager.bench_manager.helpers.github_api import GitHubAPI
from bench_manager.bench_manager.helpers.version_utils import (
	extract_version_from_tag,
	get_latest_version,
	is_prerelease,
	compare_versions
)
from frappe.model.document import Document
from frappe.utils import now_datetime


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
			# Set bench_node to Local Bench (apps are always local)
			self.bench_node = "Local Bench"
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

	def before_save(self):
		"""Store old category to update counts if category changes"""
		if not self.get("__islocal"):
			self._old_category = self.get_db_value("category")

	def on_save(self):
		"""Update category app_count when app is saved"""
		# Update old category count if category changed
		if hasattr(self, "_old_category") and self._old_category != self.category:
			if self._old_category:
				self._update_category_count(self._old_category)
		
		# Update new category count
		if self.category:
			self.update_category_app_count()

	def _update_category_count(self, category_name):
		"""Helper method to update category count"""
		try:
			category = frappe.get_doc("App Category", category_name)
			category.update_app_count()
		except frappe.DoesNotExistError:
			pass

	def update_category_app_count(self):
		"""Update the app_count for the category this app belongs to"""
		if self.category:
			try:
				category = frappe.get_doc("App Category", self.category)
				category.update_app_count()
			except frappe.DoesNotExistError:
				pass

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

	def after_delete(self):
		"""Keep the category's app_count in step once the row is gone.

		This has to run after deletion rather than in on_trash: App Category.
		update_app_count() recounts with frappe.db.count instead of
		decrementing, so calling it while this App still exists would count
		the app being deleted and leave the total one too high.
		"""
		if self.category:
			self.update_category_app_count()

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
		bench_settings = frappe.get_doc("Bench Node Manager", "Local Bench")
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
			"update_app": [
				f"git checkout {self.current_git_branch} || git checkout -b {self.current_git_branch}",
				"git pull",
				"bench --site all clear-cache",
				"bench --site all clear-website-cache",
				"bench restart"
			],
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

	# ===== VERSION MANAGEMENT METHODS =====
	
	def parse_github_datetime(self, datetime_str):
		"""Convert GitHub ISO 8601 datetime to MySQL compatible format"""
		if not datetime_str:
			return None
		try:
			# GitHub returns format: 2026-05-06T06:34:34Z
			# Convert to MySQL format: 2026-05-06 06:34:34
			from datetime import datetime
			dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
			return dt.strftime('%Y-%m-%d %H:%M:%S')
		except:
			return None
	
	def detect_current_version(self):
		"""Detect the currently installed version from git"""
		if not self.is_git_repo:
			return None
		
		app_path = os.path.join("..", "apps", self.name)
		
		try:
			# Try to get current git tag
			tag = safe_decode(
				check_output(
					"git describe --tags --exact-match".split(),
					cwd=app_path,
					stderr=PIPE
				)
			).strip()
			if tag:
				return extract_version_from_tag(tag)
		except:
			pass
		
		# If no exact tag, try to get version from hooks.py or __init__.py
		try:
			# Read version from app's __init__.py
			init_file = os.path.join(app_path, self.name, "__init__.py")
			if os.path.exists(init_file):
				with open(init_file, 'r') as f:
					content = f.read()
					match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
					if match:
						return match.group(1)
		except:
			pass
		
		# Fallback to the version field
		return self.version
	
	@frappe.whitelist()
	def sync_versions_from_github(self):
		"""Fetch releases and tags from GitHub and update versions table"""
		if not self.repository_url:
			frappe.throw("Repository URL is required for GitHub sync")
		
		try:
			frappe.publish_realtime(
				'version_sync_progress',
				{'progress': 10, 'message': 'Connecting to GitHub...'},
				user=frappe.session.user
			)
			
			# Get GitHub token from Bench Settings (centralized)
			bench_settings = frappe.get_doc('Bench Node Manager', 'Local Bench')
			github_token = bench_settings.get('github_password') or self.github_token or None
			
			github = GitHubAPI(self.repository_url, github_token)
			
			# Clear existing versions
			self.versions = []
			
			frappe.publish_realtime(
				'version_sync_progress',
				{'progress': 20, 'message': 'Fetching releases from GitHub...'},
				user=frappe.session.user
			)
			
			# Get releases from GitHub
			releases = github.get_releases()
			release_dict = {r['tag_name']: r for r in releases}
			
			frappe.publish_realtime(
				'version_sync_progress',
				{'progress': 40, 'message': f'Found {len(releases)} releases. Fetching tags...'},
				user=frappe.session.user
			)
			
			# Get all tags
			tags = github.get_tags()
			
			frappe.publish_realtime(
				'version_sync_progress',
				{'progress': 60, 'message': f'Processing {len(tags)} versions...'},
				user=frappe.session.user
			)
			
			# Process each tag
			total_tags = len(tags)
			for idx, tag in enumerate(tags):
				tag_name = tag['name']
				version_number = extract_version_from_tag(tag_name)
				
				# Get release info if available
				release_info = release_dict.get(tag_name)
				
				# Get commit info from tag object (no extra API call needed)
				commit_sha = tag['commit']['sha']
				
				version_row = {
					'version': version_number,
					'git_tag': tag_name,
					'git_hash': commit_sha,
					'is_prerelease': is_prerelease(tag_name),
					'status': 'Available'
				}
				
				if release_info:
					# Use release info (already fetched)
					version_row['release_notes'] = release_info.get('body', '')
					version_row['author'] = release_info.get('author', {}).get('login', '')
					published_at = release_info.get('published_at')
					if published_at:
						version_row['release_date'] = self.parse_github_datetime(published_at)
				# Don't fetch individual commit info - too many API calls!
				
				self.append('versions', version_row)
				
				# Update progress every 10 tags
				if (idx + 1) % 10 == 0 or idx == total_tags - 1:
					progress = 60 + int((idx + 1) / total_tags * 20)
					frappe.publish_realtime(
						'version_sync_progress',
						{'progress': progress, 'message': f'Processed {idx + 1}/{total_tags} versions...'},
						user=frappe.session.user
					)
			
			frappe.publish_realtime(
				'version_sync_progress',
				{'progress': 85, 'message': 'Analyzing versions...'},
				user=frappe.session.user
			)
			
			# Mark current and latest versions
			self.update_version_flags()
			
			# Update sync status
			self.last_synced = now_datetime()
			self.sync_status = 'Success'
			self.sync_error = None
			
			frappe.publish_realtime(
				'version_sync_progress',
				{'progress': 95, 'message': 'Saving data...'},
				user=frappe.session.user
			)
			
			self.save()
			
			frappe.publish_realtime(
				'version_sync_progress',
				{'progress': 100, 'message': f'✓ Successfully synced {len(self.versions)} versions!'},
				user=frappe.session.user
			)
			
			frappe.msgprint({
				'title': 'Sync Complete',
				'message': f'Successfully synced {len(self.versions)} versions from GitHub',
				'indicator': 'green'
			})
			
		except Exception as e:
			self.sync_status = 'Failed'
			self.sync_error = str(e)
			self.save()
			frappe.throw(f"Failed to sync versions: {str(e)}")
	
	@frappe.whitelist()
	def sync_branches_from_github(self):
		"""Fetch branches from GitHub and update branches table"""
		if not self.repository_url:
			frappe.throw("Repository URL is required for GitHub sync")
		
		try:
			frappe.publish_realtime(
				'branch_sync_progress',
				{'progress': 20, 'message': 'Connecting to GitHub...'},
				user=frappe.session.user
			)
			
			# Get GitHub token from Bench Settings (centralized)
			bench_settings = frappe.get_doc('Bench Node Manager', 'Local Bench')
			github_token = bench_settings.get('github_password') or self.github_token or None
			
			github = GitHubAPI(self.repository_url, github_token)
			
			# Clear existing branches
			self.branches = []
			
			frappe.publish_realtime(
				'branch_sync_progress',
				{'progress': 40, 'message': 'Fetching branches...'},
				user=frappe.session.user
			)
			
			# Get branches from GitHub
			branches = github.get_branches()
			
			frappe.publish_realtime(
				'branch_sync_progress',
				{'progress': 60, 'message': f'Processing {len(branches)} branches...'},
				user=frappe.session.user
			)
			
			total_branches = len(branches)
			for idx, branch in enumerate(branches):
				branch_name = branch['name']
				commit = branch['commit']
				
				branch_row = {
					'branch_name': branch_name,
					'last_commit_hash': commit['sha'],
					'is_active': branch_name == self.current_git_branch
				}
				
				# Only fetch detailed commit info for important branches (first 10) to save API calls
				if idx < 10:
					commit_info = github.get_commit_info(commit['sha'])
					if commit_info:
						branch_row['last_commit_message'] = commit_info.get('commit', {}).get('message', '')
						commit_date = commit_info.get('commit', {}).get('author', {}).get('date')
						if commit_date:
							branch_row['last_commit_date'] = self.parse_github_datetime(commit_date)
				
				self.append('branches', branch_row)
				
				# Update progress
				progress = 60 + int((idx + 1) / total_branches * 30)
				frappe.publish_realtime(
					'branch_sync_progress',
					{'progress': progress, 'message': f'Processed {idx + 1}/{total_branches} branches...'},
					user=frappe.session.user
				)
			
			frappe.publish_realtime(
				'branch_sync_progress',
				{'progress': 95, 'message': 'Saving data...'},
				user=frappe.session.user
			)
			
			self.save()
			
			frappe.publish_realtime(
				'branch_sync_progress',
				{'progress': 100, 'message': f'✓ Successfully synced {len(self.branches)} branches!'},
				user=frappe.session.user
			)
			
			frappe.msgprint({
				'title': 'Sync Complete',
				'message': f'Successfully synced {len(self.branches)} branches from GitHub',
				'indicator': 'green'
			})
			
		except Exception as e:
			frappe.throw(f"Failed to sync branches: {str(e)}")
	
	def update_version_flags(self):
		"""Update is_current and is_latest flags for versions"""
		if not self.versions:
			return
		
		# Detect current version
		current_ver = self.detect_current_version()
		self.current_version = current_ver
		
		# Get all version numbers (excluding pre-releases for latest)
		stable_versions = [v.version for v in self.versions if not v.is_prerelease]
		all_versions = [v.version for v in self.versions]
		
		# Find latest stable version
		latest_ver = get_latest_version(stable_versions) if stable_versions else get_latest_version(all_versions)
		self.latest_version = latest_ver
		
		# Set update_available flag
		if current_ver and latest_ver:
			self.update_available = compare_versions(latest_ver, current_ver) > 0
		
		# Mark versions
		for version_row in self.versions:
			version_row.is_current = (version_row.version == current_ver)
			version_row.is_latest = (version_row.version == latest_ver)
			if version_row.is_current:
				version_row.status = 'Installed'
	
	@frappe.whitelist()
	def update_to_version(self, key, target_version, target_tag):
		"""Update app to a specific version/tag"""
		commands = [
			"git fetch --all --tags",
			f"git checkout tags/{target_tag}",
			"bench --site all clear-cache",
			"bench --site all clear-website-cache",
			"bench restart"
		]
		frappe.enqueue(
			"bench_manager.bench_manager.utils.run_command",
			commands=commands,
			cwd=os.path.join("..", "apps", self.name),
			doctype=self.doctype,
			key=key,
			docname=self.name,
		)
	
	@frappe.whitelist()
	def switch_branch_and_update(self, key, branch_name, target_version=None):
		"""Switch to a different branch and optionally a specific version"""
		commands = [
			f"git fetch origin {branch_name}",
			f"git checkout {branch_name}",
			f"git pull origin {branch_name}"
		]
		
		if target_version:
			commands.append(f"git checkout tags/{target_version}")
		
		commands.extend([
			"bench --site all clear-cache",
			"bench --site all clear-website-cache",
			"bench restart"
		])
		
		frappe.enqueue(
			"bench_manager.bench_manager.utils.run_command",
			commands=commands,
			cwd=os.path.join("..", "apps", self.name),
			doctype=self.doctype,
			key=key,
			docname=self.name,
		)
	
	@frappe.whitelist()
	def rollback_to_version(self, key, version_hash):
		"""Rollback to a previous version using commit hash"""
		commands = [
			f"git checkout {version_hash}",
			"bench --site all clear-cache",
			"bench --site all clear-website-cache",
			"bench restart"
		]
		frappe.enqueue(
			"bench_manager.bench_manager.utils.run_command",
			commands=commands,
			cwd=os.path.join("..", "apps", self.name),
			doctype=self.doctype,
			key=key,
			docname=self.name,
		)
	
	@frappe.whitelist()
	def install_to_site(self, key, site_name):
		commands = [
			f"bench --site {site_name} install-app {self.name}",
			f"bench --site {site_name} migrate",
			"bench restart"
		]
		frappe.enqueue(
			"bench_manager.bench_manager.utils.run_command",
			commands=commands,
			doctype=self.doctype,
			key=key,
			docname=self.name,
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
