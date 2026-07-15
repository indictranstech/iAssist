import frappe
import json
from frappe import _
from frappe.model.meta import get_meta
import requests
from frappe.utils.password import get_decrypted_password
from iassist.iassist.api.api import *

           
@frappe.whitelist()
def delete_request_icentral(doctype,docname):
    doc = frappe.get_doc(doctype,docname)
    sync = sync_delete_remark(doc)
    return sync


def sync_delete_remark(doc):
    try:
        
        if doc.doctype == "IA Support Tickets":   
            if not doc.central_ticket_id:
                return
        
        config = frappe.get_single("IAssist Support Configurations")
        
        if get_configurations(doc):
            headers = get_configurations(doc)
        else:
            frappe.db.set_value(doc.doctype,doc.name,"custom_sync_status","Not Synced")
            frappe.msgprint("Central sync failed : User is not available in configurations")
            # frappe.log_error("Central sync failed : User is not available in configurations")
 
        base_url = config.central_support_url.rstrip("/")
        doctype = doc.doctype
        endpoint_path = get_delete_update_url(doctype)

        if not endpoint_path:
            # frappe.log_error(f"No endpoint defined for Doctype: {doctype}")
            return

        delete_update_url = f"{base_url}{endpoint_path}"
        payload = {
            "custom_referred_doctype":doc.custom_referred_doctype,
            "custom_deleted_from_iassist":1,
            "custom_sync_status":"Synced",
            "custom_last_sync":frappe.utils.now(),
            "custom_delete_remark":f"Ticket from {doc.doctype} {doc.name} has been requested to delete from IAssist."

        }
        
        if doc.doctype == "IA Support Tickets":
            payload['name'] = doc.central_ticket_id
        
        response = requests.post(delete_update_url, json=payload, headers=headers)
        response_data = response.json()
        print(response,'response',response.text)

        if response.status_code in [401,403]:
            return {"message": "Authorization failed: Please verify that the user account is active and the API Key/API Secret are valid."}

        if response_data.get("message", {}).get("status_code") == 200:
            
            frappe.db.set_value(doc.doctype, doc.name, {
                    "custom_sync_status": "Synced",
                    'custom_requested_to_delete_ticket':1,
                    "custom_last_sync": frappe.utils.now(),
                    "custom_delete_remark":f"{doc.name} has been requested to delete from Icentral Support"
                })
            return {"status":"success","message":"Deletion request acknowledged successfully."}
        else:

            # frappe.log_error(title=f"Central sync failed [{response.status_code}]",message=response.text)
            message = (response_data.get("message", {}).get("message") if response_data and isinstance(response_data, dict) else response.status_code)
            return str(message)
    except Exception:
        # frappe.log_error(title="Sync to central failed",message=frappe.get_traceback())
        message = (response_data.get("message", {}).get("message") if response_data and isinstance(response_data, dict) else response.status_code)
        return str(message)


@frappe.whitelist()
def update_delete_remark(data=None):
    if frappe.request.method != "POST":
        frappe.response["http_status_code"] = 405
        return {
            "status_code": 405,
            "message": "Method Not Allowed. Please use POST.",
            "data": {}
        }

    user = frappe.session.user
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
    
    refer_doctype = data.get("custom_referred_doctype")
    if not frappe.has_permission(refer_doctype, "write", user=user):
        return{"message":"You do not have permission to update this document."}
    valid_fields = map_valid_fields(refer_doctype, data)
    docname = valid_fields.get("name")
    if not docname:
        return {
            "status_code": 400,
            "message": "Missing required field to update on IAssist:'name'",
            "data": {}
        }

    try:
        doc = frappe.get_doc(refer_doctype, docname)
        valid_fields.pop('custom_referred_doctype')
        for key, value in valid_fields.items():
            if key != 'name':
                setattr(doc, key, value)
                    
        doc.save()
       
        if refer_doctype == "IA Support Tickets":
            frappe.db.set_value("IA Support Tickets",{'name':docname},"central_ticket_id",None)
        
        return {
            "status_code": 200,
            "message": f"{refer_doctype} {docname} updated successfully.",
        }

    except Exception as e:
        return {
            "status_code": 500,
            "message": f"Error updating document on IAssist {str(e)}",
            "data": {}
        }

    

