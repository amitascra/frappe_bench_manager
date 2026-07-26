# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
import re
import random
import string


class SiteDomain(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		domain_name: DF.Data
		domain_type: DF.Select
		parent_domain: DF.Link | None
		status: DF.Select
		verified: DF.Check
		verification_method: DF.Select
		verification_token: DF.Data
		last_verified_on: DF.Datetime
		dns_provider: DF.Select
		cloudflare_api_token: DF.Data
		cloudflare_zone_id: DF.Data
		ssl_status: DF.Select
		ssl_expiry: DF.Date
		max_sites: DF.Int
		current_sites: DF.Int
		description: DF.Text
	# end: auto-generated types

	def validate(self):
		self.validate_domain_format()
		self.update_current_sites_count()
		self.generate_verification_token()
		self.validate_max_sites()
		self.validate_status()

	def validate_domain_format(self):
		"""Validate domain name format according to RFC standards"""
		domain = self.domain_name.lower().strip()
		
		# Basic format validation
		if not re.match(r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*\.[a-z]{2,}$', domain):
			frappe.throw(
				f"Invalid domain format: {self.domain_name}. "
				"Domain must follow RFC standards (e.g., example.com, sub.example.com)"
			)
		
		# Length validation
		if len(domain) > 253:
			frappe.throw("Domain name cannot exceed 253 characters")
		
		# Each label max 63 characters
		labels = domain.split('.')
		for label in labels:
			if len(label) > 63:
				frappe.throw(f"Domain label '{label}' exceeds 63 characters")
		
		# Update to lowercase
		self.domain_name = domain

	def generate_verification_token(self):
		"""Generate verification token if not verified"""
		if not self.verified and not self.verification_token:
			self.verification_token = ''.join(
				random.choices(string.ascii_letters + string.digits, k=32)
			)

	def update_current_sites_count(self):
		"""Update current sites count based on linked sites"""
		if self.name:
			count = frappe.db.count("Site", {"site_domain": self.name})
			self.current_sites = count

	def validate_max_sites(self):
		"""Validate that current sites don't exceed max"""
		if self.current_sites > self.max_sites:
			frappe.throw(
				f"Current sites ({self.current_sites}) exceed maximum allowed ({self.max_sites})"
			)

	def validate_status(self):
		"""Validate status field based on verification state"""
		if self.verified:
			if self.status != "Active":
				self.status = "Active"
		else:
			if self.status != "Pending Verification":
				self.status = "Pending Verification"

	def before_save(self):
		"""Before save hook"""
		self.update_current_sites_count()

	def is_verification_valid(self):
		"""Check if domain verification is still valid"""
		if not self.verified or not self.last_verified_on:
			return False

		# Verification is valid if checked within the last 30 days
		from datetime import timedelta
		# Ensure last_verified_on is a datetime object
		if isinstance(self.last_verified_on, str):
			last_verified = frappe.utils.get_datetime(self.last_verified_on)
		else:
			last_verified = self.last_verified_on

		verification_age = frappe.utils.now() - last_verified
		return verification_age <= timedelta(days=30)

	def check_verification_still_valid(self):
		"""Re-verify domain to ensure ownership is still valid"""
		if not self.verified:
			return True

		if not self.is_verification_valid():
			# Verification is stale, re-verify
			try:
				self.verify_domain_ownership(verification_method=self.verification_method, force=True)
				return True
			except Exception:
				# Re-verification failed, mark as unverified
				self.verified = 0
				self.status = "Pending Verification"
				self.save()
				return False

		# Verification is recent, spot check
		try:
			if self.verification_method == "DNS":
				self._verify_via_dns()
			elif self.verification_method == "HTTP":
				self._verify_via_http()
			elif self.verification_method == "TXT Record":
				self._verify_via_txt()
			return True
		except Exception:
			# Spot check failed, mark as unverified
			self.verified = 0
			self.status = "Pending Verification"
			self.save()
			return False

	@frappe.whitelist()
	def verify_domain_ownership(self, verification_method=None, force=False):
		"""Verify domain ownership via DNS, HTTP, or TXT Record"""
		if "System Manager" not in frappe.get_roles(frappe.session.user):
			frappe.throw(_("Not permitted"), frappe.PermissionError)

		if self.verified and not force:
			frappe.throw("Domain is already verified")

		verification_method = verification_method or frappe.form_dict.get("verification_method") or self.verification_method or "http"

		try:
			if verification_method == "DNS":
				self._verify_via_dns()
			elif verification_method == "HTTP":
				self._verify_via_http()
			elif verification_method == "TXT Record":
				self._verify_via_txt()
			else:
				frappe.throw("Invalid verification method")
		except Exception as e:
			frappe.log_error(f"Verification failed: {str(e)}", "Domain Verification Error")
			raise

		self.verified = 1
		self.status = "Active"
		self.last_verified_on = frappe.utils.now()
		self.save()

		return {"success": True, "message": "Domain verified successfully"}

	def _verify_via_dns(self):
		"""Verify domain via DNS TXT record"""
		try:
			import dns.resolver
		except ImportError:
			frappe.throw("dnspython library is not installed. Please install it with: pip install dnspython")

		try:
			# Check for TXT record with verification token at the domain level
			# Using dnspython 1.x API (query)
			answers = dns.resolver.query(self.domain_name, "TXT")

			for rdata in answers:
				if self.verification_token in str(rdata):
					return

			frappe.throw("DNS TXT record not found or token mismatch. Please add a TXT record with your verification token.")
		except dns.resolver.NXDOMAIN:
			frappe.throw(f"Domain {self.domain_name} does not exist")
		except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
			frappe.throw("No TXT records found for verification. Please add a TXT record with your verification token.")
		except Exception as e:
			frappe.throw(f"DNS verification failed: {str(e)}")

	def _verify_via_http(self):
		"""Verify domain via HTTP file"""
		import requests
		
		try:
			url = f"http://{self.domain_name}/.well-known/frappe-verification"
			response = requests.get(url, timeout=10)
			
			if response.status_code != 200:
				frappe.throw(f"Verification file not accessible at {url}")
			
			if response.text.strip() != self.verification_token:
				frappe.throw("Verification token mismatch")
		except requests.exceptions.RequestException as e:
			frappe.throw(f"Failed to verify via HTTP: {str(e)}")

	def _verify_via_txt(self):
		"""Verify domain via TXT record"""
		try:
			import dns.resolver
		except ImportError:
			frappe.throw("dnspython library is not installed. Please install it with: pip install dnspython")

		try:
			# Support both dnspython 1.x (query) and 2.x (resolve)
			if hasattr(dns.resolver, 'resolve'):
				answers = dns.resolver.resolve(f"_frappe-verification.{self.domain_name}", "TXT")
			else:
				answers = dns.resolver.query(f"_frappe-verification.{self.domain_name}", "TXT")

			for rdata in answers:
				if self.verification_token in str(rdata):
					return

			frappe.throw("Verification TXT record not found or token mismatch")
		except dns.resolver.NXDOMAIN:
			frappe.throw(f"Domain {self.domain_name} does not exist")
		except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
			frappe.throw("No TXT records found for verification")
		except Exception as e:
			frappe.throw(f"DNS verification failed: {str(e)}")

	@frappe.whitelist()
	def install_ssl_certificate(self):
		"""Install SSL certificate via Let's Encrypt"""
		if "System Manager" not in frappe.get_roles(frappe.session.user):
			frappe.throw(_("Not permitted"), frappe.PermissionError)

		if not self.verified:
			frappe.throw("Domain must be verified before installing SSL")

		# Re-verify domain before SSL installation
		if not self.check_verification_still_valid():
			frappe.throw("Domain verification is no longer valid. Please re-verify the domain before installing SSL.")

		self.ssl_status = "Pending"
		self.save()

		# Enqueue SSL installation
		frappe.enqueue(
			"bench_manager.bench_manager.doctype.site_domain.site_domain._install_ssl_job",
			domain_name=self.domain_name,
			doc_name=self.name
		)

		return {"success": True, "message": "SSL installation started"}

	@frappe.whitelist()
	def get_available_subdomains(self):
		"""Get list of available subdomain names"""
		if "System Manager" not in frappe.get_roles(frappe.session.user):
			frappe.throw(_("Not permitted"), frappe.PermissionError)

		if self.domain_type != "Root Domain":
			frappe.throw("Only root domains can have subdomains")

		# Get existing subdomains
		existing_subdomains = frappe.get_all(
			"Site Domain",
			filters={
				"parent_domain": self.name,
				"domain_type": "Subdomain"
			},
			pluck="domain_name"
		)

		# Get linked sites
		linked_sites = frappe.get_all(
			"Site",
			filters={"site_domain": self.name},
			pluck="name"
		)

		# Combine and return
		return {
			"existing_subdomains": existing_subdomains,
			"linked_sites": linked_sites
		}

	@frappe.whitelist()
	def test_cloudflare_connection(self):
		"""Test Cloudflare API connection and get account info"""
		if self.dns_provider != "Cloudflare":
			frappe.throw("DNS provider must be Cloudflare")

		if not self.cloudflare_api_token:
			frappe.throw("Cloudflare API Token is required")

		try:
			from cloudflare import Cloudflare

			# Clean token - remove any whitespace
			token = self.cloudflare_api_token.strip()

			client = Cloudflare(api_token=token)

			# Test connection by getting account info
			accounts = client.accounts.list()
			
			# Iterate over the pagination object to get the first account
			account = None
			for acc in accounts:
				account = acc
				break
			
			if not account:
				frappe.throw("No Cloudflare accounts found for this API token")

			frappe.msgprint(f"Hi {account.name}, we are connected! Feel free to manage your Cloudflare DNS records from here.")

			return {
				"success": True,
				"account_name": account.name,
				"account_id": account.id
			}
		except Exception as e:
			error_msg = str(e)
			frappe.throw(f"Failed to connect to Cloudflare: {error_msg}")

	@frappe.whitelist()
	def get_cloudflare_zone_id(self):
		"""Get Cloudflare Zone ID for the domain"""
		if self.dns_provider != "Cloudflare":
			frappe.throw("DNS provider must be Cloudflare")

		if not self.cloudflare_api_token:
			frappe.throw("Cloudflare API Token is required")

		try:
			from cloudflare import Cloudflare

			# Clean token - remove any whitespace
			token = self.cloudflare_api_token.strip()

			client = Cloudflare(api_token=token)

			# Search for zone by domain name
			zones = client.zones.list(name=self.domain_name)
			
			# Iterate over the pagination object to get the first zone
			zone = None
			for z in zones:
				zone = z
				break
			
			if not zone:
				frappe.throw(f"Zone not found for domain: {self.domain_name}")

			self.cloudflare_zone_id = zone.id
			self.save()

			return {
				"success": True,
				"zone_id": zone.id,
				"zone_name": zone.name,
				"message": f"Found Cloudflare zone: {zone.name}"
			}
		except Exception as e:
			error_msg = str(e)
			frappe.logger().error(f"Cloudflare API error: {error_msg}")
			frappe.throw(f"Failed to get Cloudflare Zone ID: {error_msg}")

	@frappe.whitelist()
	def sync_cloudflare_dns_records(self):
		"""Sync DNS records from Cloudflare"""
		if self.dns_provider != "Cloudflare":
			frappe.throw("DNS provider must be Cloudflare")

		if not self.cloudflare_api_token:
			frappe.throw("Cloudflare API Token is required")

		if not self.cloudflare_zone_id:
			# Try to get zone ID first
			self.get_cloudflare_zone_id()

		try:
			from cloudflare import Cloudflare

			# Clean token - remove any whitespace
			token = self.cloudflare_api_token.strip()

			client = Cloudflare(api_token=token)

			# Fetch all DNS records for the zone
			dns_records = client.dns.records.list(zone_id=self.cloudflare_zone_id)

			# Clear existing DNS records using the child table API
			self.set("dns_records", [])

			records_list = []
			for record in dns_records:
				# Create DNS Record child doc
				dns_record = {
					"doctype": "DNS Record",
					"record_type": record.type,
					"dns_name": record.name.replace(f".{self.domain_name}", "") or "@",
					"value": record.content,
					"ttl": record.ttl,
					"proxied": 1 if record.proxied else 0,
					"status": "Active"
				}

				# Add priority for MX and SRV records
				if hasattr(record, 'priority') and record.priority:
					dns_record["priority"] = record.priority

				self.append("dns_records", dns_record)
				records_list.append(dns_record)

			frappe.msgprint(f"Appended {len(records_list)} DNS records")

			self.save()

			return {
				"success": True,
				"records_count": len(records_list),
				"message": f"Successfully synced {len(records_list)} DNS records from Cloudflare"
			}
		except Exception as e:
			error_msg = str(e)
			frappe.throw(f"Failed to sync DNS records from Cloudflare: {error_msg}")

	@frappe.whitelist()
	def delete_dns_record_from_cloudflare(self, dns_record_name, record_type):
		"""Delete a DNS record from Cloudflare"""
		frappe.logger().info(f"delete_dns_record_from_cloudflare called for: {dns_record_name} (type: {record_type})")
		
		if self.dns_provider != "Cloudflare":
			frappe.throw("DNS provider must be Cloudflare")

		if not self.cloudflare_api_token:
			frappe.throw("Cloudflare API Token is required")

		if not self.cloudflare_zone_id:
			# Try to get zone ID first
			self.get_cloudflare_zone_id()

		try:
			from cloudflare import Cloudflare

			# Clean token - remove any whitespace
			token = self.cloudflare_api_token.strip()

			client = Cloudflare(api_token=token)

			# Match the naming convention used in sync_cloudflare_dns_records
			# If dns_name is "@", use domain_name, otherwise append domain_name
			if dns_record_name == "@":
				record_name = self.domain_name
			else:
				record_name = f"{dns_record_name}.{self.domain_name}" if not dns_record_name.endswith(self.domain_name) else dns_record_name
			
			frappe.logger().info(f"Record name for Cloudflare: {record_name}")

			# Fetch existing Cloudflare DNS records
			cloudflare_records = client.dns.records.list(zone_id=self.cloudflare_zone_id)
			frappe.logger().info(f"Fetched {len(list(cloudflare_records))} records from Cloudflare")
			
			# Log all Cloudflare records for debugging
			for record in cloudflare_records:
				frappe.logger().info(f"Cloudflare record: name={record.name}, type={record.type}, id={record.id}")
			
			# Find the matching record
			matching_record = None
			for record in cloudflare_records:
				if record.name == record_name and record.type == record_type:
					matching_record = record
					frappe.logger().info(f"Found matching Cloudflare record: {record.id}")
					break

			if not matching_record:
				frappe.logger().warning(f"No matching record found in Cloudflare for {record_name} (type: {record_type})")
				# Don't throw error, just return success so local delete can proceed
				return {
					"success": True,
					"message": f"Record not found in Cloudflare, only deleted locally"
				}

			# Delete the record
			frappe.logger().info(f"Deleting Cloudflare record: {matching_record.id}")
			client.dns.records.delete(dns_record_id=matching_record.id, zone_id=self.cloudflare_zone_id)
			frappe.logger().info("Successfully deleted from Cloudflare")

			return {
				"success": True,
				"message": f"Deleted {record_type} record '{dns_record_name}' from Cloudflare"
			}
		except Exception as e:
			error_msg = str(e)
			frappe.logger().error(f"Failed to delete DNS record from Cloudflare: {error_msg}")
			frappe.throw(f"Failed to delete DNS record from Cloudflare: {error_msg}")

	@frappe.whitelist()
	def sync_single_dns_record_to_cloudflare(self, dns_record_name):
		"""Sync a single DNS record to Cloudflare"""
		if self.dns_provider != "Cloudflare":
			frappe.throw("DNS provider must be Cloudflare")

		if not self.cloudflare_api_token:
			frappe.throw("Cloudflare API Token is required")

		if not self.cloudflare_zone_id:
			# Try to get zone ID first
			self.get_cloudflare_zone_id()

		try:
			from cloudflare import Cloudflare

			# Clean token - remove any whitespace
			token = self.cloudflare_api_token.strip()

			client = Cloudflare(api_token=token)

			# Find the DNS record in the child table
			dns_record = None
			for record in self.dns_records:
				if record.dns_name == dns_record_name:
					dns_record = record
					break

			if not dns_record:
				frappe.throw(f"DNS record '{dns_record_name}' not found")

			record_name = dns_record.dns_name if dns_record.dns_name != "@" else self.domain_name
			record_content = dns_record.value
			record_type = dns_record.record_type
			record_ttl = dns_record.ttl
			record_proxied = bool(dns_record.proxied)
			record_priority = dns_record.priority if hasattr(dns_record, 'priority') else None

			# Fetch existing Cloudflare DNS records
			cloudflare_records = client.dns.records.list(zone_id=self.cloudflare_zone_id)
			
			# Check if record already exists
			matching_record = None
			conflicting_record = None
			
			for record in cloudflare_records:
				if record.name == record_name and record.type == record_type:
					matching_record = record
					break
				elif record.name == record_name and record.type in ['A', 'AAAA', 'CNAME'] and record_type in ['A', 'AAAA', 'CNAME'] and record.type != record_type:
					conflicting_record = record
					break

			if conflicting_record:
				# Delete conflicting record first
				client.dns.records.delete(dns_record_id=conflicting_record.id, zone_id=self.cloudflare_zone_id)

			if matching_record:
				# Update existing record
				update_data = {
					"name": record_name,
					"type": record_type,
					"content": record_content,
					"ttl": record_ttl,
					"proxied": record_proxied
				}
				
				if record_priority and (record_type in ['MX', 'SRV']):
					update_data["priority"] = record_priority

				client.dns.records.update(
					dns_record_id=matching_record.id,
					zone_id=self.cloudflare_zone_id,
					**update_data
				)
				message = f"Updated {record_type} record '{dns_record_name}' in Cloudflare"
			else:
				# Create new record
				create_data = {
					"name": record_name,
					"type": record_type,
					"content": record_content,
					"ttl": record_ttl,
					"proxied": record_proxied
				}
				
				if record_priority and (record_type in ['MX', 'SRV']):
					create_data["priority"] = record_priority

				client.dns.records.create(
					zone_id=self.cloudflare_zone_id,
					**create_data
				)
				message = f"Created {record_type} record '{dns_record_name}' in Cloudflare"

			frappe.msgprint(message)

			return {
				"success": True,
				"message": message
			}
		except Exception as e:
			error_msg = str(e)
			frappe.throw(f"Failed to sync DNS record to Cloudflare: {error_msg}")

	@frappe.whitelist()
	def sync_to_cloudflare(self):
		"""Sync DNS records to Cloudflare"""
		if self.dns_provider != "Cloudflare":
			frappe.throw("DNS provider must be Cloudflare")

		if not self.cloudflare_api_token:
			frappe.throw("Cloudflare API Token is required")

		if not self.cloudflare_zone_id:
			# Try to get zone ID first
			self.get_cloudflare_zone_id()

		try:
			from cloudflare import Cloudflare

			# Clean token - remove any whitespace
			token = self.cloudflare_api_token.strip()

			client = Cloudflare(api_token=token)

			# Fetch existing Cloudflare DNS records
			cloudflare_records = client.dns.records.list(zone_id=self.cloudflare_zone_id)
			
			# Create a dictionary of existing records for easy lookup (key: name+type)
			cf_records_map = {}
			for record in cloudflare_records:
				key = f"{record.name}:{record.type}"
				cf_records_map[key] = record

			# Track created, updated, and deleted records
			created = 0
			updated = 0
			deleted = 0

			# Process local DNS records
			for dns_record in self.dns_records:
				record_name = dns_record.dns_name if dns_record.dns_name != "@" else self.domain_name
				record_content = dns_record.value
				record_type = dns_record.record_type
				record_ttl = dns_record.ttl
				record_proxied = bool(dns_record.proxied)
				record_priority = dns_record.priority if hasattr(dns_record, 'priority') else None

				key = f"{record_name}:{record_type}"
				
				# Check for exact match
				if key in cf_records_map:
					# Check if record needs updating
					cf_record = cf_records_map[key]
					needs_update = (
						cf_record.content != record_content or
						cf_record.ttl != record_ttl or
						cf_record.proxied != record_proxied
					)
					
					if record_priority and (record_type in ['MX', 'SRV']):
						if cf_record.priority != record_priority:
							needs_update = True

					if needs_update:
						# Update existing record
						update_data = {
							"name": record_name,
							"type": record_type,
							"content": record_content,
							"ttl": record_ttl,
							"proxied": record_proxied
						}
						
						if record_priority and (record_type in ['MX', 'SRV']):
							update_data["priority"] = record_priority

						client.dns.records.update(
							dns_record_id=cf_record.id,
							zone_id=self.cloudflare_zone_id,
							**update_data
						)
						updated += 1
					
					# Remove from map so we don't delete it later
					del cf_records_map[key]
				else:
					# Check for conflicting record (same name, different type for A/AAAA/CNAME)
					conflicting_key = None
					conflicting_record = None
					
					for cf_key, cf_record in cf_records_map.items():
						cf_name, cf_type = cf_key.split(':')
						if cf_name == record_name and cf_type in ['A', 'AAAA', 'CNAME'] and record_type in ['A', 'AAAA', 'CNAME'] and cf_type != record_type:
							conflicting_key = cf_key
							conflicting_record = cf_record
							break
					
					if conflicting_record:
						# Delete conflicting record first
						client.dns.records.delete(dns_record_id=conflicting_record.id, zone_id=self.cloudflare_zone_id)
						del cf_records_map[conflicting_key]
					
					# Create new record
					create_data = {
						"name": record_name,
						"type": record_type,
						"content": record_content,
						"ttl": record_ttl,
						"proxied": record_proxied
					}
					
					if record_priority and (record_type in ['MX', 'SRV']):
						create_data["priority"] = record_priority

					client.dns.records.create(
						zone_id=self.cloudflare_zone_id,
						**create_data
					)
					created += 1

			# Delete records that exist in Cloudflare but not locally
			for key in cf_records_map:
				cf_record = cf_records_map[key]
				client.dns.records.delete(dns_record_id=cf_record.id, zone_id=self.cloudflare_zone_id)
				deleted += 1

			message = f"Synced to Cloudflare: {created} created, {updated} updated, {deleted} deleted"
			frappe.msgprint(message)

			return {
				"success": True,
				"created": created,
				"updated": updated,
				"deleted": deleted,
				"message": message
			}
		except Exception as e:
			error_msg = str(e)
			frappe.throw(f"Failed to sync to Cloudflare: {error_msg}")

def check_all_domain_verifications():
	"""Scheduled job to check all domain verifications every 9 minutes"""
	domains = frappe.get_all("Site Domain", filters={"verified": 1}, fields=["name"])

	for domain_name in domains:
		try:
			domain = frappe.get_doc("Site Domain", domain_name.name)
			domain.check_verification_still_valid()
		except Exception as e:
			frappe.log_error(f"Failed to check verification for domain {domain_name.name}: {str(e)}", "Domain Verification Check Error")

def _install_ssl_job(domain_name, doc_name):
	"""Background job for SSL installation"""
	import subprocess

	try:
		# Install SSL using certbot
		command = f"sudo certbot certonly --webroot -w /var/www/html -d {domain_name} --non-interactive --agree-tos"
		result = subprocess.run(command, shell=True, capture_output=True, text=True)

		if result.returncode != 0:
			frappe.log_error(result.stderr, "SSL Installation Error")
			return

		# Update SSL status
		domain = frappe.get_doc("Site Domain", doc_name)
		domain.ssl_status = "Installed"

		# Set expiry (90 days from now)
		from datetime import datetime, timedelta
		domain.ssl_expiry = (datetime.now() + timedelta(days=90)).date()
		domain.save()

	except Exception as e:
		frappe.log_error(str(e), "SSL Installation Error")


@frappe.whitelist()
def get_active_domains():
	"""Get list of active and verified domains for site creation"""
	domains = frappe.get_all(
		"Site Domain",
		filters={
			"status": "Active",
			"verified": 1
		},
		fields=["name", "domain_name", "domain_type", "max_sites", "current_sites"]
	)
	
	# Filter domains that have available slots
	available_domains = []
	for domain in domains:
		if domain.current_sites < domain.max_sites:
			available_domains.append(domain)
	
	return available_domains


@frappe.whitelist()
def validate_site_domain(domain_name, subdomain):
	"""Validate that domain and subdomain combination is available"""
	if "System Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	
	# Get domain
	try:
		domain = frappe.get_doc("Site Domain", domain_name)
	except frappe.DoesNotExist:
		return {
			"valid": False,
			"message": "Domain not found"
		}
	
	# Check domain status
	if domain.status != "Active":
		return {
			"valid": False,
			"message": f"Domain is {domain.status}"
		}
	
	if not domain.verified:
		return {
			"valid": False,
			"message": "Domain is not verified"
		}
	
	# Check max sites
	if domain.current_sites >= domain.max_sites:
		return {
			"valid": False,
			"message": f"Domain has reached maximum sites limit ({domain.max_sites})"
		}
	
	# Check subdomain format
	if subdomain:
		if not re.match(r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$', subdomain):
			return {
				"valid": False,
				"message": "Invalid subdomain format. Use lowercase letters, numbers, and hyphens"
			}
		
		if len(subdomain) > 63:
			return {
				"valid": False,
				"message": "Subdomain cannot exceed 63 characters"
			}
	
	# Check if subdomain already exists
	if subdomain:
		existing = frappe.db.exists("Site", {
			"site_domain": domain_name,
			"subdomain": subdomain
		})
		
		if existing:
			return {
				"valid": False,
				"message": f"Subdomain '{subdomain}' is already in use"
			}
		
		# Check if subdomain exists as a separate domain
		full_domain = f"{subdomain}.{domain.domain_name}"
		existing_domain = frappe.db.exists("Site Domain", {"domain_name": full_domain})
		if existing_domain:
			return {
				"valid": False,
				"message": f"Subdomain '{subdomain}' is already registered as a domain"
			}
	
	return {
		"valid": True,
		"message": "Domain and subdomain combination is available",
		"full_domain": f"{subdomain}.{domain.domain_name}" if subdomain else domain.domain_name
	}
