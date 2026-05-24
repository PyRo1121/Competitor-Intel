#!/usr/bin/env python3
"""
Sync git commits on main to Linear issue state.

Requires LINEAR_API_KEY. Config: .github/linear.config.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ci_paths import MONOREPO_ROOT

CONFIG_PATH = MONOREPO_ROOT / ".github" / "linear.config.json"
GRAPHQL_URL = "https://api.linear.app/graphql"

CLOSE_RE = re.compile(
    r"(?i)\b(?:fixes|fixed|fix|closes|closed|close|resolves|resolved|resolve|"
    r"completes|completed|complete)\s+((?:COM-\d+)(?:\s*,\s*COM-\d+)*)"
)
IDENT_RE = re.compile(r"\bCOM-(\d+)\b", re.IGNORECASE)
SUBJECT_DONE_RE = re.compile(
    r"^COM-(\d+)\s*:\s*.+(?:\[(?:done|closes)\]|\((?:done|closes)\)|#done)\s*$",
    re.IGNORECASE | re.DOTALL,
)


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def gql(api_key: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"query": query}
    if variables is not None:
        body["variables"] = variables
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"Linear HTTP {e.code}: {detail[:500]}") from e
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    return payload["data"]


def parse_close_identifiers(message: str) -> list[str]:
    """Return COM-NNN identifiers that should move to Done."""
    text = message.strip()
    if not text:
        return []

    found: list[str] = []
    seen: set[str] = set()

    for match in CLOSE_RE.finditer(text):
        for part in re.split(r"\s*,\s*", match.group(1)):
            ident = part.strip().upper()
            if ident.startswith("COM-") and ident not in seen:
                seen.add(ident)
                found.append(ident)

    if SUBJECT_DONE_RE.match(text.splitlines()[0] if text else ""):
        m = re.match(r"^COM-(\d+)\s*:", text, re.IGNORECASE)
        if m:
            ident = f"COM-{m.group(1)}"
            if ident not in seen:
                found.append(ident)

    return found


def resolve_issue_uuid(api_key: str, identifier: str, team_id: str) -> str | None:
    number = int(identifier.split("-", 1)[1])
    data = gql(
        api_key,
        """
        query($teamId: ID!, $number: Float!) {
          issues(
            first: 1
            filter: {
              team: { id: { eq: $teamId } }
              number: { eq: $number }
            }
          ) {
            nodes { id identifier }
          }
        }
        """,
        {"teamId": team_id, "number": float(number)},
    )
    nodes = data["issues"]["nodes"]
    if not nodes:
        return None
    node = nodes[0]
    if node["identifier"].upper() != identifier.upper():
        return None
    return node["id"]


def label_id_by_name(api_key: str, team_id: str, name: str) -> str | None:
    data = gql(
        api_key,
        """
        query($id: String!, $name: String!) {
          team(id: $id) {
            labels(filter: { name: { eq: $name } }) { nodes { id name } }
          }
        }
        """,
        {"id": team_id, "name": name},
    )
    nodes = data["team"]["labels"]["nodes"]
    return nodes[0]["id"] if nodes else None


def mark_done(
    api_key: str,
    issue_uuid: str,
    done_state_id: str,
    *,
    dry_run: bool,
    auto_closed_label_id: str | None = None,
) -> bool:
    if dry_run:
        return True
    input_obj: dict[str, Any] = {"stateId": done_state_id}
    if auto_closed_label_id:
        input_obj["addedLabelIds"] = [auto_closed_label_id]
    data = gql(
        api_key,
        """
        mutation($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue { identifier state { name } }
          }
        }
        """,
        {"id": issue_uuid, "input": input_obj},
    )
    return bool(data["issueUpdate"]["success"])


def add_comment(
    api_key: str,
    issue_uuid: str,
    body: str,
    *,
    dry_run: bool,
) -> None:
    if dry_run:
        return
    gql(
        api_key,
        """
        mutation($input: CommentCreateInput!) {
          commentCreate(input: $input) { success }
        }
        """,
        {"input": {"issueId": issue_uuid, "body": body}},
    )


def process_commit(
    api_key: str,
    config: dict[str, Any],
    sha: str,
    subject: str,
    body: str,
    *,
    dry_run: bool,
    link_only: bool,
    auto_closed_label_id: str | None = None,
) -> list[str]:
    message = subject if not body else f"{subject}\n\n{body}"
    team_id = config["teamId"]
    done_state_id = config["workflowStates"]["done"]
    actions: list[str] = []

    to_close = parse_close_identifiers(message)
    refs = list(dict.fromkeys(IDENT_RE.findall(message)))
    all_idents = {f"COM-{n}" for n in refs}
    for ident in to_close:
        all_idents.add(ident)

    for ident in sorted(all_idents):
        issue_uuid = resolve_issue_uuid(api_key, ident, team_id)
        if not issue_uuid:
            actions.append(f"skip {ident}: not found")
            continue

        if ident in to_close:
            ok = mark_done(
                api_key,
                issue_uuid,
                done_state_id,
                dry_run=dry_run,
                auto_closed_label_id=auto_closed_label_id,
            )
            verb = "would close" if dry_run else "closed"
            actions.append(f"{verb} {ident}" if ok else f"failed close {ident}")
        elif link_only and sha:
            short = sha[:7]
            comment = f"Linked from commit `{short}`: {subject[:200]}"
            add_comment(api_key, issue_uuid, comment, dry_run=dry_run)
            verb = "would link" if dry_run else "linked"
            actions.append(f"{verb} {ident} ({short})")

    return actions


def read_commits_from_stdin() -> list[tuple[str, str, str]]:
    commits: list[tuple[str, str, str]] = []
    for line in sys.stdin:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        sha = parts[0] if parts else ""
        subject = parts[1] if len(parts) > 1 else ""
        body = parts[2] if len(parts) > 2 else ""
        commits.append((sha, subject, body))
    return commits


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync commits to Linear")
    parser.add_argument("--dry-run", action="store_true", help="Print actions only")
    parser.add_argument(
        "--link-only",
        action="store_true",
        help="Comment on COM-NNN refs without close keywords (off by default)",
    )
    parser.add_argument("--message", help="Single message test (no stdin)")
    args = parser.parse_args()

    api_key = os.environ.get("LINEAR_API_KEY", "").strip()
    if not api_key:
        print("LINEAR_API_KEY not set; skipping", file=sys.stderr)
        return 0

    config = load_config()
    dry_run = args.dry_run
    auto_label_id = label_id_by_name(api_key, config["teamId"], "ci:auto-closed")

    if args.message:
        actions = process_commit(
            api_key,
            config,
            "local",
            args.message,
            "",
            dry_run=dry_run,
            link_only=False,
            auto_closed_label_id=auto_label_id,
        )
        for a in actions:
            print(a)
        return 0

    commits = read_commits_from_stdin()
    if not commits:
        print("No commits on stdin", file=sys.stderr)
        return 0

    exit_code = 0
    for sha, subject, body in commits:
        actions = process_commit(
            api_key,
            config,
            sha,
            subject,
            body,
            dry_run=dry_run,
            link_only=args.link_only,
            auto_closed_label_id=auto_label_id,
        )
        if actions:
            print(f"commit {sha[:7]}: {subject[:72]}")
            for a in actions:
                print(f"  {a}")
        else:
            refs = IDENT_RE.findall(f"{subject}\n{body}")
            if refs and not args.link_only:
                print(f"commit {sha[:7]}: refs COM-{','.join(refs)} (no close keyword)")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
