import frappe
import json
from frappe import _
from iassist.iassist.api.api import map_valid_fields, save_attachments_for_doc

@frappe.whitelist(allow_guest=False)
def create_ticket(data=None):
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
    refer_doctype = frappe.get_single_value("IAssist Support Configurations","doctype_for_raising_ticket")

    if not frappe.has_permission(refer_doctype, "create", user=user):
        return{"message":"You do not have permission to create an Issue."}
    
    attachments = data.pop("attachments", [])
    required_fields = ["subject"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return{"message":f"Missing required fields: {', '.join(missing)}"}
    valid_data = map_valid_fields(refer_doctype, data)

    doc = frappe.new_doc(refer_doctype)
    if refer_doctype == "IA Support Tickets":
        valid_data['central_ticket_id'] = data.get("name")
   
    valid_data['custom_referred_doctype'] = data.get("doctype")
    
    for key, value in valid_data.items():
        if key!= 'name':
            setattr(doc, key, value)

    doc.save()
    save_attachments_for_doc(doc, attachments)
    return {
        "status_code": 200,
        "message": f"{refer_doctype} created successfully",
        "data": {"name": doc.name,"custom_referred_doctype":refer_doctype}
    }