import frappe
from iassist.iassist.api.api import *
import requests
import json
from frappe.core.doctype.comment.comment import Comment as FrappeComment
from frappe.desk.notifications import notify_mentions
from frappe.core.doctype.comment.comment import update_comment_in_doc

def sync_comment_to_icentral(doc, method):
    try:
        if doc.custom_comment_from_icentral:  
            return
        if doc.reference_doctype not in ("Issue", "IA Support Tickets", "HD Ticket"):
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
        elif doc.reference_doctype == "Issue":
            reference_name = frappe.db.get_value(doc.reference_doctype, doc.reference_name, "custom_master_ic_id")
        elif doc.reference_doctype == "HD Ticket":
            reference_name = frappe.db.get_value(doc.reference_doctype, doc.reference_name, "custom_master_ticket_id")
        # else:
            # frappe.log_error(title="refrence name not found")
        referred_doctype = frappe.db.get_value(doc.reference_doctype, doc.reference_name, "custom_referred_doctype")
        if not reference_name and referred_doctype:
            return
        payload = get_doc_payload(doc.doctype, doc)
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
        if not (doc.reference_doctype == "Issue" or doc.reference_doctype == "IA Support Tickets" or doc.reference_doctype == "HD Ticket"):
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
