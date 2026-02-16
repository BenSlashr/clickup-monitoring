#!/usr/bin/env python3
"""Répartition du temps de Lucas Colin par projet - 6 derniers mois."""

import json
from datetime import datetime
from collections import defaultdict

# Charger les données
with open("/Users/benoit/api-clickup/lucas_time_entries.json") as f:
    entries = json.load(f).get("data", [])

with open("/Users/benoit/api-clickup/folder_mapping.json") as f:
    folder_names = json.load(f)

# Agrégation
by_project = defaultdict(float)
by_project_month = defaultdict(lambda: defaultdict(float))
total_hours = 0

for e in entries:
    duration_h = int(e.get("duration", 0)) / 3_600_000
    if duration_h <= 0:
        continue

    folder_id = e.get("task_location", {}).get("folder_id", "")
    project = folder_names.get(folder_id, f"Inconnu ({folder_id})")

    start_ms = int(e.get("start", 0))
    dt = datetime.fromtimestamp(start_ms / 1000)
    month_key = dt.strftime("%Y-%m")

    by_project[project] += duration_h
    by_project_month[project][month_key] += duration_h
    total_hours += duration_h

# Tri par heures décroissantes
sorted_projects = sorted(by_project.items(), key=lambda x: -x[1])
sorted_months = sorted({m for mp in by_project_month.values() for m in mp})

# Couleurs ANSI
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
COLORS = ["\033[94m", "\033[92m", "\033[93m", "\033[91m", "\033[95m", "\033[96m", "\033[97m"]

BAR_WIDTH = 40
max_hours = max(by_project.values()) if by_project else 1

# === HEADER ===
print()
print(f"{BOLD}{'='*75}{RESET}")
print(f"{BOLD}  👤 LUCAS COLIN - RÉPARTITION PAR PROJET (6 derniers mois){RESET}")
print(f"{BOLD}  📅 {sorted_months[0]} → {sorted_months[-1]}  |  Total : {total_hours:.1f}h{RESET}")
print(f"{BOLD}{'='*75}{RESET}")
print()

# === BAR CHART PAR PROJET ===
for i, (project, hours) in enumerate(sorted_projects):
    pct = (hours / total_hours * 100) if total_hours > 0 else 0
    bar_len = int((hours / max_hours) * BAR_WIDTH)
    color = COLORS[i % len(COLORS)]
    bar = "█" * bar_len + "░" * (BAR_WIDTH - bar_len)

    # Clean project name (remove emoji prefix for alignment)
    print(f"  {color}{bar}{RESET}  {BOLD}{hours:6.1f}h{RESET} ({pct:4.1f}%)  {project}")

print()
print(f"{BOLD}{'─'*75}{RESET}")

# === TABLEAU MENSUEL ===
print()
print(f"{BOLD}  📊 DÉTAIL MENSUEL PAR PROJET{RESET}")
print(f"{BOLD}{'─'*75}{RESET}")

# Header du tableau
month_labels = [datetime.strptime(m, "%Y-%m").strftime("%b %y") for m in sorted_months]
header = f"  {'Projet':<30}"
for ml in month_labels:
    header += f" {ml:>7}"
header += f" {'TOTAL':>7}"
print(f"{BOLD}{header}{RESET}")
print(f"  {'─'*30}" + "─" * (8 * len(sorted_months)) + "─" * 8)

for project, hours in sorted_projects:
    # Truncate project name
    name = project[:30].ljust(30)
    row = f"  {name}"
    for month in sorted_months:
        mh = by_project_month[project].get(month, 0)
        if mh > 0:
            row += f" {mh:6.1f}h"
        else:
            row += f" {'·':>7}"
    row += f" {BOLD}{hours:6.1f}h{RESET}"
    print(row)

# Totaux mensuels
print(f"  {'─'*30}" + "─" * (8 * len(sorted_months)) + "─" * 8)
total_row = f"  {BOLD}{'TOTAL':<30}{RESET}"
for month in sorted_months:
    month_total = sum(by_project_month[p].get(month, 0) for p in by_project)
    total_row += f" {BOLD}{month_total:6.1f}h{RESET}"
total_row += f" {BOLD}{total_hours:6.1f}h{RESET}"
print(total_row)

print()
print(f"{BOLD}{'='*75}{RESET}")
