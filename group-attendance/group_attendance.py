#!/usr/bin/env python3
"""
Attendance and team roles from Brightspace group-submission downloads.

Each class, one member of every team (the recorder) submits a short report that
lists who was present and in which role. This tool turns the downloaded zips of
those reports into one attendance CSV and a short list of things to check.

Workflow:
    # 1. Index the zips: work out which class day each submission belongs to,
    #    extract the text, and add an entry to the roles file for each new
    #    (team, day) that still needs its roles read.
    uv run group-attendance/group_attendance.py scan *.zip \
        --roster Teams_AllGroups.csv --config config.json \
        --roles roles.json --work extracted/

    # 2. Read the reports and fill in the pending entries in roles.json
    #    (by hand, or in a Claude Code session; transcribe.md lists them).

    # 3. Build the attendance CSV and the review list.
    uv run group-attendance/group_attendance.py report \
        --roster Teams_AllGroups.csv --config config.json --roles roles.json \
        -o attendance-roles.csv --review review.md

Reading the roles is the one step that is not automated: they arrive as free
text in every format ("Captain ; Ch. Rec ; me. Spok ; Dc"), as photos and as
PDFs, and need judgment.

⚠️ Every file this tool reads or writes holds student names. Keep them outside
this repo (it is public).
"""

import argparse
import collections
import csv
import datetime as dt
import html
import json
import re
import sys
import zipfile
from pathlib import Path

ROLE_CODES = {"C": "Captain", "R": "Recorder", "S": "Spokesperson",
              "T": "Technologist", "F": "Reflector", "O": "Other"}

# A group-submission folder, as Brightspace names it (Sep-Oct 2026 downloads):
#   12345-193786 - Red Team - Ann Reed - Oct 14, 2026 147 PM
#   <group id>-<assignment id> - <team> - <submitter> - <timestamp>
FOLDER = re.compile(
    r"^(?P<group>\d+)-(?P<assignment>\d+) - (?P<team>.+) - (?P<submitter>.+?) - "
    r"(?P<stamp>[A-Z][a-z]{2} \d{1,2}, \d{4} \d{3,4} [AP]M)$")
# No zero-padding and no colon: "Oct 14, 2026 147 PM", "Sep 28, 2026 1248 PM".
STAMP = re.compile(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4}) (\d{1,2})(\d{2}) ([AP]M)")
MONTHS = {m: i for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1)}

TEXT_EXT = {".html", ".htm", ".txt"}
READABLE_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".heic", ".gif", ".webp"}


# ─── Dates ──────────────────────────────────────────────────────────────────────

def parse_stamp(s: str) -> dt.datetime:
    m = STAMP.search(s)
    if not m:
        raise ValueError(f"not a Brightspace timestamp: {s!r}")
    mon, day, year, hour, minute, ampm = m.groups()
    h = int(hour) % 12 + (12 if ampm == "PM" else 0)
    return dt.datetime(int(year), MONTHS[mon], int(day), h, int(minute))


class Calendar:
    """Class meetings: given weekdays from first_day, minus no-class dates."""

    def __init__(self, cfg: dict):
        self.first = dt.date.fromisoformat(cfg["first_day"])
        self.last = dt.date.fromisoformat(cfg["last_day"]) if cfg.get("last_day") else None
        self.weekdays = {"MTWRFSU".index(c) for c in cfg.get("class_days", "MWF")}
        self.no_class = {dt.date.fromisoformat(d) for d in cfg.get("no_class", [])}
        start, end = cfg.get("class_window", ["12:00", "15:00"])
        self.window = (dt.time.fromisoformat(start), dt.time.fromisoformat(end))

    def is_class_day(self, d: dt.date) -> bool:
        return (d >= self.first and (self.last is None or d <= self.last)
                and d.weekday() in self.weekdays and d not in self.no_class)

    def days(self, through: dt.date) -> list[dt.date]:
        out, d = [], self.first
        while d <= through:
            if self.is_class_day(d):
                out.append(d)
            d += dt.timedelta(days=1)
        return out

    def in_class(self, t: dt.datetime) -> bool:
        return self.is_class_day(t.date()) and self.window[0] <= t.time() <= self.window[1]

    def latest_on_or_before(self, d: dt.date) -> dt.date | None:
        while d >= self.first:
            if self.is_class_day(d):
                return d
            d -= dt.timedelta(days=1)
        return None


def nominal_date(assignment: str, cal: Calendar) -> dt.date | None:
    """The class day an assignment's name points at, if it names a real one.

    Names seen: "Clickers and Problems 928", "... 10-14", "ELO Lab ... 107",
    "Group Activity Oct 10 (Snowy Hill)". Bare digits are ambiguous ("107" is
    10/7 or 1/07), so only a reading that lands on a class day counts — which
    also rejects a typo like "Oct 10" for a Saturday.
    """
    year = cal.first.year
    cands = []
    for m in re.finditer(r"\b(\d{1,2})[-/](\d{1,2})\b", assignment):
        cands.append((int(m[1]), int(m[2])))
    for m in re.finditer(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2})\b",
                         assignment):
        cands.append((MONTHS[m[1]], int(m[2])))
    if not cands:
        for m in re.finditer(r"\b(\d{2,4})\b", assignment):
            s = m[1]
            cands += [(int(s[:i]), int(s[i:])) for i in (1, 2) if i < len(s)]
    for mon, day in cands:
        try:
            d = dt.date(year, mon, day)
        except ValueError:
            continue
        if cal.is_class_day(d):
            return d
    return None


def class_date(submitted: dt.datetime, nominal: dt.date | None, cal: Calendar,
               assigned_days: set[dt.date] = frozenset()) -> tuple[dt.date | None, str]:
    """Which class a report describes, and why.

    A report submitted during class time describes that class, whatever
    assignment it was filed under, when that class had no assignment of its
    own: teams then file under the last one (ELO 9/30 holds the 10/2 reports).
    When the class did have its own assignment, a report filed under an
    earlier one is a late report for the earlier day, submitted at the start
    of the next class. Anything submitted outside class belongs to the
    assignment's own day, or failing that, to the most recent class before it.
    """
    d = submitted.date()
    if cal.in_class(submitted):
        if d == nominal:
            return d, "in class"
        if not (nominal and nominal < d and d in assigned_days):
            return d, "in class, filed under another day"
        return nominal, "late, submitted during a later class"
    if nominal and nominal <= d:
        return nominal, "late" if d > nominal else "after class"
    return cal.latest_on_or_before(d), "no date in the assignment name; most recent class"


# ─── Zips ───────────────────────────────────────────────────────────────────────

def html_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw)).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def assignment_name(zip_path: Path) -> str:
    return re.split(r" Download [A-Z][a-z]{2} \d", zip_path.stem)[0]


def read_zip(zip_path: Path, work: Path, cal: Calendar) -> list[dict]:
    """One record per submission folder; attachments are extracted under work/."""
    name = assignment_name(zip_path)
    nominal = nominal_date(name, cal)
    subs = {}
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir() or "/" not in info.filename:
                continue
            folder, fname = info.filename.split("/", 1)
            m = FOLDER.match(folder)
            if not m:
                raise ValueError(f"{zip_path.name}: unexpected folder name {folder!r}")
            when = parse_stamp(m["stamp"])
            rec = subs.setdefault(folder, {
                "folder": folder, "assignment": name, "assignment_id": m["assignment"],
                "team": m["team"], "submitter": m["submitter"],
                "submitted": when.isoformat(timespec="minutes"),
                "nominal": nominal.isoformat() if nominal else None,
                "text": "", "files": [], "unread": []})
            ext = Path(fname).suffix.lower()
            if ext in TEXT_EXT:
                rec["text"] += html_text(zf.read(info).decode("utf-8", "replace")) + "\n"
            else:
                dest = work / zip_path.stem / folder / fname
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(info))
                (rec["files"] if ext in READABLE_EXT else rec["unread"]).append(str(dest))
    for rec in subs.values():
        rec["text"] = rec["text"].strip()
    return sorted(subs.values(), key=lambda r: (r["team"], r["submitted"]))


# ─── Roster and roles ───────────────────────────────────────────────────────────

def read_roster(path: Path, cal: Calendar, joined_override: dict) -> dict[str, dict]:
    """username -> {team, name, first, joined}. Brightspace 'Teams' group export."""
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("Group Category Name", "Teams") != "Teams":
                continue
            u = r["Username"]
            joined = cal.first
            if r.get("Group Enrollment Date"):
                t = dt.datetime.strptime(r["Group Enrollment Date"], "%b %d, %Y %I:%M %p")
                joined = t.date() if t.time() <= cal.window[1] else t.date() + dt.timedelta(days=1)
            if u in joined_override:
                joined = dt.date.fromisoformat(joined_override[u])
            out[u] = {"team": r["Group Name"], "name": f'{r["First Name"]} {r["Last Name"]}',
                      "first": r["First Name"], "joined": joined}
    if not out:
        raise SystemExit(f"{path}: no Teams rows found")
    return out


def load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def key(team: str, date: str) -> str:
    return f"{team}|{date}"


def scan(args) -> None:
    cfg = load_json(args.config, None) or sys.exit(f"{args.config}: missing")
    cal = Calendar(cfg)
    roster = read_roster(args.roster, cal, cfg.get("joined", {}))
    roles = load_json(args.roles, {})
    subs = [s for z in args.zips for s in read_zip(Path(z), args.work, cal)]
    assigned = {dt.date.fromisoformat(s["nominal"]) for s in subs if s["nominal"]}
    reassign = cfg.get("reassign", {})
    for s in subs:
        if s["folder"] in reassign:
            s["date"], s["why"] = reassign[s["folder"]]["date"], "reassigned: " + reassign[s["folder"]]["why"]
            continue
        d, s["why"] = class_date(dt.datetime.fromisoformat(s["submitted"]),
                                 dt.date.fromisoformat(s["nominal"]) if s["nominal"] else None,
                                 cal, assigned)
        s["date"] = d.isoformat() if d else None
    teams = {p["team"] for p in roster.values()}

    groups = collections.defaultdict(list)
    for s in subs:
        if s["team"] not in teams:
            print(f"⚠️  {s['team']!r} is not a team in the roster; skipped", file=sys.stderr)
            continue
        if s["date"]:
            groups[key(s["team"], s["date"])].append(s)

    here = {s["folder"]: key(s["team"], s["date"]) for s in subs if s["date"]}
    for k, e in roles.items():
        moved = [f for f in e["submissions"] if f in here and here[f] != k]
        if moved:
            e["submissions"] = [f for f in e["submissions"] if f not in moved]
            if e["status"] == "done" and not e.get("locked"):
                e["status"] = "recheck"
    for k in [k for k, e in roles.items() if not e["submissions"] and not e.get("locked")]:
        del roles[k]          # every submission it held now counts for another day
    new, changed = 0, 0
    for k, ss in sorted(groups.items()):
        folders = sorted(s["folder"] for s in ss)
        entry = roles.get(k)
        if entry is None:
            roles[k] = {"status": "pending", "submissions": folders, "present": {},
                        "absent_noted": {}, "notes": ""}
            new += 1
        elif sorted(entry.get("submissions", [])) != folders:
            entry["submissions"] = sorted(set(entry.get("submissions", [])) | set(folders))
            if entry["status"] == "done" and not entry.get("locked"):
                entry["status"] = "recheck"
            changed += 1

    args.roles.write_text(json.dumps(roles, indent=1, ensure_ascii=False) + "\n")
    index = args.work / "submissions.json"
    old = {s["folder"]: s for s in load_json(index, [])}
    old.update({s["folder"]: s for s in subs})
    index.write_text(json.dumps(sorted(old.values(), key=lambda s: (s["date"] or "", s["team"])),
                                indent=1, ensure_ascii=False) + "\n")
    write_transcribe_list(args.work / "transcribe.md", roles, old, roster)
    print(f"{len(subs)} submissions in {len(args.zips)} zips; {new} new team-days, "
          f"{changed} with new submissions. To read: {args.work / 'transcribe.md'}")


def write_transcribe_list(path: Path, roles: dict, subs: dict, roster: dict) -> None:
    """Everything a reader needs to fill in the pending entries, in one file."""
    members = collections.defaultdict(list)
    for u, p in roster.items():
        members[p["team"]].append(f"{u} = {p['name']}")
    out = ["# Reports to transcribe", "",
           "Fill `present` with username -> role codes (" +
           ", ".join(f"{c} {n}" for c, n in ROLE_CODES.items()) +
           "), e.g. `\"annr\": \"RT\"`. A member the report says was away goes in "
           "`absent_noted` with the reason. Set `roles_omitted: true` if the report "
           "lists no roles at all. Then set `status` to `done`.", ""]
    todo = [k for k, e in sorted(roles.items(), key=lambda kv: kv[0].split("|")[::-1])
            if e["status"] in ("pending", "recheck")]
    if not todo:
        out.append("Nothing pending.")
    for k in todo:
        team, date = k.split("|")
        out += [f"## {date} — {team} ({roles[k]['status']})", "",
                "Members: " + "; ".join(sorted(members[team])), ""]
        for folder in roles[k]["submissions"]:
            s = subs.get(folder)
            if not s:
                out += [f"- {folder}: not in this scan", ""]
                continue
            out += [f"### {s['submitter']}, {s['submitted'].replace('T', ' ')} "
                    f"({s['assignment']}; {s['why']})", ""]
            out += ["```", s["text"] or "(no text)", "```", ""]
            out += [f"- read: `{f}`" for f in s["files"]]
            out += [f"- not readable here: `{f}`" for f in s["unread"]]
            out.append("")
    path.write_text("\n".join(out) + "\n")


# ─── Report ─────────────────────────────────────────────────────────────────────

def multi_day(cfg: dict) -> dict[str, list[str]]:
    """Each day of a multi-day lab -> every day of that lab."""
    return {d: block for block in cfg.get("multi_day", []) for d in block}


def entry_for(roles: dict, team: str, iso: str, blocks: dict) -> tuple[dict | None, str | None]:
    """The team's report for a day, or else the one from another day of the same lab.
    Returns (entry, the day it came from if not this one)."""
    if (e := roles.get(key(team, iso))) is not None:
        return e, None
    for other in blocks.get(iso, []):
        if other != iso and (e := roles.get(key(team, other))) is not None:
            return e, other
    return None, None


def statuses(roster: dict, roles: dict, cal: Calendar, days: list[dt.date], excused: set,
             blocks: dict | None = None) -> list[dict]:
    rows = []
    for u, p in sorted(roster.items(), key=lambda kv: (kv[1]["team"], kv[1]["name"])):
        for d in days:
            iso = d.isoformat()
            e, _ = entry_for(roles, p["team"], iso, blocks or {})
            codes = ""
            if d < p["joined"]:
                st = "n/a"
            elif (u, iso) in excused:
                st = "excused"
            elif e is None:
                st = "no report"
            elif e["status"] != "done":
                st = "pending"
            elif e.get("roles_omitted"):
                st = "unknown"
            elif u in e["present"]:
                st, codes = "present", e["present"][u]
            else:
                st = "absent"
            rows.append({"team": p["team"], "username": u, "name": p["name"],
                         "date": f"{d.month}/{d.day}", "status": st,
                         "roles": " / ".join(ROLE_CODES[c] for c in codes)})
    return rows


def report(args) -> None:
    cfg = load_json(args.config, None) or sys.exit(f"{args.config}: missing")
    cal = Calendar(cfg)
    roster = read_roster(args.roster, cal, cfg.get("joined", {}))
    roles = load_json(args.roles, {})
    subs = {s["folder"]: s for s in load_json(args.work / "submissions.json", [])} if args.work else {}
    excused = {(e["username"], e["date"]) for e in cfg.get("excused", [])}

    bad = [(k, u) for k, e in roles.items() for u in list(e["present"]) + list(e.get("absent_noted", {}))
           if u not in roster]
    if bad:
        sys.exit("roles.json names people who are not in the roster: " +
                 ", ".join(f"{u} ({k})" for k, u in bad))
    for k, e in roles.items():
        for u, codes in e["present"].items():
            if set(codes) - set(ROLE_CODES):
                sys.exit(f"{k}: {u} has unknown role code(s) {codes!r}")

    dated = [dt.date.fromisoformat(k.split("|")[1]) for k in roles]
    through = dt.date.fromisoformat(args.through) if args.through else max(dated, default=cal.first)
    days = cal.days(through)
    blocks = multi_day(cfg)
    rows = statuses(roster, roles, cal, days, excused, blocks)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["team", "username", "name", "date", "status", "roles"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {args.output}: {len(rows)} rows, {len(roster)} students x {len(days)} class days")
    if args.review:
        args.review.write_text(review(rows, roles, subs, roster, days, blocks))
        print(f"wrote {args.review}")


def review(rows, roles, subs, roster, days, blocks=None) -> str:
    blocks = blocks or {}
    teams = sorted({p["team"] for p in roster.values()})
    out = ["# Attendance review", ""]

    tally = collections.Counter(r["status"] for r in rows)
    out += ["Status counts: " + ", ".join(f"{n} {s}" for s, n in tally.most_common()), ""]

    nothing = [d for d in days if not any(key(t, d.isoformat()) in roles for t in teams)]
    if nothing:
        out += ["## Class days with no reports from any team", "",
                "No submissions were scanned for these days. Either there was no team report "
                "(test, lab without a report, cancelled class) or its zip hasn't been downloaded "
                "yet. Add the date to `no_class` in config.json if there was no class.", ""]
        out += [f"- {d:%a %-m/%-d}" for d in nothing] + [""]

    gaps = [(d, t, entry_for(roles, t, d.isoformat(), blocks)[1]) for d in days if d not in nothing
            for t in teams if key(t, d.isoformat()) not in roles]
    missing = [(d, t) for d, t, via in gaps if via is None]
    if missing:
        out += ["## Teams with no report", ""]
        out += [f"- {d:%-m/%-d} {t}" for d, t in missing] + [""]
    covered = [(d, t, via) for d, t, via in gaps if via]
    if covered:
        out += ["## Covered by the other day of a multi-day lab", "",
                "The team sent one report for the lab; it counts for both days.", ""]
        out += [f"- {d:%-m/%-d} {t}: from the {dt.date.fromisoformat(via):%-m/%-d} report"
                for d, t, via in covered] + [""]

    open_ = [k for k, e in roles.items() if e["status"] != "done"]
    if open_:
        out += ["## Not yet transcribed", ""] + [f"- {k.replace('|', ' ')}" for k in sorted(open_)] + [""]

    moved = [s for k, e in roles.items() for f in e["submissions"] if (s := subs.get(f))
             and s["why"] not in ("in class", "after class")]
    if moved:
        out += ["## Submissions placed by rule", "",
                "Each was counted for the day shown. Check any that look wrong.", "",
                "| counted for | team | submitter | submitted | filed under | why |", "|---|---|---|---|---|---|"]
        for s in sorted(moved, key=lambda s: (s["date"], s["team"])):
            out.append(f"| {s['date']} | {s['team']} | {s['submitter']} | {s['submitted'].replace('T', ' ')} "
                       f"| {s['assignment']} | {s['why']} |")
        out.append("")

    notes = [(k, e) for k, e in sorted(roles.items(), key=lambda kv: kv[0].split("|")[::-1])
             if e.get("notes") or e.get("absent_noted") or e.get("roles_omitted")]
    if notes:
        out += ["## Notes from transcription", ""]
        for k, e in notes:
            team, date = k.split("|")
            bits = [f"{roster[u]['first']}: {why}" for u, why in e.get("absent_noted", {}).items()]
            if e.get("roles_omitted"):
                bits.append("Report lists no roles, so attendance is unknown")
            if e.get("notes"):
                bits.append(e["notes"])
            out.append(f"- **{date} {team}.** " + " ".join(b.rstrip(".") + "." for b in bits))
        out.append("")

    absent = collections.Counter(r["username"] for r in rows if r["status"] == "absent")
    if absent:
        out += ["## Absences per student", ""]
        out += [f"- {roster[u]['name']} ({roster[u]['team']}): {n}" for u, n in absent.most_common()] + [""]
    return "\n".join(out)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--roster", type=Path, required=True, help="Brightspace Teams group export (CSV)")
        p.add_argument("--config", type=Path, required=True, help="calendar and exceptions (JSON)")
        p.add_argument("--roles", type=Path, required=True, help="transcribed roles (JSON, created if missing)")

    s = sub.add_parser("scan", help="index the zips and queue new team-days for transcription")
    s.add_argument("zips", nargs="+")
    common(s)
    s.add_argument("--work", type=Path, required=True, help="where to extract attachments")
    s.set_defaults(func=scan)

    r = sub.add_parser("report", help="attendance CSV and review list")
    common(r)
    r.add_argument("--work", type=Path, help="scan's work directory, for submission details in the review")
    r.add_argument("-o", "--output", type=Path, required=True)
    r.add_argument("--review", type=Path)
    r.add_argument("--through", help="last class day to include (YYYY-MM-DD); default: latest transcribed")
    r.set_defaults(func=report)

    args = ap.parse_args(argv)
    if getattr(args, "work", None):
        args.work.mkdir(parents=True, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
