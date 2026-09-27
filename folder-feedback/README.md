# folder-feedback

Build a Brightspace bulk-feedback upload: one folder per student, named the way Brightspace
names submission folders, so uploading a zip of them attaches each student's feedback file to
the right submission.

> **Status: idea, not yet verified against a real upload.** The folder-name format below is
> the working hypothesis. Before relying on it, download one assignment's submissions from
> Brightspace and compare its folder names — if they differ, `--timestamp` covers the date
> part; anything else is a one-line change in `folder_name()`.

## Workflow

```bash
# 1. In Brightspace: Classlist -> save the page as HTML (File > Save Page As, "HTML only")
uv run folder-feedback/folder_feedback.py roster classlist.html -o roster.csv

# 2. Empty per-student folders for one assignment
uv run folder-feedback/folder_feedback.py folders --assignment-id 192268 -r roster.csv

# 3. Drop each student's feedback file into their folder, then zip the non-empty ones
uv run folder-feedback/folder_feedback.py pack upload-192268
```

Upload `upload-192268.zip` from the assignment's submissions page.

## Subcommands

| Command | Does | Key options |
|---|---|---|
| `roster CLASSLIST` | Classlist HTML → `roster.csv` (user id, username, org id, name, role), de-duplicated. Keeps **Learners** only by default | `-o`, `--role PREFIX`, `--all-roles`, `--exclude USERNAME` |
| `folders` | One empty folder per roster student | `-a/--assignment-id` (required), `-r`, `-o`, `--timestamp`, `--exclude`, `-n/--dry-run`, `-f/--force` |
| `pack DIR` | Zip the folders that contain a file; lists the empty ones it skipped | `-o` |

The **assignment id** is the `db=` value in the assignment's URL.

**Roles.** `roster` reads each person's role from the Classlist and keeps those starting with
`Learner` — which includes `Learner - (Incomplete)`, so check those. Instructors are dropped
without needing `--exclude`. It prints what it kept and skipped by role.

Folder name format:

```
<brightspace_user_id>-<assignment_id> - <Full Name> - <Mon D, YYYY HMM AM>
```

For comparison, a real **group** submission download (Sep 2026) names folders

```
95869-192899 - Earth, Wind, and Fire - Leah Price - Sep 25, 2026 141 PM
<group_id>-<assignment_id> - <Group Name> - <Submitter> - <timestamp>
```

## Guards

- `roster` parses the Classlist **row by row**, so one odd row can't bleed into the next, and
  decodes HTML entities (`O&#39;Brien` → `O'Brien`). It fails if it finds nobody, or if the
  role filter leaves nobody, rather than writing an empty CSV.
- `folders` refuses to add to a non-empty output directory without `--force`, and rejects a
  roster CSV that doesn't have the expected columns.
- `pack` leaves out empty folders and dotfiles (`.DS_Store`), and fails if every folder is empty.

## ⚠️ Student data

`roster.csv`, `classlist*.html`, the `upload-*/` folders and the zip all carry student names and
IDs. They are gitignored here — this repo is public. The tests use a synthetic classlist
(`tests/fixtures/classlist-fake.html`) with invented people.
