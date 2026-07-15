import frappe
from iassist.iassist.api.api import *
from frappe import _
from frappe.utils.data import quoted, slug
from frappe.desk.doctype.notification_log.notification_log import NotificationLog, get_email_header, is_email_notifications_enabled_for_type, send_notification_email, set_notifications_as_unseen
   
   
class CustomNotificationLog(NotificationLog):
    def after_insert(self):
        if self.document_type not in ["IA Support Tickets"]:
            super().after_insert()
        else:
            frappe.publish_realtime("notification", after_commit=True, user=self.for_user)
            set_notifications_as_unseen(self.for_user)
            if  is_email_notifications_enabled_for_type(self.for_user, self.type):
                try:
                    custom_send_notification_email(self)
                
                except frappe.OutgoingEmailError:
                    self.log_error(_("Failed to send notification email"))
       
def custom_send_notification_email(doc: NotificationLog):

    if doc.type == "Energy Point" and doc.email_content is None:
        return

    from frappe.utils import get_url_to_form, strip_html

    user = frappe.db.get_value("User", doc.for_user, fieldname=["email", "language"], as_dict=True)
    if not user:
        return

    header = get_email_header(doc, user.language)
    email_subject = strip_html(doc.subject)
    args = {
        "body_content": doc.subject,
        "description": doc.email_content,
    }
    if doc.link:
        args["doc_link"] = doc.link
    else:
        args["document_type"] = doc.document_type
        args["document_name"] = doc.document_name
        args["doc_link"] = get_url_to_form(doc.document_type, doc.document_name)

    if doc.document_type not in ["IA Support Tickets"]:
        return
    else:
        docname2 = None
        if doc.document_type == "IA Support Tickets":
            docname2 = frappe.db.get_value(doc.document_type, doc.document_name, "central_ticket_id")
        args["doc_link1"] = get_url_to_form(doc.document_type, doc.document_name)
        doctype = frappe.db.get_value(doc.document_type, doc.document_name, "custom_referred_doctype")
        # customer = frappe.db.get_value(doc.document_type, doc.document_name, "customer")

        # if customer :
        #     args["customer"] = customer
        args["customer"] = "Clients"
        
        args["doctype"]= doctype
        
        if doctype and docname2:
            args["doc_link2"] = get_url_icnetral(doc, doctype, docname2)
            frappe.sendmail(
                recipients=user.email,
                subject=email_subject,
                template="email_comment_notification",
                args=args,
                header=[header, "orange"],
                now=frappe.flags.in_test,
            )


def get_url_icnetral(doc, doctype, docname) -> str:
    base_url = frappe.db.get_single_value("IAssist Support Configurations", "central_support_url")
    url = base_url + f"/app/{quoted(slug(doctype))}/{quoted(docname)}"
    return url