# group-attendance

Attendance and team roles from Brightspace **group-submission** downloads. Each class, one member
of every team submits a short report listing who was there and in which role; this tool turns
the downloaded zips into one attendance CSV and a list of things to check.

Reading the roles is the one step that is not automated. They arrive as free text in every
format ("Captain ; Ch. Rec ; me. Spok ; Dc"), as photos and as PDFs, and need judgment, so
`scan` gathers everything that needs reading into one file and a person (or a Claude Code
session) fills in `roles.json`.

## Workflow

```bash
# 1. Download each assignment's submissions from Brightspace (Select all -> Download).
#    Also export the Teams group category (Groups -> Export) for the roster.

# 2. Index the zips. Safe to re-run on every zip each time: team-days already read are kept.
uv run group-attendance/group_attendance.py scan *.zip \
    --roster Teams_AllGroups.csv --config config.json --roles roles.json --work ~/.cache/ga

# 3. Read ~/.cache/ga/transcribe.md and fill in each pending entry in roles.json.

# 4. Build the CSV and the review list.
uv run group-attendance/group_attendance.py report \
    --roster Teams_AllGroups.csv --config config.json --roles roles.json --work ~/.cache/ga \
    -o attendance-roles.csv --review review.md
```

## Which day a submission counts for

Assignment names don't reliably say: students file under whatever assignment is open, the names
are typed by hand ("96" for 9/4, "Oct 10" for a Saturday), and reports arrive late. `scan`
decides like this, and the review lists every submission it placed by rule:

1. **Submitted during class** (a class day, inside `class_window`):
   - on the assignment's own day: that day;
   - on a day with **no assignment of its own** (a lab's second day, an unnamed activity): that
     day, filed under an older assignment;
   - on a day that **has** its own assignment, but filed under an earlier one: a late report for
     the earlier day, submitted at the start of the next class.
2. **Submitted outside class**: the assignment's own day, or if its name gives no class day, the
   most recent class before the submission.
3. **`reassign`** in the config overrides both for one submission folder.

## Files

All of these hold student names. Keep them outside this repo (it is public).

| File | What |
|---|---|
| `config.json` | Calendar and exceptions (below). Written by hand. |
| `roles.json` | One entry per team and class day: `status` (`pending`, `done`, `recheck`), the submission folders it came from, `present` (username → role codes), `absent_noted` (username → reason), `roles_omitted`, `notes`. `locked: true` keeps an entry from flipping to `recheck` when its zip is re-scanned. |
| `<work>/transcribe.md` | Everything pending, with the report text inline and the paths of attached photos and PDFs |
| `<work>/submissions.json` | Every scanned submission and the day it was counted for |

Role codes: `C` Captain, `R` Recorder, `S` Spokesperson, `T` Technologist, `F` Reflector,
`O` Other (note-taker, no role). Several codes for one person are fine (`"RT"`); an empty string
means present with no role given.

### config.json

```json
{
 "first_day": "2026-09-02",
 "class_days": "MWF",
 "class_window": ["12:00", "15:00"],
 "no_class": ["2026-09-07", "2026-10-19"],
 "joined": {"username": "2026-09-09"},
 "excused": [{"username": "username", "date": "2026-09-25", "why": "..."}],
 "reassign": {"<submission folder name>": {"date": "2026-10-02", "why": "..."}},
 "multi_day": [["2026-09-30", "2026-10-02"]]
}
```

`multi_day` lists labs that ran over several class days. A team that sent one report for the lab
is counted from it on the days it has no report of its own; a day it did report stands as reported.

`joined` overrides the Teams export's group enrollment date when the reports show a student
present earlier. Someone who joins after the class window counts from the next class.

## Statuses in the CSV

A class day on which no team submitted anything is left out of the CSV: with no assignment there
was no class or no in-class activity, so there is nothing to take attendance from. The review
lists those days.

`present` (with roles), `absent` (team reported, student not listed), `no report` (team sent
nothing for that day, or for any day of a multi-day lab), `unknown` (report had no roles), `excused`, `pending` (not yet read),
`n/a` (before the student joined the team).
