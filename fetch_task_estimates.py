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


def fetch_paginated(url, params_base, label=""):
    """Fetch all pages from a ClickUp paginated endpoint."""
    all_tasks = []
    page = 0
    while True:
        params = {**params_base, "page": page}
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        tasks = resp.json().get("tasks", [])
        all_tasks.extend(tasks)
        if len(tasks) < 100:
            break
        page += 1
        time.sleep(0.1)
    if all_tasks and label:
        print(f"    {label}: {len(all_tasks)} tasks")
    return all_tasks


def fetch_lists_tasks(lists, base_params, seen_ids, all_tasks):
    """Fetch tasks from a list of ClickUp lists, dedup by seen_ids."""
    for lst in lists:
        tasks = fetch_paginated(
            f"{BASE_URL}/list/{lst['id']}/task",
            base_params,
        )
        new_tasks = [t for t in tasks if t["id"] not in seen_ids]
        all_tasks.extend(new_tasks)
        seen_ids.update(t["id"] for t in new_tasks)


def fetch_all_lists_in_folder(folder_id):
    """Get all lists (archived + non-archived) in a folder."""
    all_lists = []
    for archived_flag in ["false", "true"]:
        resp = requests.get(
            f"{BASE_URL}/folder/{folder_id}/list",
            headers=HEADERS, params={"archived": archived_flag},
        )
        resp.raise_for_status()
        all_lists.extend(resp.json().get("lists", []))
    return all_lists


def fetch_all_folders_in_space(space_id):
    """Get all folders (archived + non-archived) in a space."""
    all_folders = []
    for archived_flag in ["false", "true"]:
        resp = requests.get(
            f"{BASE_URL}/space/{space_id}/folder",
            headers=HEADERS, params={"archived": archived_flag},
        )
        resp.raise_for_status()
        all_folders.extend(resp.json().get("folders", []))
    return all_folders


def fetch_folderless_lists(space_id):
    """Get folderless lists (archived + non-archived) directly under a space."""
    all_lists = []
    for archived_flag in ["false", "true"]:
        resp = requests.get(
            f"{BASE_URL}/space/{space_id}/list",
            headers=HEADERS, params={"archived": archived_flag},
        )
        resp.raise_for_status()
        all_lists.extend(resp.json().get("lists", []))
    return all_lists


def fetch_all_tasks():
    base_params = {"include_closed": "true", "subtasks": "true"}

    # 1) Active tasks from workspace endpoint
    print("  Fetching active workspace tasks...")
    all_tasks = fetch_paginated(
        f"{BASE_URL}/team/{TEAM_ID}/task",
        {**base_params, "include_archived": "true"},
        label="Active workspace",
    )
    seen_ids = {t["id"] for t in all_tasks}
    before = len(all_tasks)
    print(f"    Total: {len(all_tasks)} tasks")

    # 2) Deep crawl of active spaces (archived folders, archived lists, folderless lists)
    print("  Deep-crawling active spaces...")
    resp = requests.get(
        f"{BASE_URL}/team/{TEAM_ID}/space",
        headers=HEADERS, params={"archived": "false"},
    )
    resp.raise_for_status()
    active_spaces = resp.json().get("spaces", [])

    for space in active_spaces:
        space_before = len(all_tasks)

        # 2a) All folders (archived + non-archived) -> all lists (archived + non-archived)
        folders = fetch_all_folders_in_space(space["id"])
        for folder in folders:
            lists = fetch_all_lists_in_folder(folder["id"])
            fetch_lists_tasks(lists, base_params, seen_ids, all_tasks)
            time.sleep(0.05)

        # 2b) Folderless lists (directly under space)
        folderless = fetch_folderless_lists(space["id"])
        fetch_lists_tasks(folderless, base_params, seen_ids, all_tasks)

        new_count = len(all_tasks) - space_before
        if new_count > 0:
            print(f"    Space '{space['name']}': +{new_count} new tasks")
        time.sleep(0.05)

    print(f"    Active spaces: +{len(all_tasks) - before} new tasks")
    before = len(all_tasks)

    # 3) Deep crawl of archived spaces
    print("  Deep-crawling archived spaces...")
    resp4 = requests.get(
        f"{BASE_URL}/team/{TEAM_ID}/space",
        headers=HEADERS, params={"archived": "true"},
    )
    resp4.raise_for_status()
    for space in resp4.json().get("spaces", []):
        space_before = len(all_tasks)

        # 3a) All folders -> all lists
        folders = fetch_all_folders_in_space(space["id"])
        for folder in folders:
            lists = fetch_all_lists_in_folder(folder["id"])
            fetch_lists_tasks(lists, base_params, seen_ids, all_tasks)
            time.sleep(0.05)

        # 3b) Folderless lists
        folderless = fetch_folderless_lists(space["id"])
        fetch_lists_tasks(folderless, base_params, seen_ids, all_tasks)

        new_count = len(all_tasks) - space_before
        if new_count > 0:
            print(f"    Archived space '{space['name']}': +{new_count} new tasks")
        time.sleep(0.05)

    print(f"    Archived spaces: +{len(all_tasks) - before} new tasks")

    print(f"  Total tasks: {len(all_tasks)}")
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

    # Extract custom fields (budget, temps vendu, etc.)
    custom_fields = {}
    FIELD_IDS = {
        "40266294-b68e-4bed-962a-67a96b87c5cc": "budget",
        "48ebbdfa-84c9-42ce-b848-db403dd51e77": "temps_vendu_jours",
        "6fca6126-5723-487e-85ae-75ffce896180": "date_debut",
        "f1f59d97-3c81-49b9-b508-cfc1a95ae3d7": "date_fin",
        "aec8c6cc-6251-40b1-bf7f-ba26fbf3a6e6": "type_prestation",
    }
    for cf in task.get("custom_fields", []):
        field_id = cf.get("id")
        if field_id in FIELD_IDS:
            value = cf.get("value")
            if cf.get("type") == "drop_down" and isinstance(value, dict):
                value = value.get("name")
            elif cf.get("type") == "drop_down" and value is not None:
                # value is an index, resolve from options
                opts = cf.get("type_config", {}).get("options", [])
                value = next((o["name"] for o in opts if str(o.get("orderindex")) == str(value)), value)
            custom_fields[FIELD_IDS[field_id]] = value

    return {
        "id": task.get("id"),
        "name": task.get("name"),
        "time_estimate": task.get("time_estimate") or 0,
        "time_spent": task.get("time_spent") or 0,
        "assignees": assignees,
        "status": status_obj.get("status") if isinstance(status_obj, dict) else str(status_obj),
        "due_date": task.get("due_date"),
        "start_date": task.get("start_date"),
        "date_created": task.get("date_created"),
        "date_updated": task.get("date_updated"),
        "date_closed": task.get("date_closed"),
        "folder_id": folder.get("id") if isinstance(folder, dict) else None,
        "folder_name": folder.get("name") if isinstance(folder, dict) else None,
        "list_id": list_obj.get("id") if isinstance(list_obj, dict) else None,
        "list_name": list_obj.get("name") if isinstance(list_obj, dict) else None,
        "space_id": space.get("id") if isinstance(space, dict) else None,
        "custom_fields": custom_fields,
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
