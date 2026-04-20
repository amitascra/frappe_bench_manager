# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from datetime import datetime, timedelta
import json


class AgentJob(Document):
	def before_save(self):
		if not self.started_at and self.status == "Started":
			self.started_at = datetime.now()
		
		if self.status == "Success" or self.status == "Failure":
			if not self.completed_at:
				self.completed_at = datetime.now()
			
			if self.started_at:
				self.duration = (self.completed_at - self.started_at).total_seconds()

	@frappe.whitelist()
	def execute_job(self):
		"""Execute the agent job"""
		try:
			from bench_manager.agent.agent_communication import AgentCommunication
			
			comm = AgentCommunication(self.server, self.server_type)
			
			# Execute the endpoint
			data = json.loads(self.data) if self.data else {}
			result = comm.post(self.endpoint, data)
			
			# Update job status
			self.db_set({
				"status": "Success",
				"output": json.dumps(result, default=str),
				"completed_at": datetime.now()
			})
			
			return {"status": "Success", "result": result}
			
		except Exception as e:
			self.db_set({
				"status": "Failure",
				"error_message": str(e),
				"completed_at": datetime.now()
			})
			
			# Check if we should retry
			if self.retry_count < self.max_retries:
				self.db_set("retry_count", self.retry_count + 1)
				self.db_set("status", "Pending")
				self.schedule_retry()
			else:
				frappe.throw(f"Agent job failed after {self.max_retries} retries: {str(e)}")

	def schedule_retry(self):
		"""Schedule job retry"""
		from frappe.utils import add_to_date
		
		# Schedule retry in 5 minutes
		retry_at = add_to_date(datetime.now(), minutes=5)
		
		# Create a scheduled task for retry
		# This would be implemented with a scheduler
		# For now, we'll just mark as pending
		pass

	@staticmethod
	def create_job(job_type, endpoint, server, server_type, data=None, bench=None, site=None):
		"""Create a new agent job"""
		job = frappe.new_doc("Agent Job")
		job.job_type = job_type
		job.endpoint = endpoint
		job.server = server
		job.server_type = server_type
		job.data = json.dumps(data) if data else None
		job.bench = bench
		job.site = site
		job.status = "Pending"
		job.save()
		
		return job
