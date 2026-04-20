# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from datetime import datetime
import json


class BenchQueue(Document):
	def before_save(self):
		if not self.queued_at:
			self.queued_at = datetime.now()
		
		if not self.started_at and self.status == "Started":
			self.started_at = datetime.now()
		
		if self.status == "Success" or self.status == "Failure":
			if not self.completed_at:
				self.completed_at = datetime.now()
			
			if self.started_at:
				self.duration = (self.completed_at - self.started_at).total_seconds()

	@staticmethod
	def get_concurrency_limit():
		"""Get bench concurrency limit from Cloud Settings"""
		from bench_manager.doctype.cloud_settings.cloud_settings import CloudSettings
		
		settings = CloudSettings.get_settings()
		return settings.bench_concurrency_limit or 3

	@staticmethod
	def get_active_bench_count():
		"""Get count of benches currently being created"""
		return frappe.db.count("Bench Queue", {"status": "Started"})

	@staticmethod
	def can_process_queue():
		"""Check if queue can be processed based on concurrency limit"""
		active_count = BenchQueue.get_active_bench_count()
		concurrency_limit = BenchQueue.get_concurrency_limit()
		return active_count < concurrency_limit

	@staticmethod
	def process_queue():
		"""Process the bench queue"""
		if not BenchQueue.can_process_queue():
			return
		
		# Get next queued item based on priority
		priority_order = {"High": 1, "Medium": 2, "Low": 3}
		queued_items = frappe.get_all(
			"Bench Queue",
			filters={"status": "Queued"},
			fields=["name", "priority"],
			order_by="priority"
		)
		
		if not queued_items:
			return
		
		# Sort by priority
		queued_items.sort(key=lambda x: priority_order.get(x.priority, 999))
		
		# Process the next item
		next_item = queued_items[0]
		queue_doc = frappe.get_doc("Bench Queue", next_item.name)
		
		try:
			# Mark as started
			queue_doc.db_set("status", "Started")
			
			# Get cloud bench
			bench = frappe.get_doc("Cloud Bench", queue_doc.cloud_bench)
			
			# Deploy bench
			result = bench.deploy_bench()
			
			# Mark as success
			queue_doc.db_set({
				"status": "Success",
				"completed_at": datetime.now()
			})
			
		except Exception as e:
			# Mark as failure
			queue_doc.db_set({
				"status": "Failure",
				"error_message": str(e),
				"completed_at": datetime.now()
			})
			
			# Check if we should retry
			if queue_doc.retry_count < queue_doc.max_retries:
				queue_doc.db_set("retry_count", queue_doc.retry_count + 1)
				queue_doc.db_set("status", "Queued")
				queue_doc.save()

	@frappe.whitelist()
	def retry_queue_item(self):
		"""Retry failed queue item"""
		if self.status != "Failure":
			frappe.throw("Only failed queue items can be retried")
		
		self.db_set({
			"status": "Queued",
			"retry_count": self.retry_count + 1,
			"error_message": None
		})
