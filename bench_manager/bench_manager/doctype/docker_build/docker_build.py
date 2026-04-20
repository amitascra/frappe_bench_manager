# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from datetime import datetime


class DockerBuild(Document):
	def before_save(self):
		if not self.started_at and self.status == "Building":
			self.started_at = datetime.now()
		
		if self.status == "Success" or self.status == "Failure":
			if not self.completed_at:
				self.completed_at = datetime.now()
			
			if self.started_at:
				self.duration = (self.completed_at - self.started_at).total_seconds()

	@frappe.whitelist()
	def start_build(self):
		"""Start Docker image build via Agent"""
		try:
			bench = frappe.get_doc("Cloud Bench", self.cloud_bench)
			app_server = frappe.get_doc("Application Server", bench.application_server)
			
			# Prepare build data
			apps_data = []
			for app in bench.apps:
				apps_data.append({
					"name": app.app,
					"repo": app.repo,
					"branch": app.branch,
					"hash": app.hash
				})
			
			data = {
				"frappe_version": bench.frappe_version,
				"apps": apps_data
			}
			
			# Create Agent Job
			from bench_manager.doctype.agent_job.agent_job import AgentJob
			agent_job = AgentJob.create_job(
				job_type="Build Docker Image",
				endpoint="server/build-image",
				server=app_server.name,
				server_type="Application Server",
				data=data,
				bench=bench.name
			)
			
			self.db_set({
				"agent_job": agent_job.name,
				"status": "Building",
				"started_at": datetime.now()
			})
			
			return {"status": "Building", "agent_job": agent_job.name}
			
		except Exception as e:
			self.db_set({
				"status": "Failure",
				"error_message": str(e)
			})
			frappe.throw(f"Failed to start Docker build: {str(e)}")
