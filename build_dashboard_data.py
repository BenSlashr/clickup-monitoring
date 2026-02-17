#!/usr/bin/env python3
"""
Transform all_tasks_raw.json (time estimates) into dashboard-ready data.js

Logic:
- Each task with time_estimate > 0 becomes one entry per assignee
- Date attribution: due_date > start_date > date_created
- Hours = time_estimate in hours (what was planned/allocated)
- Also includes time_spent for comparison
- Categorizes each task based on name/list/folder patterns
"""

import json
from datetime import datetime
from pathlib import Path

INPUT = Path("/Users/benoit/api-clickup/all_tasks_raw.json")
OUTPUT_JS = Path("/Users/benoit/api-clickup/data.js")
OUTPUT_JSON = Path("/Users/benoit/api-clickup/dashboard_data.json")
FOLDER_MAP = Path("/Users/benoit/api-clickup/folder_mapping_full.json")

MS_PER_HOUR = 3_600_000


def ms_to_date(ms_str):
    """Convert ms timestamp string to date info."""
    if not ms_str:
        return None
    try:
        ts = int(ms_str) / 1000
        dt = datetime.fromtimestamp(ts)
        return {
            "date": dt.strftime("%Y-%m-%d"),
            "month": dt.strftime("%Y-%m"),
            "week": dt.strftime("%Y-W%W"),
            "dt": dt,
        }
    except (ValueError, OSError):
        return None


def best_date(task):
    """Pick the most relevant date for a task's time allocation.
    Priority: due_date > start_date. Skip date_created to match
    ClickUp's planning views (only tasks with scheduled dates).
    """
    for field in ["due_date", "start_date"]:
        info = ms_to_date(task.get(field))
        if info:
            return info
    return None


def categorize(task):
    """Categorize a task based on name, list name and folder name patterns.

    IMPORTANT: 'formation' and 'wiki' are matched on task NAME only,
    not on folder/list names (folders like 'SLASHR Formation Interne'
    and 'SLASHR WIKI/Planning' contain all kinds of tasks).
    Séminaire, coaching, atelier = Accompagnement (client-facing).
    Formation = formation interne only.
    """
    name = (task.get("name") or "").lower()
    list_name = (task.get("list_name") or "").lower()
    folder_name = (task.get("folder_name") or "").lower()
    combined = name + " " + list_name + " " + folder_name

    # 1. Conges / Absences
    if any(k in combined for k in [
        "congé", "conge", "férié", "ferie", "absence",
        "jour férié", "amicale", "maladie", "arrêt de travail", "arrêt"
    ]):
        return "Conges / Absences"
    if name.strip() in ("cp", "férié"):
        return "Conges / Absences"

    # 2. Commercial / Avant-vente
    if any(k in combined for k in [
        "avant vente", "avant-vente", "fid", "fidé",
        "prospect", "commercial", "prise de besoin"
    ]):
        return "Commercial / Avant-vente"
    if folder_name.strip() == "avant vente":
        return "Commercial / Avant-vente"

    # 3. Accompagnement SEO (includes client-facing: séminaire, coaching, atelier)
    if any(k in combined for k in [
        "accompagnement", "régie", "temps accompagnement",
        "séminaire", "seminaire", "coaching", "atelier",
        "prépa séminaire", "préparation séminaire"
    ]):
        return "Accompagnement SEO"
    if "planification lucas" in list_name:
        return "Accompagnement SEO"

    # 4. Formation interne (task NAME only - not folder/list)
    if any(k in name for k in [
        "formation", "wiki ", "wiki-", "tuto",
        "webinair", "webinar", "veille seo", "veille rattrapage"
    ]):
        return "Formation"
    # Wiki at start of task name
    if name.strip().startswith("wiki"):
        return "Formation"

    # 5. Etude lexicale / Benchmark
    if any(k in combined for k in [
        "lexicale", "lex/bench", "étude lex", "etude lex",
        "benchmark", "bench concu", "mots clés", "mots-clés"
    ]):
        return "Etude lexicale"

    # 6. Audit (but not "restitution" which is a meeting)
    if "restitution" in name:
        return "Reunion / Call / Email"
    if any(k in combined for k in ["audit"]):
        return "Audit"

    # 7. Redaction / Contenu
    if any(k in combined for k in [
        "rédaction", "redaction", "contenu", "article", "texte", "spin"
    ]):
        return "Redaction / Contenu"

    # 8. Netlinking
    if any(k in combined for k in [
        "netlinking", "backlink", "affiliation", "vente de lien"
    ]):
        return "Netlinking"

    # 9. Maillage interne
    if any(k in combined for k in ["maillage"]):
        return "Maillage interne"

    # 10. Brief / Roadmap / Strategie
    if any(k in combined for k in [
        "brief", "roadmap", "strateg", "lancement",
        "kick off", "kickoff", "kick-off", "discover"
    ]):
        return "Brief / Roadmap / Strategie"

    # 11. Technique
    if any(k in combined for k in [
        "technique", "crawl", "migration", "indexation", "search console",
        "sitemap", "core web", "pagespeed", "vitesse", "recette", "preprod",
        "préprod", "mep", "mise en prod", "redirection", "implémentation",
        "implementation", "uat", "prelaunch", "pre-launch", "ct seo",
        "excel de reco", "amoa", "maquette", "refonte", "gsc", "install"
    ]):
        return "Technique"

    # 12. Reporting / Analytics
    if any(k in combined for k in [
        "reporting", "analytics", "matomo", "dashboard", "rapport",
        "scoring", "pulse scoring", "chiffres", "kpi"
    ]):
        return "Reporting / Analytics"

    # 13. Reunion / Call / Email
    if any(k in combined for k in [
        "réunion", "reunion", "call", "email", "mail", "échange",
        "echange", "point projet", "point équipe", "point client",
        "point hebdo", "point mensuel", "point du lundi", "points projets",
        "point orga", "point netlinking", "point tool",
        "restitution", "relance", "message", "retour", "discussion",
        "debrief", "visio", "prez", "prépa réunion",
        "bonsoir", "copil", "entretien"
    ]):
        return "Reunion / Call / Email"

    # 14. Gestion / Planning / Admin
    if any(k in combined for k in [
        "planning", "gestion", "pilotage", "orga", "clickup",
        "rétroplanning", "facture", "devis", "admin", "ré-orga",
        "linkedin", "pinterest", "youtube", "visuels", "style",
        "panning", "pllaning", "forecast", "fiche de poste",
        "accueil", "déménagement", "afterwork", "repas"
    ]):
        return "Gestion / Planning"

    # 15. Operationnel client
    if any(k in combined for k in [
        "commande cuve", "cuve expert", "cuve-expert",
        "sites d'édition", "youdrone"
    ]):
        return "Operationnel client"

    return "Autre"


DEFAULT_TJM = 690


def build_project_budgets(tasks, folder_names):
    """Extract budget data from INFOS GLOBALES tasks.

    Returns a dict keyed by folder_id with aggregated budget info.
    """
    # Collect per-list budget data from INFOS GLOBALES tasks
    list_budgets = {}
    for task in tasks:
        if "infos globales" not in (task.get("name") or "").lower():
            continue
        cf = task.get("custom_fields", {})
        if not cf:
            continue
        budget = cf.get("budget")
        temps_vendu = cf.get("temps_vendu_jours")
        if budget is None and temps_vendu is None:
            continue
        list_id = task.get("list_id")
        folder_id = task.get("folder_id")
        if not folder_id:
            continue
        list_budgets[list_id] = {
            "folder_id": str(folder_id),
            "list_id": str(list_id) if list_id else "",
            "list_name": task.get("list_name", ""),
            "budget": float(budget) if budget else 0,
            "temps_vendu_jours": float(temps_vendu) if temps_vendu else 0,
            "type_prestation": cf.get("type_prestation", ""),
            "date_debut": cf.get("date_debut"),
            "date_fin": cf.get("date_fin"),
        }

    # Aggregate per folder (project)
    folder_budgets = {}
    for lb in list_budgets.values():
        fid = lb["folder_id"]
        if fid not in folder_budgets:
            fname = folder_names.get(fid, "")
            folder_budgets[fid] = {
                "folder_id": fid,
                "folder_name": fname,
                "budget": 0,
                "temps_vendu_jours": 0,
                "prestations": [],
            }
        folder_budgets[fid]["budget"] += lb["budget"]
        folder_budgets[fid]["temps_vendu_jours"] += lb["temps_vendu_jours"]
        # Convert ms timestamps to ISO dates
        date_debut_iso = None
        date_fin_iso = None
        if lb.get("date_debut"):
            try:
                date_debut_iso = datetime.fromtimestamp(int(lb["date_debut"]) / 1000).strftime("%Y-%m-%d")
            except (ValueError, OSError):
                pass
        if lb.get("date_fin"):
            try:
                date_fin_iso = datetime.fromtimestamp(int(lb["date_fin"]) / 1000).strftime("%Y-%m-%d")
            except (ValueError, OSError):
                pass

        folder_budgets[fid]["prestations"].append({
            "list_name": lb["list_name"],
            "budget": lb["budget"],
            "temps_vendu_jours": lb["temps_vendu_jours"],
            "type_prestation": lb["type_prestation"],
            "date_debut": date_debut_iso,
            "date_fin": date_fin_iso,
        })

    # Compute TJM per folder
    for fb in folder_budgets.values():
        if fb["temps_vendu_jours"] > 0 and fb["budget"] > 0:
            fb["tjm"] = round(fb["budget"] / fb["temps_vendu_jours"], 2)
        else:
            fb["tjm"] = DEFAULT_TJM
        fb["budget"] = round(fb["budget"], 2)
        fb["temps_vendu_jours"] = round(fb["temps_vendu_jours"], 2)

    return folder_budgets


def main():
    with open(INPUT) as f:
        tasks = json.load(f)

    # Load folder mapping for better names
    with open(FOLDER_MAP) as f:
        folder_names = json.load(f)

    # Build project budgets from INFOS GLOBALES
    project_budgets = build_project_budgets(tasks, folder_names)
    print(f"Project budgets found: {len(project_budgets)} projects")
    total_budget = sum(fb["budget"] for fb in project_budgets.values())
    print(f"Total budget: {total_budget:,.0f} EUR")

    entries = []
    skipped_no_estimate = 0
    skipped_no_date = 0
    skipped_no_assignee = 0

    for task in tasks:
        est_ms = task.get("time_estimate", 0) or 0
        if est_ms <= 0:
            skipped_no_estimate += 1
            continue

        date_info = best_date(task)
        if not date_info:
            skipped_no_date += 1
            continue

        assignees = task.get("assignees", [])
        if not assignees:
            skipped_no_assignee += 1
            continue

        est_hours = round(est_ms / MS_PER_HOUR, 2)
        spent_hours = round((task.get("time_spent", 0) or 0) / MS_PER_HOUR, 2)

        # Resolve folder name
        folder_id = task.get("folder_id", "")
        folder_name = task.get("folder_name", "")
        if folder_id and str(folder_id) in folder_names:
            folder_name = folder_names[str(folder_id)]

        # Determine task status
        status = task.get("status", "")
        is_closed = task.get("date_closed") is not None

        # Categorize
        category = categorize(task)

        # ClickUp assigns full estimate to each assignee (no split)
        for assignee in assignees:
            username = assignee.get("username") or assignee.get("email") or str(assignee.get("id"))

            entries.append({
                "user": username,
                "user_id": assignee.get("id"),
                "project": folder_name or "(sans dossier)",
                "folder_id": str(folder_id) if folder_id else "",
                "list_name": task.get("list_name", ""),
                "task": task.get("name", ""),
                "task_id": task.get("id", ""),
                "hours": est_hours,
                "spent_hours": spent_hours,
                "date": date_info["date"],
                "month": date_info["month"],
                "week": date_info["week"],
                "status": status,
                "closed": is_closed,
                "category": category,
                "source": "time_estimate",
            })

    # Sort by date
    entries.sort(key=lambda e: e["date"])

    # Stats
    users = {}
    cats = {}
    for e in entries:
        if e["user"] not in users:
            users[e["user"]] = {"hours": 0, "tasks": 0}
        users[e["user"]]["hours"] += e["hours"]
        users[e["user"]]["tasks"] += 1
        cats[e["category"]] = cats.get(e["category"], 0) + e["hours"]

    print(f"Total entries: {len(entries)}")
    print(f"Skipped: no estimate={skipped_no_estimate}, no date={skipped_no_date}, no assignee={skipped_no_assignee}")
    print(f"\nPer user:")
    for user, stats in sorted(users.items(), key=lambda x: -x[1]["hours"]):
        print(f"  {user}: {stats['hours']:.1f}h ({stats['tasks']} entries)")
    print(f"\nPer category:")
    for cat, hours in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {hours:.0f}h")

    # Build budget lookup by folder_name for JS
    budgets_by_name = {}
    for fb in project_budgets.values():
        name = fb["folder_name"]
        if name:
            budgets_by_name[name] = {
                "budget": fb["budget"],
                "temps_vendu_jours": fb["temps_vendu_jours"],
                "tjm": fb["tjm"],
                "prestations": fb["prestations"],
            }

    # Save JSON
    with open(OUTPUT_JSON, "w") as f:
        json.dump({"entries": entries, "project_budgets": budgets_by_name}, f, indent=2, ensure_ascii=True)
    print(f"\nSaved {OUTPUT_JSON}")

    # Save JS (for dashboard)
    with open(OUTPUT_JS, "w") as f:
        f.write("const RAW_DATA = ")
        json.dump(entries, f, ensure_ascii=True)
        f.write(";\n")
        f.write("const PROJECT_BUDGETS = ")
        json.dump(budgets_by_name, f, ensure_ascii=True)
        f.write(";\n")
    print(f"Saved {OUTPUT_JS}")
    print(f"Budget data for {len(budgets_by_name)} projects included")


if __name__ == "__main__":
    main()
