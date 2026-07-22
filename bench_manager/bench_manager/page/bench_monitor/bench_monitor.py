import frappe


@frappe.whitelist()
def get_monitor_data():
    data = {}

    # Error Logs (last 20)
    try:
        data["error_logs"] = frappe.get_all(
            "Error Log",
            fields=["name", "title", "method", "creation"],
            order_by="creation desc",
            limit=20,
        )
    except Exception:
        data["error_logs"] = []

    # RQ Jobs - running, queued, and failed
    try:
        data["rq_jobs"] = frappe.get_all(
            "RQ Job",
            fields=[
                "name",
                "job_name",
                "status",
                "queue",
                "started_at",
                "ended_at",
                "exc_info",
            ],
            filters={"status": ["in", ["started", "queued", "failed"]]},
            order_by="started_at desc",
            limit=30,
        )
    except Exception:
        data["rq_jobs"] = []

    # Bench Manager Commands - ongoing + failed (last 50)
    try:
        commands = frappe.get_all(
            "Bench Manager Command",
            fields=[
                "name",
                "command",
                "status",
                "source",
                "time_taken",
                "creation",
                "console",
            ],
            filters={"status": ["in", ["Ongoing", "Failed"]]},
            order_by="creation desc",
            limit=50,
        )
        # Truncate console field to last 500 chars
        for cmd in commands:
            if cmd.get("console") and len(cmd["console"]) > 500:
                cmd["console"] = "..." + cmd["console"][-500:]
        data["bench_commands"] = commands
    except Exception:
        data["bench_commands"] = []

    # Recent successful commands for context (last 10)
    try:
        data["recent_commands"] = frappe.get_all(
            "Bench Manager Command",
            fields=["name", "command", "status", "source", "time_taken", "creation"],
            filters={"status": "Success"},
            order_by="creation desc",
            limit=10,
        )
    except Exception:
        data["recent_commands"] = []

    # Agent Jobs - pending, running, failed
    try:
        data["agent_jobs"] = frappe.get_all(
            "Agent Job",
            fields=[
                "name",
                "job_type",
                "status",
                "server",
                "server_type",
                "start",
                "end",
                "traceback",
                "output",
            ],
            filters={
                "status": [
                    "in",
                    ["Pending", "Running", "Failure", "Delivery Failure", "Undelivered"],
                ]
            },
            order_by="start desc",
            limit=30,
        )
        # Truncate traceback to last 500 chars
        for job in data["agent_jobs"]:
            if job.get("traceback") and len(job["traceback"]) > 500:
                job["traceback"] = "..." + job["traceback"][-500:]
    except Exception:
        data["agent_jobs"] = []

    # Bench Queue - queued, started, failed
    try:
        data["bench_queue"] = frappe.get_all(
            "Bench Queue",
            fields=[
                "name",
                "status",
                "priority",
                "cloud_bench",
                "queued_at",
                "started_at",
                "error_message",
                "retry_count",
            ],
            filters={"status": ["in", ["Queued", "Started", "Failure"]]},
            order_by="queued_at desc",
            limit=20,
        )
    except Exception:
        data["bench_queue"] = []

    return data
