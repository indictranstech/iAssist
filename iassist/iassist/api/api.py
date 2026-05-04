import frappe
from frappe import _
from frappe.model.meta import get_meta
import requests
from frappe.utils.file_manager import save_file
import os, base64, re

def map_valid_fields(doctype, data):
    meta = get_meta(doctype)
    valid_fieldnames = [df.fieldname for df in meta.fields] + ["name"]
    return {key: value for key, value in data.items() if key in valid_fieldnames}

def get_doc_payload(doctype, doc):
    meta = get_meta(doctype)
    valid_fieldnames = [df.fieldname for df in meta.fields] + ["name", "doctype"]
    
    exclude_fields = {"contact", "company","custom_status_wise_activity_table"}  
    valid_fieldnames = [field for field in valid_fieldnames if field not in exclude_fields]

    doc_dict = doc if isinstance(doc, dict) else doc.as_dict()

    return {
        key: safe_json_value(value)
        for key, value in doc_dict.items()
        if key in valid_fieldnames
    }

def safe_json_value(value):
    import datetime, uuid

    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        # convert timedelta to HH:MM:SS string
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def get_create_url(doctype):
    if not doctype:
        return
    url = "/api/method/icentral_support.icentral_support.api.issue.create_issue"
    return url


def get_update_url(doctype):
    if not doctype:
        return
    url = "/api/method/icentral_support.icentral_support.api.issue.update_issue"
    return url


@frappe.whitelist(allow_guest=True)
def generate_token(data=None):
    try:
        if not data:
            data = frappe.request.get_json()
    except Exception:
        return{"message": "Invalid JSON data provided."}
    try:
        username = data.get("username")
        password = data.get("password")
        if frappe.db.exists("User",{'name':username},'name'):
            login_url = f"{frappe.utils.get_url()}/api/method/login"
            response = requests.post(login_url, data={"usr": username, "pwd": password})
            if response.status_code == 200:
                frappe.set_user(username)
                user_doc = frappe.get_doc("User", username)
                user_doc.reload()
                if not user_doc.api_key:
                    user_doc.api_key = frappe.generate_hash(length=15)
                user_doc.api_secret = frappe.generate_hash(length=15)
                user_doc.save(ignore_permissions = True,ignore_version=True)
                return {
                "status_code": 200,
                "api_key": user_doc.api_key,
                "api_secret": user_doc.get_password("api_secret")
                }
            else:
                return {"status_code": 401, "message": "Invalid login"}
        else:
            return{"status_code":404,"message":"User does not exist"}
    except Exception as e:
        # frappe.log_error(title="Generate Token Failed",message=str(e))
        return str(e)
    
# def set_token_daily():
#     try:
#         config = frappe.get_single("IAssist Support Configurations")
#         if not config.is_active:
#             return
#         base_url = config.central_support_url.rstrip("/")
#         token_url = f"{base_url}/api/method/icentral_support.icentral_support.api.issue.generate_token"
        
#         if config.is_multiple_users:
#             for user_row in config.ics_multi_user_details:
#                 data_login = {"username": user_row.username, "password": user_row.get_password("password")}
#                 auth_response = requests.post(token_url, json=data_login) 

#                 if auth_response.status_code != 200:
#                     frappe.log_error(
#                         "Invalid credentials while generating token",
#                         "IAssist Token"
#                     )

#                     return {
#                         "status": "Error",
#                         "message": "Credentials may be incorrect. Please update password and try again."
#                     }

#                 auth_data = auth_response.json()
#                 message = auth_data.get("message")

#                 if not isinstance(message, dict):
#                     return {
#                         "status": "Error",
#                         "message": f"Authentication failed for user {user_row.username}. Please verify credentials."
#                     }

#                 api_key = message.get("api_key")
#                 api_secret = message.get("api_secret")

#                 if not api_key or not api_secret:
#                     return {
#                         "status": "Error",
#                         "message": "Token generation Failed<br>Central server rejected credentials<br><b>Please update the password and try again."
#                     }

#                 user_row.api_key = api_key
#                 user_row.api_secret = api_secret
#                 # else:
#                 #     frappe.log_error(title="Generate Token failed",message="")
#                 #     return{"message":"Generate Token failed"}
#             config.save()
#             return {
#             "status": "success",
#             "message": "Token generated successfully"
#         }
#         else:
#             data_login = {"username": config.username, "password": config.get_password("password")}
#             auth_response = requests.post(token_url, json=data_login)
#             auth_data = auth_response.json()
            
#             if auth_response.status_code != 200:
#                 frappe.log_error(
#                     "Invalid credentials while generating token",
#                     "IAssist Token"
#                 )
#                 return {
#                     "status": "error",
#                     "message": "Credentials may be incorrect. Please update password and try again."
#                 }

#             auth_data = auth_response.json()
#             message = auth_data.get("message")

#             if not isinstance(message, dict):
#                 return {
#                     "status": "Error",
#                     "message": "Authentication failed. Please verify credentials."
#                 }

#             api_key = message.get("api_key")
#             api_secret = message.get("api_secret")

#             if not api_key or not api_secret:
#                 return {
#                     "status": "Error",
#                     "message": "Token generation Failed<br>Central server rejected credentials<br><b>Please update the password and try again."
#                 }

#             config.api_key = api_key
#             config.api_secret = api_secret
#             config.save()
#         return {
#             "status": "success",
#             "message": "Token generated successfully"
#         }    
#     except Exception as e:
#         frappe.log_error(title="Generate token failed", message=str(e))
#         return {
#             "status": "Error",
#             "message": "Unexpected error occurred. Please check Error Log."
#         }
def get_updated_payload(doc):
    changed_fields = get_common_fields(doc)
    if doc.doctype == "Issue":
        changed_fields["name"] = doc.custom_master_ic_id
    elif doc.doctype == "HD Ticket":
        changed_fields["name"] = doc.custom_master_ticket_id
    elif doc.doctype == "IA Support Tickets":
        changed_fields["name"] = doc.central_ticket_id

    changed_fields["custom_last_sync"] = frappe.utils.now()
    return changed_fields

def sync_to_central_support_to_create(doc):
    # try:
    if check_if_sync_id_exists(doc):
        return {"message": "Already Created."}
    config = frappe.db.get_single_value("IAssist Support Configurations","central_support_url")
    headers={}
    if get_configurations(doc):
        headers = get_configurations(doc)
    else:
        frappe.db.set_value(doc.doctype,doc.name,{
                "custom_sync_status": "Not Synced",
                "custom_last_sync": frappe.utils.now()
        })
        frappe.msgprint("Central sync failed : User is not available in configurations")
        # frappe.log_error("Central sync failed : User is not available in configurations")

    base_url = config.rstrip("/")
    doctype = doc.doctype
    endpoint_path = get_create_url(doctype)

    if not endpoint_path:
        # frappe.log_error(f"No endpoint defined for Doctype: {doctype}")
        return

    create_url = f"{base_url}{endpoint_path}"
    # frappe.log_error(title="sync_to_central_support_to_create", message=f"""frappe.utils.get_url()={frappe.utils.get_url()},config={config},  create_url={create_url}, base_url={base_url}, endpoint_path={endpoint_path}""")

    payload = get_doc_payload(doctype, doc)
    payload["raised_by"] = frappe.session.user
    payload["attachments"] = get_attachments_for_payload(doc)
    payload["custom_url"] = frappe.utils.get_url()
    payload["custom_referred_doctype"] = doc.doctype
    payload["custom_sync_status"] = "Synced"
    payload["custom_last_sync"] = frappe.utils.now()
    payload["priority"] = doc.ia_priority if doctype == "IA Support Tickets" else doc.priority
    payload['custom_analysis']=doc.custom_analysis if doc.custom_analysis else ""
    payload['custom_corrective_actions'] = doc.custom_corrective_actions if doc.custom_corrective_actions else ''
    payload['custom_preventive_actions']= doc.custom_preventive_actions if doc.custom_preventive_actions else ''
                
    response = requests.post(create_url, json=payload, headers=headers)
    response_data = response.json()
    # frappe.log_error(title="Sync Response data", message=response_data)
    # frappe.log_error(title="Request Body", message=f"""request ticket body-payload={payload}""")

    if response.status_code == 401 or response.status_code == 403:
        frappe.db.set_value(doc.doctype,doc.name,{
                "custom_sync_status": "Not Synced",
                "custom_last_sync": frappe.utils.now()
        })
        return {"message": "Authorization failed: Please verify that the user account is active and the API Key/API Secret are valid."}

    if response_data.get("message", {}).get("status_code") == 200:
        referred_doctype = response_data.get("message", {}).get("data").get("doctype")
        frappe.db.set_value(doc.doctype, doc.name, {
                "custom_sync_status": "Synced",
                "custom_referred_doctype":referred_doctype,
                "custom_last_sync": frappe.utils.now()
            })
        name = response_data.get("message", {}).get("data").get("name")
        if doctype == "Issue":
            frappe.db.set_value(doc.doctype,doc.name,"custom_master_ic_id",name)
        elif doctype == "HD Ticket":
            frappe.db.set_value(doc.doctype,doc.name,"custom_master_ticket_id",name)
        elif doctype == "IA Support Tickets":
            frappe.db.set_value(doc.doctype,doc.name,"central_ticket_id",name)

        return {"message": "Issue raised successfully", "data": doc.name}
    else:
        frappe.db.set_value(doc.doctype,doc.name,"custom_sync_status","Not Synced")
        # frappe.log_error(title=f"Central sync failed [{response.status_code}]",message=response.text)
        message = (response_data.get("message", {}).get("message") if response_data and isinstance(response_data, dict) else response.status_code)
        return str(message)
    # except Exception:
    #     frappe.log_error(title="Sync to central failed",message=frappe.get_traceback())
    #     message = (response_data.get("message", {}).get("message") if response_data and isinstance(response_data, dict) else response.status_code)
    #     return str(message)

    
def sync_to_central_support_to_update(doc):
    # try:
    config = frappe.db.get_single_value("IAssist Support Configurations","central_support_url")
    headers={}
    if get_configurations(doc):
        headers = get_configurations(doc)
    else:
        frappe.db.set_value(doc.doctype,doc.name,{
                "custom_sync_status": "Not Synced",
                "custom_last_sync": frappe.utils.now()
        })            
        frappe.msgprint("Central sync failed : User is not available in configurations")
        # frappe.log_error("Central sync failed : User is not available in configurations")
        return{"message:Central sync failed : User is not available in configurations"}
    base_url = config.rstrip("/")
    doctype = doc.doctype 
    endpoint_path = get_update_url(doctype)
    if not endpoint_path:
        # frappe.log_error(f"No endpoint defined for Doctype: {doctype}")
        return{"message":f"No endpoint defined for Doctype: {doctype}"}

    update_url = f"{base_url}{endpoint_path}"
    payload = get_updated_payload(doc)
    payload["attachments"]= get_attachments_for_payload(doc)
    payload["custom_url"] = frappe.utils.get_url()
    payload["custom_referred_doctype"] = doc.custom_referred_doctype
    payload["custom_sync_status"] = "Synced"
    payload["custom_last_sync"] = frappe.utils.now()
    payload["priority"] = doc.ia_priority if doctype == "IA Support Tickets" else doc.priority
    payload["custom_not_feasible"] = doc.custom_not_feasible if doc.custom_not_feasible else ""
    payload["custom_ticket_hold_reason"] = doc.custom_ticket_hold_reason if doc.custom_ticket_hold_reason else ""
    payload["custom_ticket_closure_reason"] = doc.custom_ticket_closure_reason if doc.custom_ticket_closure_reason else ""

    response = requests.post(update_url, json=payload, headers=headers)
    response_data = response.json()
     
    # frappe.log_error(title="Sync Response data", message=f"""response_data={response_data}, update_url={update_url}""")
    # frappe.log_error(title="Request Body URL", message=f"""frappe.utils.get_url()={frappe.utils.get_url()}""")

    if response.status_code == 401 or response.status_code == 403:
        frappe.db.set_value(doc.doctype,doc.name,{
                "custom_sync_status": "Not Synced",
                "custom_last_sync": frappe.utils.now()
        })
        return {"message": "Authorization failed: Please verify that the user account is active and the API Key/API Secret are valid."}
    if response_data.get("message", {}).get("status_code") == 200:
        frappe.db.set_value(doc.doctype, doc.name,"custom_sync_status", "Synced")
        frappe.db.set_value(doc.doctype, doc.name,"custom_last_sync",frappe.utils.now())
        return {"message": "Issue updated successfully", "data": doc.name}
    else:
        frappe.db.set_value(doc.doctype,doc.name,"custom_sync_status","Not Synced")
        # frappe.log_error(f"Central sync failed [{response.status_code}]",message =response.text)
        message = (response_data.get("message", {}).get("message") if response_data and isinstance(response_data, dict) else response.status_code)
        return str(message)
    # except Exception:
    #     frappe.log_error(title="Sync to central failed", message=frappe.get_traceback())
    #     return {"message": frappe.get_traceback()}
    
def get_configurations(doc):
    config = frappe.get_doc("IAssist Support Configurations")
    if not config.is_active:
        return
    headers={}
    api_key = None     
    api_secret = None

    if config.is_multiple_users:
        logged_user = frappe.session.user
        for user_row in config.ics_multi_user_details:
            if logged_user == user_row.username:
                api_key = user_row.api_key
                api_secret = user_row.get_password("api_secret")
                # frappe.log_error(title="get_configurations",message=f"""api_key{api_key}, api_secret={api_secret}""")
                break   
        if not api_key or not api_secret:
            return None 
    else:
        api_key = config.api_key
        api_secret = config.get_password("api_secret")
    if not (api_key or api_secret):
        return headers
    api_key = api_key.strip()
    api_secret = api_secret.strip()

    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }
    # frappe.log_error(title="get_configurations-headers",message=f"""headers={headers}""")
    return headers

def check_if_sync_id_exists(doc):
    if doc.doctype == "Issue" and doc.custom_master_ic_id:
        return True
    elif doc.doctype == "IA Support Tickets" and doc.central_ticket_id:
        return True
    elif doc.doctype == "HD Ticket" and doc.custom_master_ticket_id:
        return True

@frappe.whitelist()
def sync_to_create(doctype,docname):
    doc = frappe.get_doc(doctype,docname)
    # sync_to_central_support_to_create(doc)
    return sync_to_central_support_to_create(doc)

@frappe.whitelist()
def sync_to_update(docname, doctype):
    doc = frappe.get_doc(doctype,docname)
    # sync_to_central_support_to_update(doc)
    return sync_to_central_support_to_update(doc)

@frappe.whitelist()
def get_allowed_user(doctype):
    config = frappe.get_doc("IAssist Support Configurations")
    is_allowed_user = 0
    if config.is_multiple_users:
        for user_row in config.ics_multi_user_details:
            if frappe.session.user == user_row.username and config.doctype_for_raising_ticket == doctype:
                is_allowed_user = 1
                break
    else:
        if config.username == frappe.session.user and config.doctype_for_raising_ticket == doctype:
            is_allowed_user = 1
    return is_allowed_user


def get_common_fields(doc):
    if not doc:
        return
    valid_fieldname={'subject','status','description','priority','issue_type','name','resolution_details','feedback_rating',
                     'summary','feedback','feedback_extra','opening_date','opening_time','first_responded_on'}
    doc_dict = doc if isinstance(doc,dict) else doc.as_dict()
   
    payload = {
        key:safe_json_value(value) for key,value in doc_dict.items() if key in valid_fieldname 
    }
    return payload


def file_to_base64(file_url):
    try:
        clean_url = file_url.split("?")[0]

        file_path = frappe.get_site_path(clean_url.lstrip("/"))

        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    except Exception as e:
       
        # frappe.log_error(
        #     title="Attachment Encoding Failed",
        #     message=f"File: {file_url}, Error: {str(e)}"
        # )
        return str(e) or None
    

def get_attachments_for_payload(doc):
    attachments_payload = []

    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": doc.doctype,
            "attached_to_name": doc.name
        },
        fields=["file_name", "file_url", "file_type"]
    )

    html_fields = {
        "description": getattr(doc, "description", "") or "",
        "resolution_details": getattr(doc, "resolution_details", "") or "",
        "summary": getattr(doc,"summary", "") or ""
    }

    for file_info in files:
        try:
            if file_info.file_url.startswith("/private"):
                file_path = frappe.get_site_path(file_info.file_url.lstrip("/"))
            else:
                file_path = frappe.get_site_path("public", file_info.file_url.lstrip("/"))

            if not os.path.exists(file_path):
                continue

            with open(file_path, "rb") as f:
                encoded_content = base64.b64encode(f.read()).decode()

            related_to = "attachment"
            for field, html in html_fields.items():
                if file_info.file_url in html:
                    related_to = field
                    break

            attachments_payload.append({
                "file_name": file_info.file_name,
                "file_type": file_info.file_type,
                "file_base64": encoded_content,
                "related_to": related_to 
            })

        except Exception as e:
            # frappe.log_error(title=f"Error encoding file {file_info.file_name}",message=str(e))
            return str(e)
    return attachments_payload

def save_attachments_for_doc(doc, attachments):
    if not attachments:
        return

    saved_files = []

    for file in attachments:
        file_name = file.get("file_name")
        file_base64 = file.get("file_base64")
        related_to = file.get("related_to") or "attachment"

        if not file_name or not file_base64:
            # frappe.log_error(f"Invalid attachment payload: {file}")
            continue

        try:
            file_doc = save_file(
                fname=file_name,
                content=file_base64,
                dt=doc.doctype,
                dn=doc.name,
                decode=True
            )

            saved_files.append(file_doc.file_url)

            if related_to in ["description", "resolution_details","summary"]:
                html_value = getattr(doc, related_to, "") or ""

                html_value = re.sub(
                    r'src="[^"]+"',
                    f'src="{file_doc.file_url}"',
                    html_value,
                    count=1 
                )

                # setattr(doc, related_to, html_value)
                doc.db_set(related_to,html_value)
        except Exception as e:  
            # frappe.log_error(title=f"Failed to save attachment {file_name}",message=str(e))
            return str(e)
    # if saved_files:
    #     doc.save(ignore_permissions=True) 

    return saved_files

def get_delete_update_url(doctype):
    if not doctype:
        return
    url = "/api/method/icentral_support.icentral_support.api.issue.delete_remark_update"
    return url


