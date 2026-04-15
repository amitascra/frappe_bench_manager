# -*- coding: utf-8 -*-
# Real-time sync functionality for Bench Manager
# Monitors filesystem changes and triggers automatic sync

import os
import frappe
from frappe.utils import now_datetime, get_datetime
from datetime import timedelta


def check_and_sync_if_needed():
	"""
	Check if sync is needed based on file modifications
	Called by scheduler every 15 minutes
	"""
	try:
		# Get last sync timestamp
		last_sync = frappe.db.get_single_value("Bench Settings", "last_sync_timestamp")
		
		if not last_sync:
			# First time sync
			trigger_sync()
			return
		
		last_sync_time = get_datetime(last_sync) if isinstance(last_sync, str) else last_sync
		
		# Check if apps.txt has been modified since last sync
		apps_file = "apps.txt"
		if os.path.exists(apps_file):
			apps_mtime = os.path.getmtime(apps_file)
			if apps_mtime > last_sync:
				frappe.logger().info("apps.txt modified, triggering sync")
				trigger_sync()
				return
		
		# Check if new sites have been created
		sites_changed = check_sites_changed(last_sync)
		if sites_changed:
			frappe.logger().info("Sites changed, triggering sync")
			trigger_sync()
			return
		
		# Check if new backups exist
		backups_changed = check_backups_changed(last_sync)
		if backups_changed:
			frappe.logger().info("Backups changed, triggering sync")
			trigger_sync()
			return
			
	except Exception as e:
		frappe.log_error(f"Real-time sync check failed: {str(e)}", "Bench Manager Real-time Sync")


def check_sites_changed(last_sync):
	"""Check if any site_config.json files have been modified"""
	try:
		for root, dirs, files in os.walk(".", topdown=True):
			if "site_config.json" in files:
				site_config_path = os.path.join(root, "site_config.json")
				if os.path.getmtime(site_config_path) > last_sync:
					return True
		return False
	except:
		return False


def check_backups_changed(last_sync):
	"""Check if new backups have been created"""
	try:
		for root, dirs, files in os.walk(".", topdown=True):
			if "backups" in root:
				for file in files:
					if "database.sql" in file:
						backup_file = os.path.join(root, file)
						if os.path.getmtime(backup_file) > last_sync:
							return True
		return False
	except:
		return False


def trigger_sync():
	"""Trigger background sync"""
	from bench_manager.bench_manager.doctype.bench_settings.bench_settings import (
		sync_sites, sync_apps, sync_backups
	)
	
	frappe.enqueue(sync_sites, queue="long")
	frappe.enqueue(sync_apps, queue="long")
	frappe.enqueue(sync_backups, queue="long")
	
	frappe.set_value(
		"Bench Settings", None, "last_sync_timestamp", frappe.utils.time.time()
	)
	frappe.db.commit()


@frappe.whitelist()
def force_sync_now():
	"""Force immediate sync - can be called from UI"""
	trigger_sync()
	return {"message": "Sync triggered successfully"}
