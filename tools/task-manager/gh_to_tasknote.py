#!/usr/bin/env python3
"""
Reproduce the user's two-note "GitHub issue -> Obsidian task" web-clipper pattern, headlessly,
from clean `gh` data (no browser, no Web Clipper extension needed).

It writes two notes from the REAL Web Clipper templates, rendered with Knap:

  "GitHub Issue"        -> media/github/github_issues/GitHub Issue - <owner> - <repo> - <title>.md
  "TASK - GitHub Issue" -> tasks/Solve GitHub Issue - <owner> - <repo> - <title>.md

They embed each other exactly as the templates say, because they ARE the templates. Note B is
a TaskNotes task, so mtn / the TaskNotes plugin pick it up via its `task` tag and `tasks/`
location.

This used to hand-maintain a Python copy of both templates' note shape, which then drifted
from the templates it was copied from. Since Obsidian published Knap (the template engine
behind Web Clipper) the rendering half can be reused directly, so editing a template in the
extension now changes this tool's output too. Re-export after editing:

  ~/git/dotfiles/tools/lorite/obsidian-clipper/export-templates.py

The page fields the templates scrape with `{{selector:...}}` are supplied here from the `gh`
API response instead, under those exact variable names.

Requires `gh` authenticated, node, and the exported templates. Reads nothing secret. Usage:

  gh_to_tasknote.py --repo <owner/repo> --issue <N> [options]
    --vault <path>          default: ~/git/lorite-obsidian-notes
    --projects "<wl>||<wl>" '||'-separated wikilinks, e.g. "[[Conference Paper ...]]||[[PhD ...]]"
    --tags  t1,t2           EXTRA tags beyond the template's own
    --priority <p>          TaskNotes priority for the task note (default: none)
    --due YYYY-MM-DD        optional date_due on the task note
    --scheduled YYYY-MM-DD  optional date_scheduled on the task note
    --dry-run               print what would be written, write nothing
"""
import argparse, json, os, re, subprocess, sys
from datetime import datetime
from pathlib import Path

CLIPPER_CONFIG = Path.home() / ".config/obsidian-clipper-cli"
TEMPLATE_DIR = CLIPPER_CONFIG / "templates"
PROPERTY_TYPES = CLIPPER_CONFIG / "property-types.json"
RENDERER = Path.home() / "git/dotfiles/tools/lorite/obsidian-clipper/render-template.mjs"

ISSUE_TEMPLATE = "GitHub Issue"
TASK_TEMPLATE = "TASK - GitHub Issue"

# The two page fields the templates scrape. Knap looks variables up by their full name, so
# these keys resolve the template's {{selector:...}} expressions from `gh` data.
SEL_AUTHOR = 'selector:[data-testid="issue-body-header-author"]'
SEL_PUBLISHED = "selector:relative-time?datetime"


def gh_issue(repo, num):
    out = subprocess.run(
        ["gh", "issue", "view", str(num), "-R", repo, "--json",
         "number,title,body,author,url,createdAt,state,labels"],
        capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"gh failed: {out.stderr.strip()}")
    return json.loads(out.stdout)


def load_template(name):
    """Find an exported template by its NAME. Filenames carry a list-order prefix that moves
    whenever templates are reordered in the extension, so they are not a stable handle."""
    if not TEMPLATE_DIR.is_dir():
        sys.exit(f"No exported templates at {TEMPLATE_DIR}. Run export-templates.py first.")
    for path in sorted(TEMPLATE_DIR.glob("*.json")):
        tpl = json.loads(path.read_text())
        if tpl.get("name") == name:
            return tpl
    sys.exit(f"No template named {name!r} in {TEMPLATE_DIR}")


def property_types():
    if not PROPERTY_TYPES.is_file():
        return {}
    return {e["name"]: e.get("type", "text") for e in json.loads(PROPERTY_TYPES.read_text())}


def render(template, variables, types):
    if not os.access(RENDERER, os.X_OK):
        sys.exit(f"Renderer not executable: {RENDERER}")
    payload = json.dumps({"template": template, "variables": variables, "propertyTypes": types})
    out = subprocess.run([str(RENDERER)], input=payload, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"render-template.mjs failed: {out.stderr.strip()}")
    result = json.loads(out.stdout)
    for err in result.get("errors", []):
        print(f"WARNING: template error: {err}", file=sys.stderr)
    return result


def set_property(template, name, value, ptype="text", after=None):
    """Apply a CLI override to the template before rendering, so there is still a single
    render pass and the frontmatter is generated in exactly one place."""
    props = template.setdefault("properties", [])
    for p in props:
        if p.get("name") == name:
            p["value"] = value
            return
    entry = {"name": name, "value": value, "type": ptype}
    if after:
        for i, p in enumerate(props):
            if p.get("name") == after:
                props.insert(i + 1, entry)
                return
    props.append(entry)


def append_to_property(template, name, extra):
    for p in template.get("properties", []):
        if p.get("name") == name:
            p["value"] = f"{p['value']}, {extra}" if p.get("value") else extra
            return


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
    body = iss.get("body") or "_(no issue description)_"

    # The templates parse GitHub's own page title ("<title> · Issue #N · <owner>/<repo>") with
    # split:"·" to recover the repo, owner and issue title, so hand them that exact shape.
    variables = {
        "title": f"{iss['title']} · Issue #{iss['number']} · {owner}/{repo}",
        "url": iss.get("url", ""),
        "content": body,
        "description": re.sub(r"\s+", " ", body).strip()[:150],
        "time": datetime.now().astimezone().isoformat(),
        SEL_AUTHOR: (iss.get("author") or {}).get("login", ""),
        SEL_PUBLISHED: iss.get("createdAt", ""),
    }

    types = property_types()
    issue_tpl = load_template(ISSUE_TEMPLATE)
    task_tpl = load_template(TASK_TEMPLATE)

    # CLI overrides. The template carries the defaults; these replace or extend them.
    set_property(task_tpl, "priority", a.priority)
    projects = [p.strip() for p in a.projects.split("||") if p.strip()]
    if projects:
        set_property(task_tpl, "projects", ", ".join(projects), "multitext")
    # Inserted scheduled-then-due because each lands directly after `projects`, so the
    # second insert ends up first. This keeps the due/scheduled order the notes already use.
    if a.scheduled:
        set_property(task_tpl, "date_scheduled", a.scheduled, "date", after="projects")
    if a.due:
        set_property(task_tpl, "date_due", a.due, "date", after="projects")
    extra_tags = [t.strip() for t in a.tags.split(",") if t.strip()]
    if extra_tags:
        append_to_property(task_tpl, "tags", ", ".join(extra_tags))

    issue_note = render(issue_tpl, variables, types)
    task_note = render(task_tpl, variables, types)

    vault = Path(a.vault)
    targets = []
    for note in (issue_note, task_note):
        path = vault / note["path"] / f"{note['noteName']}.md"
        targets.append((path, note["frontmatter"] + note["content"]))

    if a.dry_run:
        print("[dry-run] would write:")
        for path, _ in targets:
            print(f"  {path}")
        print()
        for path, content in targets:
            print(f"--- {path.name} ---\n{content}")
        return

    for path, content in targets:
        if path.exists():
            print(f"SKIP (exists): {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        print(f"WROTE: {path}")
    print(f"\nIssue #{iss['number']} ({iss.get('state','')}) -> task '{task_note['noteName']}'.")


if __name__ == "__main__":
    main()
