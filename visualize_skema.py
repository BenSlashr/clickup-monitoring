#!/usr/bin/env python3
"""Visualisation du temps passé sur le projet SKEMA - par mois et par personne."""

import json
from datetime import datetime
from collections import defaultdict

# Charger les données
with open("/Users/benoit/api-clickup/skema_time_entries.json") as f:
    data = json.load(f)

entries = data.get("data", [])

# Agrégation par mois
by_month = defaultdict(float)
by_month_person = defaultdict(lambda: defaultdict(float))
by_person_total = defaultdict(float)

for e in entries:
    duration_h = int(e.get("duration", 0)) / 3_600_000
    start_ms = int(e.get("start", 0))
    user = e.get("user", {}).get("username", "Inconnu")

    if duration_h <= 0:
        continue

    dt = datetime.fromtimestamp(start_ms / 1000)
    month_key = dt.strftime("%Y-%m")

    by_month[month_key] += duration_h
    by_month_person[month_key][user] += duration_h
    by_person_total[user] += duration_h

# Tri des mois
sorted_months = sorted(by_month.keys())

# Couleurs ANSI
COLORS = [
    "\033[94m",  # Bleu
    "\033[92m",  # Vert
    "\033[93m",  # Jaune
    "\033[91m",  # Rouge
    "\033[95m",  # Magenta
    "\033[96m",  # Cyan
    "\033[97m",  # Blanc
]
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Mapping couleur par personne
all_persons = sorted(by_person_total.keys(), key=lambda p: -by_person_total[p])
person_color = {p: COLORS[i % len(COLORS)] for i, p in enumerate(all_persons)}

# Header
print()
print(f"{BOLD}{'='*70}{RESET}")
print(f"{BOLD}  ⏱️  TEMPS PASSÉ SUR SKEMA - PAR MOIS{RESET}")
print(f"{BOLD}{'='*70}{RESET}")
print()

# Bar chart par mois
max_hours = max(by_month.values()) if by_month else 1
BAR_WIDTH = 40

for month in sorted_months:
    hours = by_month[month]
    bar_len = int((hours / max_hours) * BAR_WIDTH)
    bar = "█" * bar_len + "░" * (BAR_WIDTH - bar_len)

    # Format mois lisible
    dt = datetime.strptime(month, "%Y-%m")
    month_label = dt.strftime("%b %Y")

    print(f"  {BOLD}{month_label:>8}{RESET}  {bar}  {BOLD}{hours:6.1f}h{RESET}")

    # Détail par personne
    persons_in_month = sorted(
        by_month_person[month].items(),
        key=lambda x: -x[1]
    )
    for person, ph in persons_in_month:
        color = person_color[person]
        person_bar_len = int((ph / max_hours) * BAR_WIDTH)
        person_bar = "▓" * person_bar_len
        print(f"  {'':>8}  {color}{person_bar} {person}: {ph:.1f}h{RESET}")
    print()

# Total
total_hours = sum(by_month.values())
print(f"{BOLD}{'─'*70}{RESET}")
print(f"  {BOLD}TOTAL : {total_hours:.1f}h{RESET}")
print()

# Résumé par personne
print(f"{BOLD}{'='*70}{RESET}")
print(f"{BOLD}  👥 RÉPARTITION PAR PERSONNE{RESET}")
print(f"{BOLD}{'='*70}{RESET}")
print()

for person in all_persons:
    hours = by_person_total[person]
    pct = (hours / total_hours * 100) if total_hours > 0 else 0
    bar_len = int((hours / max(by_person_total.values())) * BAR_WIDTH)
    color = person_color[person]
    bar = "█" * bar_len
    print(f"  {color}{person:>25}{RESET}  {color}{bar} {hours:.1f}h ({pct:.0f}%){RESET}")

print()
print(f"{BOLD}{'='*70}{RESET}")
