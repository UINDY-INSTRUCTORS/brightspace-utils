"""Tests for group_attendance. Every name here is invented."""
import csv
import datetime as dt
import json
import zipfile

import pytest

import group_attendance as ga

CFG = {"first_day": "2026-09-02", "class_days": "MWF", "class_window": ["12:00", "15:00"],
       "no_class": ["2026-09-07"]}


@pytest.fixture
def cal():
    return ga.Calendar(CFG)


def test_parse_stamp_unpadded():
    assert ga.parse_stamp("Oct 14, 2026 147 PM") == dt.datetime(2026, 10, 14, 13, 47)
    assert ga.parse_stamp("Sep 28, 2026 1248 PM") == dt.datetime(2026, 9, 28, 12, 48)
    assert ga.parse_stamp("Oct 6, 2026 1200 AM") == dt.datetime(2026, 10, 6, 0, 0)


def test_calendar_skips_no_class_and_weekends(cal):
    assert [d.day for d in cal.days(dt.date(2026, 9, 11))] == [2, 4, 9, 11]


@pytest.mark.parametrize("name,expect", [
    ("Clickers and Problems 928", "2026-09-28"),
    ("Clickers and Problems 10-14", "2026-10-14"),
    ("ELO Lab Circular Motion (Flying Pig) 107", "2026-10-07"),
    ("Clickers 92", "2026-09-02"),
    ("Group Activity Oct 10 (Snowy Hill)", None),   # a Saturday: not a class day
    ("Clickers and Problems 96", None),              # 9/6 is a Sunday
])
def test_nominal_date(cal, name, expect):
    d = ga.nominal_date(name, cal)
    assert (d.isoformat() if d else None) == expect


def test_class_date_rules(cal):
    t = dt.datetime
    nom = dt.date(2026, 9, 30)
    # in class on the assignment's own day
    assert ga.class_date(t(2026, 9, 30, 13, 50), nom, cal)[0] == nom
    # in class on a day with no assignment of its own: that day's report, misfiled
    assert ga.class_date(t(2026, 10, 2, 13, 15), nom, cal, {nom})[0] == dt.date(2026, 10, 2)
    # in class on a day that has its own assignment: late report for the earlier day
    d, why = ga.class_date(t(2026, 10, 5, 12, 23), nom, cal, {nom, dt.date(2026, 10, 5)})
    assert d == nom and why.startswith("late")
    # evening of the same day, or the next morning: the assignment's day
    assert ga.class_date(t(2026, 9, 30, 19, 57), nom, cal)[0] == nom
    assert ga.class_date(t(2026, 10, 1, 9, 16), nom, cal)[0] == nom
    # no usable date in the name, outside class: most recent class
    assert ga.class_date(t(2026, 9, 8, 10, 33), None, cal)[0] == dt.date(2026, 9, 4)


def test_html_text_drops_markup():
    raw = "<p>Ann - Recorder<br>Bo&nbsp;- Captain&amp;Tech</p><style>p{}</style>"
    assert ga.html_text(raw) == "Ann - Recorder\nBo - Captain&Tech"


ROSTER = [
    ("Teams", "Red Team", "annr", "Ann", "Reed", "Sep 1, 2026 5:45 PM"),
    ("Teams", "Red Team", "bol", "Bo", "Lane", "Sep 1, 2026 5:45 PM"),
    ("Teams", "Red Team", "cyw", "Cy", "Webb", "Sep 9, 2026 4:00 PM"),   # joins after class 9/9
    ("Teams", "Blue Team", "dee", "Dee", "Ford", "Sep 1, 2026 5:45 PM"),
]


def write_roster(path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Group Category Name", "Group Name", "Group Code", "Username", "OrgDefinedId",
                    "First Name", "Last Name", "Email Address", "Group Enrollment Date"])
        for cat, team, u, first, last, when in ROSTER:
            w.writerow([cat, team, "g", u, "A0", first, last, f"{u}@example.edu", when])


def write_zip(path, entries):
    with zipfile.ZipFile(path, "w") as zf:
        for folder, fname, body in entries:
            zf.writestr(f"{folder}/{fname}", body)
        zf.writestr("index.html", "<html></html>")


def test_read_roster_join_dates(tmp_path, cal):
    write_roster(tmp_path / "teams.csv")
    r = ga.read_roster(tmp_path / "teams.csv", cal, {})
    assert r["cyw"]["joined"] == dt.date(2026, 9, 10)     # 4 PM is after the class window
    assert ga.read_roster(tmp_path / "teams.csv", cal, {"cyw": "2026-09-09"})["cyw"]["joined"] == dt.date(2026, 9, 9)


def test_scan_then_report(tmp_path):
    write_roster(tmp_path / "teams.csv")
    (tmp_path / "config.json").write_text(json.dumps(CFG))
    z = tmp_path / "Clickers and Problems 99 Download Sep 10, 2026 433 AM (Group Submission Folder).zip"
    write_zip(z, [
        ("1-5 - Red Team - Ann Reed - Sep 9, 2026 130 PM", "TextSubmission-x.html", "<p>Ann - Recorder</p>"),
        ("1-5 - Red Team - Bo Lane-Hart - Sep 9, 2026 900 PM", "photo.jpg", b"\xff\xd8"),
    ])
    common = ["--roster", str(tmp_path / "teams.csv"), "--config", str(tmp_path / "config.json"),
              "--roles", str(tmp_path / "roles.json")]
    ga.main(["scan", str(z), *common, "--work", str(tmp_path / "work")])

    roles = json.loads((tmp_path / "roles.json").read_text())
    assert list(roles) == ["Red Team|2026-09-09"]
    entry = roles["Red Team|2026-09-09"]
    assert entry["status"] == "pending" and len(entry["submissions"]) == 2
    todo = (tmp_path / "work" / "transcribe.md").read_text()
    assert "Ann - Recorder" in todo and "photo.jpg" in todo

    entry.update(status="done", present={"annr": "RT"}, absent_noted={"bol": "sick"})
    (tmp_path / "roles.json").write_text(json.dumps(roles))
    ga.main(["report", *common, "--work", str(tmp_path / "work"),
             "-o", str(tmp_path / "out.csv"), "--review", str(tmp_path / "review.md")])

    rows = {(r["username"], r["date"]): r for r in csv.DictReader(open(tmp_path / "out.csv"))}
    assert rows[("annr", "9/9")]["status"] == "present"
    assert rows[("annr", "9/9")]["roles"] == "Recorder / Technologist"
    assert rows[("bol", "9/9")]["status"] == "absent"
    assert rows[("cyw", "9/9")]["status"] == "n/a"
    assert rows[("dee", "9/9")]["status"] == "no report"
    review = (tmp_path / "review.md").read_text()
    assert "Bo: sick" in review and "9/9 Blue Team" in review

    # a later download with a new submission flips the entry to recheck
    write_zip(z, [
        ("1-5 - Red Team - Ann Reed - Sep 9, 2026 130 PM", "TextSubmission-x.html", "<p>Ann - Recorder</p>"),
        ("1-5 - Red Team - Bo Lane-Hart - Sep 9, 2026 900 PM", "photo.jpg", b"\xff\xd8"),
        ("1-5 - Red Team - Cy Webb - Sep 10, 2026 800 AM", "TextSubmission-y.html", "<p>late</p>"),
    ])
    ga.main(["scan", str(z), *common, "--work", str(tmp_path / "work")])
    assert json.loads((tmp_path / "roles.json").read_text())["Red Team|2026-09-09"]["status"] == "recheck"


def test_report_rejects_unknown_people(tmp_path):
    write_roster(tmp_path / "teams.csv")
    (tmp_path / "config.json").write_text(json.dumps(CFG))
    (tmp_path / "roles.json").write_text(json.dumps({"Red Team|2026-09-09": {
        "status": "done", "submissions": [], "present": {"nobody": "R"}, "absent_noted": {}, "notes": ""}}))
    with pytest.raises(SystemExit, match="nobody"):
        ga.main(["report", "--roster", str(tmp_path / "teams.csv"), "--config", str(tmp_path / "config.json"),
                 "--roles", str(tmp_path / "roles.json"), "-o", str(tmp_path / "o.csv")])


def test_multi_day_lab_borrows_the_other_days_report(cal):
    roster = {"areed": {"team": "Red Team", "name": "Ann Reed", "first": "Ann", "joined": dt.date(2026, 9, 2)},
              "bblue": {"team": "Blue Team", "name": "Bo Blue", "first": "Bo", "joined": dt.date(2026, 9, 2)}}
    done = lambda who: {"status": "done", "submissions": [], "present": who}
    roles = {"Red Team|2026-10-02": done({"areed": "C"}),
             "Blue Team|2026-09-30": done({}), "Blue Team|2026-10-02": done({"bblue": "R"})}
    days = [dt.date(2026, 9, 30), dt.date(2026, 10, 2), dt.date(2026, 10, 5)]
    blocks = ga.multi_day({"multi_day": [["2026-09-30", "2026-10-02"]]})
    got = {(r["username"], r["date"]): r["status"] for r in ga.statuses(roster, roles, cal, days, set(), blocks)}
    assert got[("areed", "9/30")] == "present"      # borrowed from 10/2
    assert got[("bblue", "9/30")] == "absent"       # Blue reported 9/30 itself; that report stands
    assert got[("areed", "10/5")] == "no report"    # outside the lab
    text = ga.review(ga.statuses(roster, roles, cal, days, set(), blocks), roles, {}, roster, days, blocks)
    assert "9/30 Red Team: from the 10/2 report" in text
