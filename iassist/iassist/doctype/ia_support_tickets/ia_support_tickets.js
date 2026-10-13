// Copyright (c) 2025, New Indictrans Technologies pvt. ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("IA Support Tickets", {
	refresh: function (frm) {
		// render_status_box(frm);
		assigned_to(frm);
		frm.trigger("make_dashboard");
		if (!frm.doc.__islocal) {
			frappe.call({
				method: "iassist.iassist.api.api.get_allowed_user",
				args: { doctype: frm.doc.doctype },
				callback: function (r) {
					if (
						r.message &&
						r.message == 1 &&
						!frm.doc.custom_deleted_from_icentral_support &&
						!frm.doc.custom_requested_to_delete_ticket &&
						!frm.doc.__islocal
					) {
						if (!frm.doc.central_ticket_id) {
							let raiseBtn = frm.add_custom_button("Raise Ticket", function () {
								frappe.call({
									method: "iassist.iassist.api.api.sync_to_create",
									args: {
										docname: frm.doc.name,
										doctype: frm.doc.doctype,
									},
									freeze: true,
									callback: function (res) {
										if (!res.exc) {
											let message =
												typeof res.message === "string"
													? res.message
													: JSON.stringify(res.message);

											frappe.msgprint(message);
											frm.reload_doc();
										} else {
											frappe.msgprint(
												"Failed to raise ticket on Icentral Support",
											);
										}
									},
								}, 5000);
							});
							$(raiseBtn).removeClass("btn-default").css({
								"background-color": "#1E88E5",
								"border-color": "#1E88E5",
								color: "#ffffff",
							});
						} else if (!frm.doc.custom_requested_to_delete_ticket) {
							let updateBtn = frm.add_custom_button("Update Ticket", function () {
								frappe.call({
									method: "iassist.iassist.api.api.sync_to_update",
									args: {
										docname: frm.doc.name,
										doctype: frm.doc.doctype,
									},
									callback: function (res) {
										if (!res.exc) {
											let message =
												typeof res.message === "string"
													? res.message
													: JSON.stringify(res.message);

											frappe.msgprint(message);
											frm.reload_doc();
										} else {
											frappe.msgprint(
												"Failed to update ticket on Icentral Support",
											);
										}
									},
								});
							});
							$(updateBtn).removeClass("btn-default").css({
								"background-color": "#FB8C00",
								"border-color": "#FB8C00",
								color: "#ffffff",
							});

							let deleteBtn = frm.add_custom_button(
								"Request For Deletion",
								function () {
									let d = new frappe.ui.Dialog({
										title: "Request for Deletion",
										fields: [
											{
												fieldtype: "Small Text",
												fieldname: "reason",
												label: "Reason for Deletion",
												reqd: 1,
											},
										],
										primary_action_label: "Delete Request",
										primary_action(values) {
											frappe.call({
												method: "iassist.iassist.api.delete.delete_request_icentral",
												args: {
													doctype: frm.doc.doctype,
													docname: frm.doc.name,
												},
												callback: function (r) {
													if (
														r.message &&
														r.message.status == "success"
													) {
														frappe.call({
															method: "frappe.desk.form.utils.add_comment",
															args: {
																reference_doctype: frm.doc.doctype,
																reference_name: frm.doc.name,
																content: values.reason,
																comment_email: frappe.session.user,
																comment_by:
																	frappe.session.user_fullname,
															},
															callback: function (res) {
																frappe.show_alert({
																	message: __(
																		"Comment and deletion remark updated successfully on Icentral",
																	),
																	indicator: "green",
																});
																frm.reload_doc();
																d.hide();
															},
														});
													} else {
														frappe.show_alert({
															message: __(
																"Failed to acknowledge delete request on icentral.",
															),
															indicator: "red",
														});
													}
												},
											});
										},
									});

									d.show();
								},
							);
							$(deleteBtn).removeClass("btn-default").css({
								"background-color": "#070707",
								"border-color": "#151616",
								color: "#ffffff",
							});
						}
					}
				},
			});
		}
	},
	custom_sync_status(frm) {
		frm.trigger("make_dashboard");
	},
	custom_requested_to_delete_ticket(frm) {
		frm.trigger("make_dashboard");
	},
	custom_deleted_from_icentral_support(frm) {
		frm.trigger("make_dashboard");
	},
	onload_post_render: function (frm) {
		frm.trigger("make_dashboard");

		frm.fields_dict &&
			Object.keys(frm.fields_dict).forEach((fieldname) => {
				frm.fields_dict[fieldname].df.onchange = () => {
					if (frm.doc.__unsaved) {
						frm.clear_custom_buttons();
						// Re-render status box after clearing buttons
						// so the messages are not lost
						render_status_box(frm);
					}
				};
			});
	},
	// make_dashboard: function (frm) {
	// 	$("div").remove(".form-dashboard-section.custom");

	// 	frm.dashboard.add_section(
	// 		frappe.render_template("ia_support_tickets_dashboard", {}),
	// 		__("Instructions"),
	// 	);

	// 	frm.dashboard.show();
	// },

	make_dashboard: function (frm) {
		$("div").remove(".form-dashboard-section.custom");

		let instructions_html = frappe.render_template("ia_support_tickets_dashboard", {});
		let status_html = get_status_html(frm);

		frm.dashboard.add_section(instructions_html + status_html, __("Instructions"));

		frm.dashboard.show();
	},
});

function assigned_to(frm) {
	if (frm.doc.custom_assigned_in_icentral) {
		$("div").remove(".form-dashboard-section.custom");
		frm.dashboard.add_section(frm.doc.custom_assigned_in_icentral, __("Assigned To"));
		frm.dashboard.show();
	}
}

// function render_status_box(frm) {
// 	if (!frm.fields_dict || !frm.fields_dict.status_box) return;

// 	let messages = [];

// 	if (frm.doc.custom_sync_status === "Not Synced") {
// 		messages.push({
// 			text: "This ticket has not been synced yet.",
// 		});
// 	}

// 	if (frm.doc.custom_requested_to_delete_ticket == 1) {
// 		messages.push({
// 			text: "A deletion request has been raised for this ticket. You can proceed to delete it.",
// 		});
// 	}

// 	if (frm.doc.custom_deleted_from_icentral_support == 1) {
// 		messages.push({
// 			text: "This ticket has been deleted from ICentral Support.",
// 		});
// 	}

// 	frm.fields_dict.status_box.$wrapper.empty();

// 	if (!messages.length) return;

// 	let html = `<div style="padding: 10px 10px 2px 10px;">`;

// 	messages.forEach((msg) => {
// 		html += `
// 			<div style="
// 				display: flex;
// 				align-items: flex-start;
// 				gap: 8px;
// 				background: #e0f4ff;
// 				border-left: 5px solid #38aae1;
// 				padding: 10px 14px;
// 				margin-bottom: 8px;
// 				border-radius: 6px;
// 				font-size: 13px;
// 				color: #1a4f6e;
// 				box-shadow: 0 1px 3px rgba(56,170,225,0.10);
// 			">
// 				<span style="font-size:15px; margin-top:1px;"></span>
// 				<span>${msg.text}</span>
// 			</div>
// 		`;
// 	});

// 	html += `</div>`;

// 	frm.fields_dict.status_box.$wrapper.append(html);
// }

function get_status_html(frm) {
	let messages = [];

	if (frm.doc.custom_sync_status === "Not Synced") {
		messages.push("This ticket has not been synced yet.");
	}
	if (frm.doc.custom_requested_to_delete_ticket == 1) {
		messages.push(
			"A deletion request has been raised for this ticket. You can proceed to delete it.",
		);
	}
	if (frm.doc.custom_deleted_from_icentral_support == 1) {
		messages.push("This ticket has been deleted from ICentral Support.");
	}

	if (!messages.length) return "";

	let html = `<div style="padding: 10px 10px 2px 10px;">`;
	messages.forEach((text) => {
		html += `
			<div style="
				display: flex;
				align-items: flex-start;
				gap: 8px;
				background: #e0f4ff;
				border-left: 5px solid #38aae1;
				padding: 10px 14px;
				margin-bottom: 8px;
				border-radius: 6px;
				font-size: 13px;
				color: #1a4f6e;
				box-shadow: 0 1px 3px rgba(56,170,225,0.10);
			">
				<span style="font-size:15px; margin-top:1px;"></span>
				<span>${text}</span>
			</div>
		`;
	});
	html += `</div>`;
	return html;
}
