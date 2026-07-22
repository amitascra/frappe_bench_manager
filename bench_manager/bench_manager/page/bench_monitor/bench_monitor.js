frappe.pages["bench-monitor"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Bench Monitor",
		single_column: true,
	});

	frappe.bench_monitor = new BenchMonitor(page);
};

frappe.pages["bench-monitor"].on_page_show = function (wrapper) {
	if (frappe.bench_monitor) {
		frappe.bench_monitor.refresh();
	}
};

BenchMonitor = class BenchMonitor {
	constructor(page) {
		this.page = page;
		this.refresh_interval = 30; // seconds
		this.countdown = this.refresh_interval;
		this.timer = null;
		this.countdown_timer = null;

		this.setup_toolbar();
		this.setup_page();
		this.refresh();
	}

	setup_toolbar() {
		this.page.add_inner_button(__("Refresh Now"), () => {
			this.refresh();
		});
	}

	setup_page() {
		var html = `
		<style>
			.bench-monitor-page {
				padding: 16px 0;
			}
			.monitor-header {
				display: flex;
				justify-content: space-between;
				align-items: center;
				margin-bottom: 20px;
				padding: 10px 16px;
				background: var(--card-bg, #fff);
				border-radius: 6px;
				border: 1px solid var(--border-color, #d1d8dd);
			}
			.monitor-header .last-updated {
				font-size: 12px;
				color: var(--text-muted, #8d99a6);
			}
			.monitor-header .countdown-badge {
				font-size: 12px;
				padding: 2px 8px;
				border-radius: 12px;
				background: var(--primary-light, #e8f4fb);
				color: var(--primary, #5484ed);
				font-weight: 500;
			}
			.monitor-section {
				margin-bottom: 20px;
				border: 1px solid var(--border-color, #d1d8dd);
				border-radius: 6px;
				overflow: hidden;
			}
			.monitor-section-header {
				display: flex;
				justify-content: space-between;
				align-items: center;
				padding: 10px 16px;
				background: var(--subtle-fg, #f4f5f6);
				cursor: pointer;
				user-select: none;
				border-bottom: 1px solid var(--border-color, #d1d8dd);
			}
			.monitor-section-header:hover {
				background: var(--fg-hover-color, #ebeef0);
			}
			.monitor-section-title {
				font-weight: 600;
				font-size: 13px;
				display: flex;
				align-items: center;
				gap: 8px;
			}
			.monitor-section-title .section-icon {
				width: 18px;
				height: 18px;
				opacity: 0.6;
			}
			.count-badge {
				display: inline-flex;
				align-items: center;
				justify-content: center;
				min-width: 20px;
				height: 20px;
				padding: 0 6px;
				border-radius: 10px;
				font-size: 11px;
				font-weight: 600;
			}
			.count-badge.badge-danger { background: #fde8e8; color: #c92a2a; }
			.count-badge.badge-warning { background: #fff3bf; color: #845e00; }
			.count-badge.badge-info { background: #e3f2fd; color: #1565c0; }
			.count-badge.badge-success { background: #e6f4ea; color: #1e6f2e; }
			.count-badge.badge-secondary { background: var(--subtle-fg, #f4f5f6); color: var(--text-muted, #8d99a6); border: 1px solid var(--border-color, #d1d8dd); }
			.monitor-section-body {
				background: var(--card-bg, #fff);
			}
			.monitor-section-body.collapsed {
				display: none;
			}
			.monitor-table {
				width: 100%;
				border-collapse: collapse;
				font-size: 12px;
			}
			.monitor-table thead tr {
				background: var(--subtle-fg, #f4f5f6);
			}
			.monitor-table th {
				padding: 8px 12px;
				text-align: left;
				font-weight: 600;
				font-size: 11px;
				text-transform: uppercase;
				letter-spacing: 0.5px;
				color: var(--text-muted, #8d99a6);
				border-bottom: 1px solid var(--border-color, #d1d8dd);
				white-space: nowrap;
			}
			.monitor-table td {
				padding: 8px 12px;
				border-bottom: 1px solid var(--border-color, #d1d8dd);
				vertical-align: top;
				max-width: 400px;
				word-break: break-word;
			}
			.monitor-table tr:last-child td {
				border-bottom: none;
			}
			.monitor-table tr:hover td {
				background: var(--fg-hover-color, #f8f9fa);
			}
			.status-pill {
				display: inline-block;
				padding: 1px 8px;
				border-radius: 10px;
				font-size: 11px;
				font-weight: 600;
				white-space: nowrap;
			}
			.status-pill.status-running,
			.status-pill.status-ongoing,
			.status-pill.status-started { background: #fff3bf; color: #845e00; }
			.status-pill.status-failed,
			.status-pill.status-failure,
			.status-pill.status-delivery-failure,
			.status-pill.status-undelivered { background: #fde8e8; color: #c92a2a; }
			.status-pill.status-success,
			.status-pill.status-complete { background: #e6f4ea; color: #1e6f2e; }
			.status-pill.status-queued,
			.status-pill.status-pending { background: #e3f2fd; color: #1565c0; }
			.console-snippet {
				font-family: var(--mono-font, "SFMono-Regular", Consolas, monospace);
				font-size: 11px;
				background: #1e1e2e;
				color: #cdd6f4;
				padding: 6px 10px;
				border-radius: 4px;
				max-height: 80px;
				overflow-y: auto;
				white-space: pre-wrap;
				word-break: break-all;
				margin-top: 2px;
			}
			.traceback-snippet {
				font-family: var(--mono-font, "SFMono-Regular", Consolas, monospace);
				font-size: 11px;
				background: #2c1a1a;
				color: #ffb3b3;
				padding: 6px 10px;
				border-radius: 4px;
				max-height: 80px;
				overflow-y: auto;
				white-space: pre-wrap;
				word-break: break-all;
				margin-top: 2px;
			}
			.exc-snippet {
				font-family: var(--mono-font, "SFMono-Regular", Consolas, monospace);
				font-size: 11px;
				background: #2c1a1a;
				color: #ffb3b3;
				padding: 6px 10px;
				border-radius: 4px;
				max-height: 60px;
				overflow-y: auto;
				white-space: pre-wrap;
				word-break: break-all;
				margin-top: 2px;
			}
			.empty-state {
				padding: 30px;
				text-align: center;
				color: var(--text-muted, #8d99a6);
				font-size: 13px;
			}
			.empty-state .indicator-icon {
				font-size: 24px;
				margin-bottom: 8px;
				color: var(--text-extra-muted, #c8d0d8);
			}
			.chevron {
				transition: transform 0.2s;
			}
			.chevron.open {
				transform: rotate(180deg);
			}
			.doc-link {
				color: var(--primary, #5484ed);
				text-decoration: none;
				font-weight: 500;
			}
			.doc-link:hover {
				text-decoration: underline;
			}
			.text-muted-sm {
				color: var(--text-muted, #8d99a6);
				font-size: 11px;
			}
		</style>
		<div class="bench-monitor-page container">
			<div class="monitor-header">
				<div>
					<span class="font-weight-bold" style="font-size:14px;">System Monitor</span>
					<span class="last-updated ml-3" id="bm-last-updated">Not yet loaded</span>
				</div>
				<div>
					<span class="countdown-badge" id="bm-countdown">Refreshing in ${this.refresh_interval}s</span>
				</div>
			</div>
			<div id="bm-sections"></div>
		</div>`;

		$(this.page.main).html(html);
	}

	refresh() {
		this.stop_timers();

		// Show loading state on sections
		var sections_el = document.getElementById("bm-sections");
		if (sections_el) {
			sections_el.innerHTML =
				'<div class="text-center text-muted p-5"><div class="spinner-border spinner-border-sm mr-2" role="status"></div> Loading monitor data...</div>';
		}

		frappe.call({
			method: "bench_manager.bench_manager.page.bench_monitor.bench_monitor.get_monitor_data",
			callback: (r) => {
				if (r.message) {
					this.render(r.message);
				} else {
					if (sections_el) {
						sections_el.innerHTML =
							'<div class="alert alert-warning">No data returned from server.</div>';
					}
				}
				this.start_countdown();
			},
			error: () => {
				if (sections_el) {
					sections_el.innerHTML =
						'<div class="alert alert-danger">Failed to load monitor data. Check console for details.</div>';
				}
				this.start_countdown();
			},
		});
	}

	stop_timers() {
		if (this.timer) {
			clearTimeout(this.timer);
			this.timer = null;
		}
		if (this.countdown_timer) {
			clearInterval(this.countdown_timer);
			this.countdown_timer = null;
		}
	}

	start_countdown() {
		this.countdown = this.refresh_interval;
		var countdown_el = document.getElementById("bm-countdown");
		var last_updated_el = document.getElementById("bm-last-updated");

		if (last_updated_el) {
			last_updated_el.textContent =
				"Last updated: " + frappe.datetime.now_in_user_format();
		}

		this.countdown_timer = setInterval(() => {
			this.countdown--;
			if (countdown_el) {
				if (this.countdown <= 0) {
					countdown_el.textContent = "Refreshing...";
				} else {
					countdown_el.textContent = "Refreshing in " + this.countdown + "s";
				}
			}
		}, 1000);

		this.timer = setTimeout(() => {
			this.refresh();
		}, this.refresh_interval * 1000);
	}

	render(data) {
		var sections_el = document.getElementById("bm-sections");
		if (!sections_el) return;

		var html = "";
		html += this.render_error_logs(data.error_logs || []);
		html += this.render_rq_jobs(data.rq_jobs || []);
		html += this.render_bench_commands(
			data.bench_commands || [],
			data.recent_commands || []
		);
		html += this.render_agent_jobs(data.agent_jobs || []);
		html += this.render_bench_queue(data.bench_queue || []);

		sections_el.innerHTML = html;

		// Bind collapse toggles
		sections_el.querySelectorAll(".monitor-section-header").forEach((header) => {
			header.addEventListener("click", () => {
				var body = header.nextElementSibling;
				var chevron = header.querySelector(".chevron");
				if (body) {
					body.classList.toggle("collapsed");
				}
				if (chevron) {
					chevron.classList.toggle("open");
				}
			});
		});
	}

	// ── Helper: status pill ──────────────────────────────────────────────────

	status_pill(status) {
		if (!status) return "<span class=\"text-muted\">—</span>";
		var cls = "status-" + status.toLowerCase().replace(/\s+/g, "-");
		return (
			'<span class="status-pill ' + cls + '">' + frappe.utils.escape_html(status) + "</span>"
		);
	}

	// ── Helper: section wrapper ──────────────────────────────────────────────

	section(icon, title, count_html, body_html, start_open) {
		var open_class = start_open ? "" : "collapsed";
		var chevron_class = start_open ? "open" : "";
		return `
		<div class="monitor-section">
			<div class="monitor-section-header">
				<div class="monitor-section-title">
					${frappe.utils.icon(icon, "sm", "section-icon")}
					${frappe.utils.escape_html(title)}
					${count_html}
				</div>
				<div class="chevron ${chevron_class}">${frappe.utils.icon("chevron-down", "sm")}</div>
			</div>
			<div class="monitor-section-body ${open_class}">
				${body_html}
			</div>
		</div>`;
	}

	empty_state(msg) {
		return `<div class="empty-state"><div class="indicator-icon">&#10003;</div>${frappe.utils.escape_html(msg)}</div>`;
	}

	fmt_time(val) {
		if (!val) return '<span class="text-muted-sm">—</span>';
		return (
			'<span class="text-muted-sm">' +
			frappe.utils.escape_html(frappe.datetime.str_to_user(val)) +
			"</span>"
		);
	}

	doc_link(doctype, name) {
		if (!name) return "—";
		var url = frappe.utils.get_form_link(doctype, name);
		return (
			'<a href="' +
			url +
			'" class="doc-link" target="_blank">' +
			frappe.utils.escape_html(name) +
			"</a>"
		);
	}

	// ── Section 1: Error Logs ────────────────────────────────────────────────

	render_error_logs(logs) {
		var count = logs.length;
		var badge_cls = count > 0 ? "badge-danger" : "badge-secondary";
		var count_html =
			'<span class="count-badge ' + badge_cls + '">' + count + "</span>";

		if (!count) {
			return this.section("alert", "Error Logs", count_html, this.empty_state("No recent error logs"), true);
		}

		var rows = logs
			.map((log) => {
				return (
					"<tr>" +
					"<td>" +
					this.doc_link("Error Log", log.name) +
					"</td>" +
					"<td>" +
					frappe.utils.escape_html(log.title || "—") +
					"</td>" +
					"<td>" +
					frappe.utils.escape_html(log.method || "—") +
					"</td>" +
					"<td>" +
					this.fmt_time(log.creation) +
					"</td>" +
					"</tr>"
				);
			})
			.join("");

		var body =
			'<table class="monitor-table"><thead><tr>' +
			"<th>Name</th><th>Title</th><th>Method</th><th>Time</th>" +
			"</tr></thead><tbody>" +
			rows +
			"</tbody></table>";

		return this.section("alert", "Error Logs", count_html, body, true);
	}

	// ── Section 2: RQ Jobs ───────────────────────────────────────────────────

	render_rq_jobs(jobs) {
		var count = jobs.length;
		var has_failed = jobs.some(
			(j) => (j.status || "").toLowerCase() === "failed"
		);
		var badge_cls = has_failed
			? "badge-danger"
			: count > 0
			? "badge-warning"
			: "badge-secondary";
		var count_html =
			'<span class="count-badge ' + badge_cls + '">' + count + "</span>";

		if (!count) {
			return this.section("setting-alt", "RQ Jobs", count_html, this.empty_state("No running or failed RQ jobs"), true);
		}

		var rows = jobs
			.map((job) => {
				var exc = job.exc_info
					? '<div class="exc-snippet">' +
					  frappe.utils.escape_html(job.exc_info.slice(-400)) +
					  "</div>"
					: "";
				return (
					"<tr>" +
					"<td>" +
					this.doc_link("RQ Job", job.name) +
					"</td>" +
					"<td>" +
					frappe.utils.escape_html(job.job_name || "—") +
					"</td>" +
					"<td>" +
					this.status_pill(job.status) +
					"</td>" +
					"<td>" +
					frappe.utils.escape_html(job.queue || "—") +
					"</td>" +
					"<td>" +
					this.fmt_time(job.started_at) +
					"</td>" +
					"<td>" +
					exc +
					"</td>" +
					"</tr>"
				);
			})
			.join("");

		var body =
			'<table class="monitor-table"><thead><tr>' +
			"<th>Name</th><th>Job</th><th>Status</th><th>Queue</th><th>Started At</th><th>Exception</th>" +
			"</tr></thead><tbody>" +
			rows +
			"</tbody></table>";

		return this.section("setting-alt", "RQ Jobs", count_html, body, true);
	}

	// ── Section 3: Bench Manager Commands ───────────────────────────────────

	render_bench_commands(commands, recent) {
		var active = commands.filter(
			(c) => (c.status || "").toLowerCase() === "ongoing"
		);
		var failed = commands.filter(
			(c) => (c.status || "").toLowerCase() === "failed"
		);
		var count = commands.length;

		var badge_cls =
			failed.length > 0
				? "badge-danger"
				: active.length > 0
				? "badge-warning"
				: "badge-secondary";
		var count_html =
			'<span class="count-badge ' +
			badge_cls +
			'">' +
			(active.length
				? active.length + " active"
				: failed.length
				? failed.length + " failed"
				: count) +
			"</span>";

		var all_rows = [...active, ...failed, ...recent];

		if (!all_rows.length) {
			return this.section("terminal", "Bench Manager Commands", count_html, this.empty_state("No ongoing or failed commands"), true);
		}

		var rows = all_rows
			.map((cmd) => {
				var console_html = cmd.console
					? '<div class="console-snippet">' +
					  frappe.utils.escape_html(cmd.console) +
					  "</div>"
					: "";
				var time_taken = cmd.time_taken
					? frappe.utils.escape_html(String(cmd.time_taken)) + "s"
					: "—";
				return (
					"<tr>" +
					"<td>" +
					this.doc_link("Bench Manager Command", cmd.name) +
					"</td>" +
					"<td><code style=\"font-size:11px\">" +
					frappe.utils.escape_html(cmd.command || "—") +
					"</code></td>" +
					"<td>" +
					this.status_pill(cmd.status) +
					"</td>" +
					"<td>" +
					frappe.utils.escape_html(cmd.source || "—") +
					"</td>" +
					"<td>" +
					time_taken +
					"</td>" +
					"<td>" +
					this.fmt_time(cmd.creation) +
					"</td>" +
					"<td>" +
					console_html +
					"</td>" +
					"</tr>"
				);
			})
			.join("");

		var body =
			'<table class="monitor-table"><thead><tr>' +
			"<th>Name</th><th>Command</th><th>Status</th><th>Source</th><th>Time</th><th>Created</th><th>Console</th>" +
			"</tr></thead><tbody>" +
			rows +
			"</tbody></table>";

		return this.section("terminal", "Bench Manager Commands", count_html, body, true);
	}

	// ── Section 4: Agent Jobs ────────────────────────────────────────────────

	render_agent_jobs(jobs) {
		var count = jobs.length;
		var has_failed = jobs.some((j) =>
			["failure", "delivery failure", "undelivered"].includes(
				(j.status || "").toLowerCase()
			)
		);
		var badge_cls = has_failed
			? "badge-danger"
			: count > 0
			? "badge-warning"
			: "badge-secondary";
		var count_html =
			'<span class="count-badge ' + badge_cls + '">' + count + "</span>";

		if (!count) {
			return this.section("collaborations", "Agent Jobs", count_html, this.empty_state("No pending or failed agent jobs"), false);
		}

		var rows = jobs
			.map((job) => {
				var tb = job.traceback
					? '<div class="traceback-snippet">' +
					  frappe.utils.escape_html(job.traceback) +
					  "</div>"
					: "";
				return (
					"<tr>" +
					"<td>" +
					this.doc_link("Agent Job", job.name) +
					"</td>" +
					"<td>" +
					frappe.utils.escape_html(job.job_type || "—") +
					"</td>" +
					"<td>" +
					this.status_pill(job.status) +
					"</td>" +
					"<td>" +
					frappe.utils.escape_html(job.server || "—") +
					"</td>" +
					"<td>" +
					frappe.utils.escape_html(job.server_type || "—") +
					"</td>" +
					"<td>" +
					this.fmt_time(job.start) +
					"</td>" +
					"<td>" +
					tb +
					"</td>" +
					"</tr>"
				);
			})
			.join("");

		var body =
			'<table class="monitor-table"><thead><tr>' +
			"<th>Name</th><th>Job Type</th><th>Status</th><th>Server</th><th>Server Type</th><th>Started</th><th>Traceback</th>" +
			"</tr></thead><tbody>" +
			rows +
			"</tbody></table>";

		return this.section("collaborations", "Agent Jobs", count_html, body, false);
	}

	// ── Section 5: Bench Queue ───────────────────────────────────────────────

	render_bench_queue(items) {
		var count = items.length;
		var has_failed = items.some(
			(i) => (i.status || "").toLowerCase() === "failure"
		);
		var badge_cls = has_failed
			? "badge-danger"
			: count > 0
			? "badge-info"
			: "badge-secondary";
		var count_html =
			'<span class="count-badge ' + badge_cls + '">' + count + "</span>";

		if (!count) {
			return this.section("list", "Bench Queue", count_html, this.empty_state("No queued or failed bench queue items"), false);
		}

		var rows = items
			.map((item) => {
				return (
					"<tr>" +
					"<td>" +
					this.doc_link("Bench Queue", item.name) +
					"</td>" +
					"<td>" +
					frappe.utils.escape_html(item.cloud_bench || "—") +
					"</td>" +
					"<td>" +
					this.status_pill(item.status) +
					"</td>" +
					"<td>" +
					frappe.utils.escape_html(String(item.priority || "—")) +
					"</td>" +
					"<td>" +
					this.fmt_time(item.queued_at) +
					"</td>" +
					"<td>" +
					this.fmt_time(item.started_at) +
					"</td>" +
					"<td>" +
					frappe.utils.escape_html(String(item.retry_count || 0)) +
					"</td>" +
					"<td>" +
					frappe.utils.escape_html(item.error_message || "—") +
					"</td>" +
					"</tr>"
				);
			})
			.join("");

		var body =
			'<table class="monitor-table"><thead><tr>' +
			"<th>Name</th><th>Bench</th><th>Status</th><th>Priority</th><th>Queued At</th><th>Started At</th><th>Retries</th><th>Error</th>" +
			"</tr></thead><tbody>" +
			rows +
			"</tbody></table>";

		return this.section("list", "Bench Queue", count_html, body, false);
	}
};
