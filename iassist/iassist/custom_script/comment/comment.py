import frappe
from iassist.iassist.api.api import *
import requests
from frappe import _
import json
from frappe.core.doctype.comment.comment import Comment as FrappeComment
from frappe.desk.notifications import notify_mentions
from frappe.core.doctype.comment.comment import update_comment_in_doc
from frappe.desk.doctype.notification_log.notification_log import NotificationLog, get_email_header, is_email_notifications_enabled_for_type, send_notification_email, set_notifications_as_unseen
import re
from urllib.parse import urlparse
import base64, os
from frappe.utils.file_manager import save_file

def get_attachments_for_comment_payload(doc):
    """Read local files referenced in a comment's content and base64-encode them for transport."""
    attachments_payload = []
    content = doc.content or ""

    pattern = r'src="(/(?:private/)?files/[^"]+)"'
    matches = re.findall(pattern, content)

    for file_url in set(matches):
        try:
            clean_url = urlparse(file_url).path
            file_doc = frappe.get_doc("File", {"file_url": clean_url})

            if clean_url.startswith("/private"):
                file_path = frappe.get_site_path(clean_url.lstrip("/"))
            else:
                file_path = frappe.get_site_path("public", clean_url.lstrip("/"))

            if not os.path.exists(file_path):
                continue

            with open(file_path, "rb") as f:
                encoded_content = base64.b64encode(f.read()).decode()

            attachments_payload.append({
                "file_name": file_doc.file_name,
                "file_type": file_doc.file_type,
                "file_base64": encoded_content,
                "content_hash": file_doc.content_hash,
                "source_file_url": file_url,
            })
        except Exception as e:
            frappe.log_error(title="Comment attachment encode failed", message=f"{file_url}: {str(e)}")

    return attachments_payload


def save_attachments_for_comment(doc, attachments):
    """Save base64 attachments locally (public, attached to this comment) and fix content to point at them."""
    if not attachments:
        return

    content = doc.content or ""

    for file in attachments:
        file_name = file.get("file_name")
        file_base64 = file.get("file_base64")
        content_hash = file.get("content_hash")
        source_file_url = file.get("source_file_url")

        if not file_name or not file_base64:
            continue

        existing_file = None
        if content_hash:
            existing_file = frappe.db.get_value(
                "File",
                {"content_hash": content_hash, "attached_to_doctype": doc.doctype, "attached_to_name": doc.name},
                ["name", "file_url", "is_private"],
                as_dict=True,
            )

        if existing_file:
            if existing_file.is_private:
                existing_doc = frappe.get_doc("File", existing_file.name)
                existing_doc.is_private = 0
                existing_doc.save(ignore_permissions=True)
                new_file_url = frappe.db.get_value("File", existing_file.name, "file_url")
            else:
                new_file_url = existing_file.file_url
        else:
            try:
                file_doc = save_file(
                    fname=file_name,
                    content=file_base64,
                    dt=doc.doctype,
                    dn=doc.name,
                    decode=True,
                    # is_private=0
                )
                new_file_url = file_doc.file_url
            except Exception as e:
                frappe.log_error(title="Comment attachment save failed", message=f"{file_name}: {str(e)}")
                continue

        if source_file_url and source_file_url in content:
            content = content.replace(source_file_url, new_file_url)

    if content != (doc.content or ""):
        frappe.db.set_value("Comment", doc.name, "content", content, update_modified=False)
        doc.content = content


def sync_comment_to_icentral(doc, method):
    try:
        if doc.custom_comment_from_icentral:  
            return
        if doc.reference_doctype not in ("IA Support Tickets"):
            return

        config = frappe.get_single("IAssist Support Configurations")
        headers = get_configurations(doc) 
        if not headers:
            # frappe.log_error(title="Central sync failed : User not available in configurations")
            return

        base_url = config.central_support_url.rstrip("/")
        endpoint_path = f"{base_url}/api/method/icentral_support.icentral_support.custom_script.comment.comment.create_comment_in_icentral"

        reference_name = None
        if doc.reference_doctype == "IA Support Tickets":
            reference_name = frappe.db.get_value(doc.reference_doctype, doc.reference_name, "central_ticket_id")
        # else:
            # frappe.log_error(title="refrence name not found")
        referred_doctype = frappe.db.get_value(doc.reference_doctype, doc.reference_name, "custom_referred_doctype")
        if not reference_name and referred_doctype:
            return
        payload = get_doc_payload(doc.doctype, doc)
        payload["attachments"] = get_attachments_for_comment_payload(doc)
        payload["reference_doctype"] = referred_doctype
        payload["reference_name"] = reference_name
        payload["custom_ia_comment_id"] = doc.name
        payload["custom_comment_sync_from_iassist"] = 1
        payload["custom_ia_comment_id"] = doc.name

        response = requests.post(endpoint_path, json=payload, headers=headers)
        if response.status_code == 200:
            response_data = response.json()
            comment_id = response_data["message"]["data"]["name"]
            frappe.db.set_value("Comment", doc.name, "custom_ic_comment_id",comment_id)
            return {"message":"commented successfully"}
        else:
            response_data = response.json()
            message = (response_data.get("message", {}).get("message") if response_data and isinstance(response_data, dict) else response.status_code)
            # frappe.log_error(title="Comment sync failed",message=message)
    except Exception as e:
        # frappe.log_error(title="Comment sync failed",message=str(e))
        return str(e)

def update_comment_in_icentral(doc,method):
    try:
        if not doc or doc.is_new():
            return
        if not (doc.reference_doctype == "IA Support Tickets"):
            return
        config = frappe.get_single("IAssist Support Configurations")
        headers = get_configurations(doc)
        if not headers:
            frappe.db.set_value(doc.doctype,doc.name,"custom_sync_status","Not Synced")
            frappe.msgprint("Central sync failed : User is not available in configurations")
            # frappe.log_error(title="Central sync failed : User is not available in configurations")

        base_url = config.central_support_url.rstrip("/")
        doctype = doc.doctype
        endpoint_path = f"{base_url}/api/method/icentral_support.icentral_support.custom_script.comment.comment.update_comment_in_icentral"
        payload = {"name":doc.custom_ic_comment_id, "content":doc.content}
        payload["attachments"] = get_attachments_for_comment_payload(doc)

        if not endpoint_path:
            frappe.log_error(title=f"No endpoint defined for Doctype: {doctype}")
            return
        response = requests.post(endpoint_path, json=payload, headers=headers)
        if response.status_code == 200:
            return True
        else:
            response_data = response.json()
            message = (response_data.get("message", {}).get("message") if response_data and isinstance(response_data, dict) else response.status_code)
            # frappe.log_error(title="Comment sync failed",message=message)
    except Exception as e:
        # frappe.log_error(title="Comment sync failed",message=str(e))
        return str(e)

@frappe.whitelist()
def update_comment_in_iassist(data=None):
    if frappe.request.method != "POST":
        frappe.response["http_status_code"] = 405
        return {
            "status_code": 405,
            "message": "Method Not Allowed. Please use POST.",
            "data": {}
        }

    user = frappe.session.user
    doctype = "Comment"

    try:
        if not data:
            data = frappe.request.data
            data = json.loads(data)
    except Exception as e:
        return {
            "status_code": 400,
            "message": f"Invalid request data: {str(e)}",
            "data": {}
        }
    

    if not frappe.has_permission(doctype, "write", user=user):
        return{"message":"You do not have permission to update this document."}

    valid_fields = map_valid_fields(doctype, data)
    docname = valid_fields.get("name")

    if not docname:
        return {
            "status_code": 400,
            "message": "Missing required field: 'name'",
            "data": {}
        }

    if not frappe.db.exists(doctype, docname):
        return {
            "status_code": 404,
            "message": f"{doctype} {docname} does not exist.",
            "data": {}
        }

    try:
        doc = frappe.get_doc(doctype, docname)
    
        for key, value in valid_fields.items():
            if key != "name":
                setattr(doc, key, value)
        doc.save()
        save_attachments_for_comment(doc, data.get("attachments"))

        return {
            "status_code": 200,
            "message": f"{doctype} {docname} updated successfully.",
            "data": doc.as_dict()
        }
    except Exception as e:
        return {
            "status_code": 500,
            "message": f"Error updating document: {str(e)}",
            "data": {}
        }     
        
@frappe.whitelist()
def create_comment_in_iassist(data=None):
    if frappe.request.method != "POST":
        frappe.response["http_status_code"] = 405
        return {
            "status_code": 405,
            "message": "Method Not Allowed. Please use POST.",
            "data": {}
        }
    try:
        if not data:
            data = frappe.request.data
            data = json.loads(data)

    except Exception:
        return{"message": "Invalid JSON data provided."}

    if not isinstance(data, dict):
        return{"message": "Invalid input format. Expected JSON object."}

    user = frappe.session.user
    doctype = "Comment"
    if not frappe.has_permission(doctype, "create", user=user):
        return{"message":"You do not have permission to create an Comment"}
    
    if frappe.db.exists("Comment", {"custom_ia_comment_id": data.get("name")}):
        return {"status_code": 200, "data": {"name": data.get("name")}}

    comment_by=data.get("comment_by"),
    valid_data = map_valid_fields(doctype, data)

    comment_doc = frappe.new_doc(doctype)  
    for key, value in valid_data.items():
        if key!= 'name':
            setattr(comment_doc, key, value)
    comment_doc.flags.ignore_sync = True
    comment_doc.save()
    save_attachments_for_comment(comment_doc, data.get("attachments"))
    return {"status_code": 200, "data": {"name": comment_doc.name}}

# def after_insert(doc,method):
#     return sync_comment_to_icentral(doc, method)
    
# def on_update(doc,method):
#     return update_comment_in_icentral(doc,method)
    
class CustomComment(FrappeComment):
    def after_insert(self):
        """
        Override the core Comment's after_insert method.
        Example: sync with external system only if a checkbox is not checked.
        """
        if self.custom_comment_from_icentral == 1:
            return None
        else:
            super(CustomComment, self).after_insert()
            doc= frappe.get_doc("Comment", self.name)
            return sync_comment_to_icentral(doc,method=None)
       
    def on_update(self):
        super(CustomComment,self).on_update()
        doc= frappe.get_doc("Comment", self.name)
        return update_comment_in_icentral(doc,method=None)

