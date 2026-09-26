"""folder_feedback CLI, end to end, against a synthetic classlist."""

import csv
import zipfile
from pathlib import Path

from folder_feedback import main, parse_classlist, folder_name

FIXTURES = Path(__file__).parent / "fixtures"
TS = "Sep 26, 2026 741 PM"


def make_roster(tmp_path, *extra):
    roster = tmp_path / "roster.csv"
    assert main(["roster", str(FIXTURES / "classlist-fake.html"), "-o", str(roster), *extra]) == 0
    return roster


def test_parse_classlist_dedupes_and_normalises_names():
    roster = parse_classlist((FIXTURES / "classlist-fake.html").read_text())
    assert [r["brightspace_user_id"] for r in roster] == ["90001", "90002", "90003"]
    assert roster[1] == {"brightspace_user_id": "90002", "username": "hopperg",
                         "org_defined_id": "A00000002", "full_name": "Grace Hopper"}


def test_roster_exclude(tmp_path):
    roster = make_roster(tmp_path, "--exclude", "turinga")
    with roster.open() as f:
        assert [r["username"] for r in csv.DictReader(f)] == ["lovelacea", "hopperg"]


def test_roster_with_no_students_fails(tmp_path):
    bad = tmp_path / "bad.html"
    bad.write_text("<html>nothing here</html>")
    assert main(["roster", str(bad), "-o", str(tmp_path / "r.csv")]) == 1
    assert not (tmp_path / "r.csv").exists()


def test_folder_name_format():
    student = {"brightspace_user_id": "90001", "full_name": "Ada Lovelace"}
    assert folder_name(student, "192268", TS) == "90001-192268 - Ada Lovelace - Sep 26, 2026 741 PM"


def test_folders_created(tmp_path):
    roster = make_roster(tmp_path)
    out = tmp_path / "up"
    assert main(["folders", "-a", "192268", "-r", str(roster), "-o", str(out), "--timestamp", TS]) == 0
    assert sorted(p.name for p in out.iterdir()) == [
        "90001-192268 - Ada Lovelace - Sep 26, 2026 741 PM",
        "90002-192268 - Grace Hopper - Sep 26, 2026 741 PM",
        "90003-192268 - Alan Turing - Sep 26, 2026 741 PM",
    ]


def test_folders_dry_run_creates_nothing(tmp_path):
    roster = make_roster(tmp_path)
    out = tmp_path / "up"
    assert main(["folders", "-a", "1", "-r", str(roster), "-o", str(out), "-n"]) == 0
    assert not out.exists()


def test_folders_refuses_non_empty_dir_without_force(tmp_path):
    roster = make_roster(tmp_path)
    out = tmp_path / "up"
    args = ["folders", "-a", "1", "-r", str(roster), "-o", str(out), "--timestamp", TS]
    assert main(args) == 0
    assert main(args) == 1
    assert main(args + ["--force"]) == 0


def test_folders_rejects_wrong_roster_columns(tmp_path):
    roster = tmp_path / "roster.csv"
    roster.write_text("UserID,FirstName,LastName\n1,Ada,Lovelace\n")
    assert main(["folders", "-a", "1", "-r", str(roster), "-o", str(tmp_path / "up")]) == 1


def test_pack_skips_empty_folders(tmp_path):
    roster = make_roster(tmp_path)
    out = tmp_path / "up"
    main(["folders", "-a", "192268", "-r", str(roster), "-o", str(out), "--timestamp", TS])
    ada, grace, _ = sorted(out.iterdir())
    (ada / "feedback.pdf").write_bytes(b"%PDF fake")
    (grace / "feedback.pdf").write_bytes(b"%PDF fake")
    (grace / ".DS_Store").write_bytes(b"junk")

    zip_path = tmp_path / "up.zip"
    assert main(["pack", str(out), "-o", str(zip_path)]) == 0
    with zipfile.ZipFile(zip_path) as z:
        assert sorted(z.namelist()) == [
            f"{ada.name}/feedback.pdf",
            f"{grace.name}/feedback.pdf",
        ]


def test_pack_all_empty_fails(tmp_path):
    roster = make_roster(tmp_path)
    out = tmp_path / "up"
    main(["folders", "-a", "1", "-r", str(roster), "-o", str(out)])
    assert main(["pack", str(out), "-o", str(tmp_path / "up.zip")]) == 1
