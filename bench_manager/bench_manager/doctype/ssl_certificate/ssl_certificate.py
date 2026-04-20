# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from datetime import datetime, timedelta


class SSLCertificate(Document):
	def before_save(self):
		if not self.created_at:
			self.created_at = datetime.now()
		self.updated_at = datetime.now()

	@frappe.whitelist()
	def issue_certificate(self):
		"""Issue SSL certificate via Let's Encrypt or custom provider"""
		try:
			if self.certificate_type == "Let's Encrypt":
				self._issue_lets_encrypt()
			else:
				self._issue_custom_certificate()
			
			self.db_set("status", "Issuing")
			
			return {
				"status": "Issuing",
				"message": "Certificate issuance initiated"
			}
			
		except Exception as e:
			self.db_set("status", "Revoked")
			frappe.throw(f"Failed to issue certificate: {str(e)}")

	def _issue_lets_encrypt(self):
		"""Issue Let's Encrypt certificate via Certbot"""
		# TODO: Call Agent to run Certbot on Proxy Server
		# This will be implemented in Phase 2.2 (Agent Communication Module)
		
		# Set default expiry date (90 days for Let's Encrypt)
		self.expiry_date = datetime.now() + timedelta(days=90)
		self.certificate_provider = "Let's Encrypt"
		self.save()

	def _issue_custom_certificate(self):
		"""Issue custom certificate"""
		# TODO: Upload custom certificate files
		# This will be implemented later
		
		self.certificate_provider = "Custom"
		self.save()

	@frappe.whitelist()
	def renew_certificate(self):
		"""Renew SSL certificate"""
		if self.status == "Expired":
			frappe.throw("Cannot renew expired certificate")
		
		try:
			if self.certificate_type == "Let's Encrypt":
				self._renew_lets_encrypt()
			else:
				frappe.throw("Custom certificates must be renewed manually")
			
			self.db_set("status", "Issuing")
			
			return {
				"status": "Issuing",
				"message": "Certificate renewal initiated"
			}
			
		except Exception as e:
			frappe.throw(f"Failed to renew certificate: {str(e)}")

	def _renew_lets_encrypt(self):
		"""Renew Let's Encrypt certificate via Certbot"""
		# TODO: Call Agent to run Certbot renew on Proxy Server
		
		# Update expiry date
		self.expiry_date = datetime.now() + timedelta(days=90)
		self.save()

	@frappe.whitelist()
	def revoke_certificate(self):
		"""Revoke SSL certificate"""
		try:
			# TODO: Call Agent to revoke certificate on Proxy Server
			
			self.db_set("status", "Revoked")
			
			return {"status": "Revoked", "message": "Certificate revoked"}
			
		except Exception as e:
			frappe.throw(f"Failed to revoke certificate: {str(e)}")

	@staticmethod
	def check_expiry():
		"""Check for certificates nearing expiry and send alerts"""
		from frappe.utils import getdate
		
		# Get certificates expiring in 30 days
		today = getdate()
		alert_date = today + timedelta(days=30)
		
		expiring_certs = frappe.get_all(
			"SSL Certificate",
			filters={
				"status": "Active",
				"expiry_date": ["<=", alert_date],
				"expiry_date": [">=", today]
			},
			fields=["name", "domain_name", "expiry_date", "auto_renew"]
		)
		
		for cert in expiring_certs:
			if cert.auto_renew:
				# Auto renew if enabled
				cert_doc = frappe.get_doc("SSL Certificate", cert.name)
				cert_doc.renew_certificate()
			else:
				# Send alert
				frappe.sendmail(
					recipients=["admin@example.com"],
					subject=f"SSL Certificate Expiring: {cert.domain_name}",
					message=f"SSL Certificate for {cert.domain_name} will expire on {cert.expiry_date}"
				)
