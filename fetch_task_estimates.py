#!/usr/bin/env python3
"""
Fetch ALL tasks across ClickUp workspace that have time estimates,
then produce a per-user summary.

Uses ClickUp API v2 - GET /team/{team_id}/task (filtered workspace-wide).
"""

import json
import time
import requests
from collections import defaultdict
from pathlib import Path

# Configuration
API_KEY = "pk_82507373_W88DTWK21TOL2R6YN23VXHO6TONU5VII"
BASE_URL = "https://api.clickup.com/api/v2"
TEAM_ID = "9015001133"
OUTPUT_DIR = Path("/Users/benoit/api-clickup")
RAW_FILE = OUTPUT_DIR / "all_tasks_raw.json"
SUMMARY_FILE = OUTPUT_DIR / "task_estimates_summary.json"

HEADERS = {
    "Authorization": API_KEY,
    "Content-Type": "application/json",
}

MS_PER_HOUR = 3_600_000


def fetch_all_tasks():
    all_tasks = []
    page = 0
    url = f"{BASE_URL}/team/{TEAM_ID}/task"

    while True:
        params = {
            "include_closed": "true",
            "subtasks": "true",
            "page": page,
        }

        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()

        tasks = data.get("tasks", [])
        all_tasks.extend(tasks)

        if page % 5 == 0:
            print(f"  Page {page}: fetched {len(tasks)} tasks (total so far: {len(all_tasks)})")

        if len(tasks) < 100:
            print(f"  Last page reached (page {page}, {len(tasks)} tasks). Done.")
            break

        page += 1
        time.sleep(0.1)

    return all_tasks


def extract_task_fields(task):
    assignees = []
    for a in task.get("assignees", []):
        assignees.append({
            "id": a.get("id"),
            "username": a.get("username"),
            "email": a.get("email"),
        })

    status_obj = task.get("status", {})
    folder = task.get("folder", {})
    list_obj = task.get("list", {})
    space = task.get("space", {})

    return {
        "id": task.get("id"),
        "name": task.get("name"),
        "time_estimate": task.get("time_estimate") or 0,
        "time_spent": task.get("time_spent") or 0,
        "assignees": assignees,
        "status": status_obj.get("status") if isinstance(status_obj, dict) else str(status_obj),
        "date_created": task.get("date_created"),
        "date_updated": task.get("date_updated"),
        "date_closed": task.get("date_closed"),
        "folder_id": folder.get("id") if isinstance(folder, dict) else None,
        "folder_name": folder.get("name") if isinstance(folder, dict) else None,
        "list_id": list_obj.get("id") if isinstance(list_obj, dict) else None,
        "list_name": list_obj.get("name") if isinstance(list_obj, dict) else None,
        "space_id": space.get("id") if isinstance(space, dict) else None,
    }


def build_summary(cleaned_tasks):
    tasks_with_estimate = [t for t in cleaned_tasks if t["time_estimate"] > 0]

    user_stats = defaultdict(lambda: {
        "total_estimate_hours": 0.0,
        "total_spent_hours": 0.0,
        "task_count": 0,
        "projects": defaultdict(float),
    })

    for t in tasks_with_estimate:
        est_hours = t["time_estimate"] / MS_PER_HOUR
        spent_hours = t["time_spent"] / MS_PER_HOUR
        folder_name = t["folder_name"] or "(no folder)"

        if not t["assignees"]:
            key = "(unassigned)"
            user_stats[key]["total_estimate_hours"] += est_hours
            user_stats[key]["total_spent_hours"] += spent_hours
            user_stats[key]["task_count"] += 1
            user_stats[key]["projects"][folder_name] += est_hours
        else:
            for a in t["assignees"]:
                key = a.get("username") or a.get("email") or str(a.get("id"))
                user_stats[key]["total_estimate_hours"] += est_hours
                user_stats[key]["total_spent_hours"] += spent_hours
                user_stats[key]["task_count"] += 1
                user_stats[key]["projects"][folder_name] += est_hours

    user_stats_clean = {}
    for user, stats in sorted(user_stats.items()):
        user_stats_clean[user] = {
            "total_estimate_hours": round(stats["total_estimate_hours"], 2),
            "total_spent_hours": round(stats["total_spent_hours"], 2),
            "task_count": stats["task_count"],
            "projects": {
                k: round(v, 2)
                for k, v in sorted(stats["projects"].items(), key=lambda x: -x[1])
            },
        }

    summary = {
        "total_tasks_fetched": len(cleaned_tasks),
        "tasks_with_time_estimate": len(tasks_with_estimate),
        "total_estimate_hours": round(
            sum(t["time_estimate"] for t in tasks_with_estimate) / MS_PER_HOUR, 2
        ),
        "total_spent_hours": round(
            sum(t["time_spent"] for t in tasks_with_estimate) / MS_PER_HOUR, 2
        ),
        "per_user": user_stats_clean,
    }

    return summary


def main():
    print("=" * 60)
    print("ClickUp Task Estimates Fetcher")
    print("=" * 60)

    print("\n[1/4] Fetching all tasks from workspace...")
    raw_tasks = fetch_all_tasks()
    print(f"       Total raw tasks fetched: {len(raw_tasks)}")

    print("\n[2/4] Extracting task fields...")
    cleaned = [extract_task_fields(t) for t in raw_tasks]

    print(f"\n[3/4] Saving raw data to {RAW_FILE}")
    with open(RAW_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    print(f"       Saved {len(cleaned)} tasks.")

    print(f"\n[4/4] Building summary -> {SUMMARY_FILE}")
    summary = build_summary(cleaned)
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total tasks fetched:        {summary['total_tasks_fetched']}")
    print(f"  Tasks with time estimate:   {summary['tasks_with_time_estimate']}")
    print(f"  Total estimated hours:      {summary['total_estimate_hours']}h")
    print(f"  Total spent hours:          {summary['total_spent_hours']}h")
    print(f"\n  Per-user breakdown:")
    for user, stats in summary["per_user"].items():
        print(f"\n    {user}:")
        print(f"      Tasks:          {stats['task_count']}")
        print(f"      Estimate:       {stats['total_estimate_hours']}h")
        print(f"      Spent:          {stats['total_spent_hours']}h")
        print(f"      Top projects:")
        for proj, hours in list(stats["projects"].items())[:5]:
            print(f"        - {proj}: {hours}h")

    print("\nDone.")


if __name__ == "__main__":
    main()
