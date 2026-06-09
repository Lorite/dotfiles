#!/usr/bin/env python3
"""
Reproduce the user's two-note "GitHub issue -> Obsidian task" web-clipper pattern, headlessly,
from clean `gh` data (no browser, no Web Clipper extension needed).

It writes two notes that mirror clipper templates 20 (GitHub Issue) and 08 (TASK - GitHub Issue):

  Note A  media/github/github_issues/GitHub Issue - <owner> - <repo> - <title>.md   (type: github_issue)
  Note B  tasks/Solve GitHub Issue - <owner> - <repo> - <title>.md                  (type: task)

They embed each other exactly as the clipper templates do (A shows the issue body + embeds B's
journal/outcome; B embeds A's task description). Note B is a TaskNotes task, so mtn / the
TaskNotes plugin pick it up via its `task` tag and `tasks/` location.

Requires `gh` authenticated. Reads nothing secret. Usage:

  gh_to_tasknote.py --repo <owner/repo> --issue <N> [options]
    --vault <path>          default: ~/git/lorite-obsidian-notes
    --projects "<wl>||<wl>" '||'-separated wikilinks, e.g. "[[Conference Paper ...]]||[[PhD ...]]"
    --tags  t1,t2           EXTRA tags beyond the base set (e.g. a project tag)
    --priority <p>          TaskNotes priority for Note B (default: none)
    --due YYYY-MM-DD        optional date_due on Note B
    --scheduled YYYY-MM-DD  optional date_scheduled on Note B
    --dry-run               print what would be written, write nothing
"""
import argparse, json, os, re, subprocess, sys
from datetime import datetime
from pathlib import Path

BASE_TASK_TAGS = ["task", "work", "phd_novo_itu", "github", "github_issues"]
ISSUE_TAGS = ["media", "github", "github_issues"]


def gh_issue(repo, num):
    out = subprocess.run(
        ["gh", "issue", "view", str(num), "-R", repo, "--json",
         "number,title,body,author,url,createdAt,state,labels"],
        capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"gh failed: {out.stderr.strip()}")
    return json.loads(out.stdout)


def safe_name(s):
    """Filesystem-safe but readable, matching the clipper's safe_name spirit."""
    s = s.replace(":", " - ").replace("/", "-")
    s = re.sub(r'[\\*?"<>|]', "", s)          # strip illegal chars
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fmt_local(iso):
    """ISO 8601 (e.g. 2026-05-04T17:28:00Z) -> 'YYYY-MM-DDTHH:mm' to match existing notes."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%Y-%m-%dT%H:%M")
    except Exception:
        return datetime.now().strftime("%Y-%m-%dT%H:%M")


def yaml_list(items, indent="  "):
    return "".join(f"\n{indent}- {it}" for it in items)


def yq(s):
    """YAML-safe double-quoted scalar (values may contain ':', '[', '#', quotes)."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--issue", required=True)
    ap.add_argument("--vault", default=str(Path.home() / "git/lorite-obsidian-notes"))
    ap.add_argument("--projects", default="")
    ap.add_argument("--tags", default="")
    ap.add_argument("--priority", default="none")
    ap.add_argument("--due", default="")
    ap.add_argument("--scheduled", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    owner, repo = a.repo.split("/", 1)
    iss = gh_issue(a.repo, a.issue)
    title = safe_name(iss["title"])
    stem = f"{owner} - {repo} - {title}"            # shared suffix for both notes + embeds
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    created = fmt_local(iss.get("createdAt", ""))
    body = iss.get("body") or "_(no issue description)_"
    author = (iss.get("author") or {}).get("login", "")
    desc = re.sub(r"\s+", " ", body).strip()[:150]

    projects = [p.strip() for p in a.projects.split("||") if p.strip()]
    extra_tags = [t.strip() for t in a.tags.split(",") if t.strip()]
    repo_tag = f"github_repo_{safe_name(repo).replace('-', '_')}"
    issue_tags = ISSUE_TAGS + [repo_tag]
    task_tags = BASE_TASK_TAGS + [repo_tag] + extra_tags

    note_a_name = f"GitHub Issue - {stem}"
    note_b_name = f"Solve GitHub Issue - {stem}"

    # --- Note A: the clipped GitHub issue (type: github_issue) ---
    a_front = (
        "---\n"
        f"created: {now}\n"
        f"url: {iss.get('url','')}\n"
        f"title: {yq(title)}\n"
        f"opened_by: {yq(author)}\n"
        f"published: {created}\n"
        f"description: {yq(desc)}\n"
        f"tags:{yaml_list(issue_tags)}\n"
        f"github_repository: {repo}\n"
        f"github_user: {owner}\n"
        "is_completed: false\n"
        f"aliases:\n  - {yq(title)}\n"
        "type: github_issue\n"
        f"updated: {now}\n"
        "---\n"
    )
    a_body = (
        f"\n# 🎯 Task Description\n\n{body}\n\n"
        f"# 📓 Task Notes\n\n![[{note_b_name}#📓 Journal / Work Log]]\n\n"
        f"# ✅ Outcome & Learnings\n\n![[{note_b_name}#✅ Outcome & Learnings]]\n"
    )

    # --- Note B: the TaskNotes task (type: task) ---
    extra_dates = ""
    if a.due:
        extra_dates += f"date_due: {a.due}\n"
    if a.scheduled:
        extra_dates += f"date_scheduled: {a.scheduled}\n"
    b_front = (
        "---\n"
        "status: new\n"
        f"priority: {a.priority}\n"
        + (f"projects:{yaml_list([yq(p) for p in projects])}\n" if projects else "projects: []\n")
        + extra_dates
        + f"date_created: {created}\n"
        f"date_updated: {now}\n"
        f"tags:{yaml_list(task_tags)}\n"
        "type: task\n"
        f"created: {now}\n"
        f"updated: {now}\n"
        "---\n"
    )
    today = datetime.now().strftime("%Y-%m-%d")
    b_body = (
        f"\n# 🎯 Task Description\n\n![[{note_a_name}#🎯 Task Description]]\n\n"
        f"# 📓 Journal / Work Log\n\n## [[{today}]]\n\n- TODO\n\n"
        f"# ✅ Outcome & Learnings\n\n## Outcome\n\n- TODO\n\n## Learnings\n\n- TODO\n\n## Next Steps\n\n- TODO\n"
    )

    vault = Path(a.vault)
    path_a = vault / "media/github/github_issues" / f"{note_a_name}.md"
    path_b = vault / "tasks" / f"{note_b_name}.md"

    if a.dry_run:
        print(f"[dry-run] would write:\n  {path_a}\n  {path_b}\n")
        print("--- Note B frontmatter ---\n" + b_front)
        return

    for p, content in ((path_a, a_front + a_body), (path_b, b_front + b_body)):
        if p.exists():
            print(f"SKIP (exists): {p}")
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        print(f"WROTE: {p}")
    print(f"\nIssue #{iss['number']} ({iss.get('state','')}) -> task '{note_b_name}'.")


if __name__ == "__main__":
    main()
