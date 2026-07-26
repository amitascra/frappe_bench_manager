# Copyright (c) 2026, Amit Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class PaymentTransaction(Document):
	def on_payment_authorized(self, payment_status):
		"""
		Called by payments app when payment succeeds
		Handles both Razorpay and Stripe callbacks
		"""
		if payment_status == "Completed":
			self.status = "Completed"
			self.payment_date = frappe.utils.now()
			
			# Calculate commission based on settings
			settings = frappe.get_single("App Store Settings")
			commission_percent = settings.commission_percentage or 10
			self.commission_amount = (self.amount * commission_percent) / 100
			self.developer_payout_amount = self.amount - self.commission_amount
			
			# Create Member App record with license
			self.create_member_app_license()
			
			# Send confirmation email
			self.send_purchase_confirmation()
			
			self.save()
		elif payment_status == "Failed":
			self.status = "Failed"
			self.save()
	
	def create_member_app_license(self):
		"""
		Create Member App record with license (perpetual or time-limited)
		"""
		app = frappe.get_doc("App", self.app)
		
		# Determine license expiry
		expiry_date = None
		if app.license_type == "Time-limited":
			duration_days = app.license_duration_days or 365
			expiry_date = frappe.utils.add_days(frappe.utils.nowdate(), duration_days)
		
		# For subscriptions, set subscription dates
		subscription_start = None
		subscription_end = None
		if self.pricing_model == "Subscription":
			subscription_start = frappe.utils.nowdate()
			duration_days = app.subscription_duration_days or 30
			if self.subscription_type == "Annual":
				duration_days = duration_days * 12
			subscription_end = frappe.utils.add_days(subscription_start, duration_days)
		
		# Create Member App record
		member_app = frappe.get_doc({
			"doctype": "Member App",
			"parent": self.member,
			"app": self.app,
			"purchase_date": frappe.utils.nowdate(),
			"pricing_model": self.pricing_model,
			"subscription_type": self.subscription_type,
			"license_key": self.generate_license_key(),
			"license_type": app.license_type,
			"expiry_date": expiry_date,
			"subscription_start_date": subscription_start,
			"subscription_end_date": subscription_end,
			"is_active": 1,
			"status": "Active",
			"payment_transaction": self.name
		})
		member_app.insert()
	
	def generate_license_key(self):
		"""
		Generate a unique license key
		"""
		import secrets
		import string
		alphabet = string.ascii_uppercase + string.digits
		return ''.join(secrets.choice(alphabet) for _ in range(16))
	
	def send_purchase_confirmation(self):
		"""
		Send purchase confirmation email to member
		"""
		# TODO: Implement email notification
		pass
	
	def process_refund(self, reason):
		"""
		Handle refund logic
		"""
		# Check refund policy
		settings = frappe.get_single("App Store Settings")
		refund_days = settings.refund_policy_days or 15
		
		# Check if within refund window
		payment_date = frappe.utils.get_datetime(self.payment_date)
		if (frappe.utils.now() - payment_date).days > refund_days:
			frappe.throw("Refund period has expired")
		
		# Process refund via payment gateway
		# TODO: Implement actual refund processing
		self.status = "Refunded"
		self.refund_amount = self.amount
		self.refund_date = frappe.utils.nowdate()
		self.refund_reason = reason
		self.save()
