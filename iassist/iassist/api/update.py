import frappe
import json
from frappe import _
from iassist.iassist.api.api import *
from datetime import datetime
from frappe.utils import get_datetime



@frappe.whitelist()
def update_ticket(data=None):
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

    
    # refer_doctype = frappe.get_single_value("IAssist Support Configurations","doctype_for_raising_ticket")
    valid_fields = map_valid_fields(refer_doctype, data)
    docname = valid_fields.get("name")
    # custom_sla_status = data.pop("agreement_status","")
    attachments = data.pop("attachments",[])
    if not docname:
        return {
            "status_code": 400,
            "message": "Missing required field to update on IAssist:'name'",
            "data": {}
        }

    if not frappe.db.exists(refer_doctype, docname):
        return {
            "status_code": 404,
            "message": f"{refer_doctype} {docname} does not exist on IAssist.",
            "data": {}
        }

    try:
        doc = frappe.get_doc(refer_doctype, docname)
        valid_fields.pop('custom_referred_doctype')
        response_by= valid_fields.pop("response_by")
        # resolution_time = valid_fields.pop('resolution_time')
        if refer_doctype == "Issue":
            valid_fields.pop("agreement_status")
        assigned_users = data.get("assignees_list", "not_provided")
        for key, value in valid_fields.items():
            if key != 'name':
                df = doc.meta.get_field(key)
                if not df:
                    # Field doesn't exist on this doctype at all — ignore it
                    continue
                if df and df.fieldtype == "Link" and value:
                    if frappe.db.exists(df.options, value):
                        setattr(doc, key, value)
                    else:
                        setattr(doc, key, None) 
                else:
                    setattr(doc, key, value) 
        if refer_doctype=="IA Support Tickets":
            doc.db_set('ia_priority',data.get("priority",""))

        # sla_field_mapping = {
        #     "sla": "custom_sla_info",
        #     "agreement_status": "custom_sla_status",
        #     "resolution_by": "custom_resolution_by_info",
        #     "service_level_agreement_creation": "custom_sla_creation",
        #     "response_by": "custom_response_by_info",
        #     "on_hold_since": "custom_on_hold_since_info",
        #     "total_hold_time": "custom_total_hold_time_info"
        # }
        # for src, target in sla_field_mapping.items():
        #     value = data.get(src)
        #     if value is not None:
        #         parsed_value = parse_datetime_or_duration(src, value)
        #         setattr(doc, target, parsed_value)

        doc.save()
        status_value = valid_fields.get('status')
        if status_value:
            try:
                doc.db_set("status", status_value)
            except Exception as e:
                # frappe.log_error(
                #     title=f"Status update failed for {refer_doctype} {docname}",
                #     message=str(e)
                # )
                return str(e)
        # doc.db_set("custom_sla_status",custom_sla_status)
        doc.db_set("response_by",get_datetime(response_by))
        # doc.db_set("resolution_time",resolution_time)
        doc.db_set("custom_sync_status", "Synced")
        if assigned_users != "not_provided": 
            if not assigned_users: 
                doc.db_set("custom_assigned_in_icentral", "")
            else:
                assigned_users_html = build_assigned_users_table(assigned_users)
                doc.db_set("custom_assigned_in_icentral", assigned_users_html)
        if attachments:
            save_attachments_for_doc(doc,attachments)
        return {
            "status_code": 200,
            "message": f"{refer_doctype} {docname} updated successfully.",
            "data": doc.as_dict()
        }

    except Exception as e:
        return {
            "status_code": 500,
            "message": f"Error updating document on IAssist {str(e)}",
            "data": {}
        }
    

def parse_datetime_or_duration(fieldname, value):
    """Convert string values into datetime/date or rounded durations."""
    if not value:
        return None

    if isinstance(value, str) and "T" in value:
        try:
            dt = datetime.fromisoformat(value)
            rounded = dt.replace(microsecond=0)
            return rounded
        except Exception:
            pass
   
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except Exception:
            pass

    if fieldname == "total_hold_time":
        try:
            seconds = float(value)
            minutes = round(seconds / 60, 2)
            return minutes  
        except Exception:
            pass

    return value

def build_assigned_users_table(assigned_users):

    if not assigned_users:
        return "" 
    
    rows = ""
    for i ,user in enumerate(assigned_users):
    
        rows += f"""<tr>
                <td>{i+1}</td>
                <td>{user.get('assigned_to')}</td>
                <td>{user.get('email')}</td>
                <td>{user.get('time')}</td>
                </tr>
                """
       
    table_html = f"""
        <table class="table table-bordered small">
            <thead>
                <tr>
                    <th>Sr No</th>
                    <th>Assigned To</th>
                    <th>Email</th>
                    <th>Time</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    """
        
    return table_html
