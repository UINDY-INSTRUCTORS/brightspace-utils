#!/usr/bin/env python3
"""
Build a Brightspace bulk-feedback upload: one folder per student, named the way
Brightspace names submission folders, so a zip of them attaches each student's
feedback file to the right submission.

Workflow:
    # 1. Save the course Classlist page from Brightspace as HTML, then:
    uv run folder-feedback/folder_feedback.py roster classlist.html -o roster.csv

    # 2. Make the empty per-student folders for an assignment:
    uv run folder-feedback/folder_feedback.py folders --assignment-id 192268 --roster roster.csv

    # 3. Drop each student's feedback file into their folder, then:
    uv run folder-feedback/folder_feedback.py pack upload-192268

⚠️ roster.csv and the upload folders contain student names and IDs. Both are
gitignored in this repo; don't move them somewhere that isn't.
"""

import argparse
import csv
import datetime
import re
import sys
import zipfile
from pathlib import Path

ROSTER_FIELDS = ["brightspace_user_id", "username", "org_defined_id", "full_name"]

# The Classlist grid: each row's checkbox carries the full name (aria-label) and the
# Brightspace user id (value="i<n>_<userid>"); the next two cells are username and
# org-defined id.
CLASSLIST_ROW = re.compile(
    r'aria-label="Select\s+(.*?)"\s+name="gridUsers_cb"\s+value="i\d+_(\d+)"'
    r'.*?<td class="d_gn"><label>(.*?)</label></td>'
    r'\s*<td class="d_gn"><label>(.*?)</label></td>',
    re.DOTALL,
)

# e.g. "Sep 26, 2026 0741 PM"
TIMESTAMP_FORMAT = "%b %d, %Y %I%M %p"


def parse_classlist(html: str) -> list[dict]:
    """Roster rows from a saved Brightspace Classlist page, de-duplicated by user id."""
    roster, seen = [], set()
    for full_name, user_id, username, org_id in CLASSLIST_ROW.findall(html):
        if user_id in seen:
            continue
        seen.add(user_id)
        roster.append({
            "brightspace_user_id": user_id.strip(),
            "username": username.strip(),
            "org_defined_id": org_id.strip(),
            "full_name": " ".join(full_name.split()),
        })
    return roster


def read_roster(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = set(ROSTER_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is missing column(s): {', '.join(sorted(missing))} "
                             f"- make it with the 'roster' subcommand")
        return list(reader)


def folder_name(student: dict, assignment_id: str, timestamp: str) -> str:
    """[UserID]-[AssignmentID] - [Full Name] - [Timestamp]"""
    name = re.sub(r'[/\\:]', '-', student["full_name"])  # keep it a single path component
    return f"{student['brightspace_user_id']}-{assignment_id} - {name} - {timestamp}"


def cmd_roster(args) -> int:
    html = args.classlist.read_text(encoding="utf-8", errors="ignore")
    roster = parse_classlist(html)
    if not roster:
        print(f"❌ No students found in {args.classlist}. Save the Classlist page itself "
              "(not a print view) - or Brightspace has changed its markup.", file=sys.stderr)
        return 1
    if args.exclude:
        roster = [r for r in roster if r["username"] not in args.exclude]

    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ROSTER_FIELDS)
        writer.writeheader()
        writer.writerows(roster)
    print(f"✅ {len(roster)} students -> {args.output}")
    return 0


def cmd_folders(args) -> int:
    roster = read_roster(args.roster)
    if args.exclude:
        roster = [r for r in roster if r["username"] not in args.exclude]
    out = args.output or Path(f"upload-{args.assignment_id}")
    timestamp = args.timestamp or datetime.datetime.now().strftime(TIMESTAMP_FORMAT)

    if out.exists() and any(out.iterdir()) and not args.force:
        print(f"❌ {out} already exists and isn't empty. Use --force to add to it.", file=sys.stderr)
        return 1

    for student in roster:
        path = out / folder_name(student, args.assignment_id, timestamp)
        if args.dry_run:
            print(f"  would create: {path.name}")
        else:
            path.mkdir(parents=True, exist_ok=True)
            if args.verbose:
                print(f"  created: {path.name}")

    verb = "Would create" if args.dry_run else "Created"
    print(f"✅ {verb} {len(roster)} folders in {out}/ (timestamp '{timestamp}')")
    if not args.dry_run:
        print(f"   Next: drop each student's feedback file into their folder, then "
              f"run: pack {out}")
    return 0


def cmd_pack(args) -> int:
    src = args.folder
    if not src.is_dir():
        print(f"❌ Not a directory: {src}", file=sys.stderr)
        return 1
    student_dirs = sorted(p for p in src.iterdir() if p.is_dir())
    filled = [d for d in student_dirs if any(f.is_file() for f in d.iterdir())]
    empty = [d for d in student_dirs if d not in filled]

    if not filled:
        print(f"❌ Every folder in {src} is empty - nothing to upload.", file=sys.stderr)
        return 1

    out = args.output or src.with_suffix(".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d in filled:
            for f in sorted(d.iterdir()):
                if f.is_file() and not f.name.startswith("."):
                    z.write(f, f"{d.name}/{f.name}")

    print(f"✅ {len(filled)} students packed -> {out}")
    if empty:
        print(f"⚠️  {len(empty)} folder(s) had no feedback and were left out:")
        for d in empty:
            print(f"     {d.name}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a Brightspace bulk-feedback upload, one folder per student.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Workflow:")[1],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("roster", help="Extract the roster from a saved Brightspace Classlist page")
    p.add_argument("classlist", type=Path, help="Classlist page saved as HTML")
    p.add_argument("-o", "--output", type=Path, default=Path("roster.csv"),
                   help="Roster CSV to write (default: roster.csv)")
    p.add_argument("--exclude", action="append", metavar="USERNAME",
                   help="Leave out this username, e.g. yourself or a TA (repeatable)")
    p.set_defaults(func=cmd_roster)

    p = sub.add_parser("folders", help="Create one empty feedback folder per student")
    p.add_argument("-a", "--assignment-id", required=True,
                   help="Brightspace assignment (dropbox folder) id, e.g. 192268 - "
                        "the db= value in the assignment's URL")
    p.add_argument("-r", "--roster", type=Path, default=Path("roster.csv"),
                   help="Roster CSV from the 'roster' subcommand (default: roster.csv)")
    p.add_argument("-o", "--output", type=Path,
                   help="Directory to create folders in (default: upload-<assignment-id>)")
    p.add_argument("--timestamp",
                   help=f"Timestamp to put in folder names (default: now, as "
                        f"'{datetime.datetime(2026, 9, 26, 19, 41).strftime(TIMESTAMP_FORMAT)}'). "
                        "Copy it from a real Brightspace submission download if uploads don't match.")
    p.add_argument("--exclude", action="append", metavar="USERNAME",
                   help="Skip this username (repeatable)")
    p.add_argument("-n", "--dry-run", action="store_true", help="Show what would be created")
    p.add_argument("-f", "--force", action="store_true",
                   help="Add to an output directory that already has content")
    p.add_argument("-v", "--verbose", action="store_true", help="List each folder created")
    p.set_defaults(func=cmd_folders)

    p = sub.add_parser("pack", help="Zip the filled folders for upload, skipping empty ones")
    p.add_argument("folder", type=Path, help="Directory made by the 'folders' subcommand")
    p.add_argument("-o", "--output", type=Path, help="Zip to write (default: <folder>.zip)")
    p.set_defaults(func=cmd_pack)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError) as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
