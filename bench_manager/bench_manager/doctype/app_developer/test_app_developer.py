# Copyright (c) 2026, Amit Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


def _make_user(email):
	"""App Developer.user is mandatory and unique, so each test needs its own
	User to link to."""
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	return email


class TestAppDeveloper(FrappeTestCase):
	def test_developer_creation(self):
		user = _make_user("test-developer-creation@example.com")
		developer = frappe.get_doc(
			{
				"doctype": "App Developer",
				"user": user,
				"developer_name": "test_dev",
				"email": user,
			}
		)
		developer.insert()
		self.assertTrue(developer.name)

	def test_duplicate_user_rejected(self):
		"""One User cannot have two developer profiles - App Developer.user is
		unique. This is the reachable duplicate case: validate_email's own
		check cannot be provoked through a normal insert, because
		populate_from_user() overwrites email from the linked User first, and
		User.email is itself unique."""
		user = _make_user("test-duplicate-user@example.com")

		frappe.get_doc(
			{
				"doctype": "App Developer",
				"user": user,
				"developer_name": "test_dev1",
				"email": user,
			}
		).insert()

		duplicate = frappe.get_doc(
			{
				"doctype": "App Developer",
				"user": user,
				"developer_name": "test_dev2",
				"email": user,
			}
		)

		with self.assertRaises((frappe.ValidationError, frappe.DuplicateEntryError)):
			duplicate.insert()
