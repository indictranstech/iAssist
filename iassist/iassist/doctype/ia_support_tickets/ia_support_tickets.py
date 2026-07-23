# Copyright (c) 2025, New Indictrans Technologies pvt. ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname,revert_series_if_last
from frappe.utils import now


class IASupportTickets(Document):
    def validate(self):
        status_wise_activity_table(self)
        make_rating_mandatory(self)

    def before_insert(self):
        self.raised_by = frappe.session.user
        if self.raised_by:
            self.full_name = frappe.db.get_value("User",{'name':self.raised_by},fieldname=['full_name'])

    def autoname(self):
        dot_series = f"IAT.-.YYYY.-.#####"
        self.name = make_autoname(dot_series)

    def on_trash(self):
        dot_series = f"IAT.-.YYYY.-.#####"
        revert_series_if_last(dot_series, self.name)
        if self.custom_requested_to_delete_ticket == 0 and self.custom_deleted_from_icentral_support==0 and self.central_ticket_id:
            frappe.throw('For deleting this synced documents,You need to request on Icentral.Go to Actions -> Request For Deletion. Note: Sync Status should not be Not Synced')

    def on_update(self):
        self.custom_sync_status = "Not Synced"
    # 	frappe.db.set_value("IA Support Tickets",self.name,"custom_sync_status","Not Synced")

def make_rating_mandatory(self):
    if self.status == "Closed" and not self.feedback_rating:
        frappe.throw("Please provide a rating before closing the ticket.")
def status_wise_activity_table(self):

    if frappe.flags.get('ignore_status_activity_flag'):
        return
    
    if self.is_new():
        activity = {
            "timestamp": now(),
            "status": self.status,
            "updated_by" : frappe.session.user,
        }
        self.append("custom_status_wise_activity_table",activity)
    else:
        old_doc = self.get_doc_before_save()
        if old_doc.status != self.status:
            activity = {
            "timestamp": self.custom_last_sync,
            "status": self.status,
            "updated_by" : frappe.session.user,
        }
            self.append("custom_status_wise_activity_table",activity)

