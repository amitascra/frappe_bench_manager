# Copyright (c) 2026, Amit Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class AppReview(Document):
	def validate(self):
		# Check if member already has a review for this app
		if self.get("__islocal"):
			existing_review = frappe.db.exists("App Review", {
				"app": self.app,
				"member": self.member
			})
			if existing_review and existing_review != self.name:
				frappe.throw("You have already reviewed this app")
		
		# Validate rating range
		if self.rating < 1 or self.rating > 5:
			frappe.throw("Rating must be between 1 and 5")
		
		# Set review date if not set
		if not self.review_date:
			self.review_date = frappe.utils.today()
		
		# Check if member has purchased this app (verified purchase)
		self.is_verified_purchase = self.check_verified_purchase()
	
	def check_verified_purchase(self):
		"""Check if member has purchased this app"""
		member_app = frappe.db.exists("Member App", {
			"member": self.member,
			"app": self.app
		})
		return 1 if member_app else 0
	
	def on_update(self):
		"""Update app's aggregate rating and review count"""
		self.update_app_rating()
	
	def on_trash(self):
		"""Update app's aggregate rating and review count when review is deleted"""
		self.update_app_rating()
	
	def on_insert(self):
		"""Update app's aggregate rating and review count when review is created"""
		self.update_app_rating()
	
	def update_app_rating(self):
		"""Update the parent App's rating and review count based on all reviews"""
		try:
			# Get all reviews for this app
			reviews = frappe.get_all("App Review", 
				filters={"app": self.app},
				fields=["rating"]
			)
			
			if not reviews:
				# No reviews, reset to 0
				frappe.db.set_value("App", self.app, {
					"rating": 0,
					"review_count": 0
				})
			else:
				# Calculate average rating
				total_rating = sum(r.rating for r in reviews)
				avg_rating = total_rating / len(reviews)
				
				# Update app
				frappe.db.set_value("App", self.app, {
					"rating": round(avg_rating, 1),
					"review_count": len(reviews)
				})
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Update App Rating Error")
