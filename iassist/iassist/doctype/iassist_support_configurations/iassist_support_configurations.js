// Copyright (c) 2025, New Indictrans Technologies pvt. ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("IAssist Support Configurations", {
	refresh: function (frm) {
		user_query(frm);
		// 		if (!frm.doc.__islocal) {
		// 			frm.add_custom_button("Generate Token", function () {
		// 				frappe.call({
		// 					method: "iassist.iassist.doctype.iassist_support_configurations.iassist_support_configurations.generate_token_on_custom_button",
		// 					callback: function (res) {
		// 						if (!res.message) return;
		// 						let response = res.message;
		// 						frappe.msgprint({
		// 							title: response.status === "success" ? __("Success") : __("Error"),
		// 							indicator: response.status === "success" ? "green" : "red",
		// 							message: response.message,
		// 						});
		// 						if (response.status === "success") {
		// 							frm.reload_doc();
		// 						}
		// 					},
		// 				});
		// 			});
		// 		}
	},
	onload: function (frm) {
		// Child table field filter
		user_query(frm);
	},
});

// function user_query(frm) {
// 	frm.set_query("username", function () {
// 		return {
// 			query: "frappe.core.doctype.user.user.user_query",
// 			filters: {
// 				role: "IAssist User",
// 			},
// 		};
// 	});
// 	frm.fields_dict["ics_multi_user_details"].grid.get_field("username").get_query = function (
// 		doc,
// 		cdt,
// 		cdn,
// 	) {
// 		return {
// 			query: "frappe.core.doctype.user.user.user_query",
// 			filters: {
// 				role: "IAssist User",
// 			},
// 		};
// 	};
// }
function user_query(frm) {
	frm.set_query("username", function () {
		return {
			query: "iassist.iassist.api.api.get_users_by_role",
			filters: {
				role: "IAssist User",
			},
		};
	});

	frm.fields_dict["ia_multi_user_details"].grid.get_field("username").get_query = function () {
		return {
			query: "iassist.iassist.api.api.get_users_by_role",
			filters: {
				role: "IAssist User",
			},
		};
	};
}
