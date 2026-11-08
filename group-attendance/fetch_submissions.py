#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["websockets"]
# ///
"""Fetch group-submission folders from Brightspace as the zips `scan` reads.

Saves the "Select all -> Download" clicks: runs inside your logged-in
Brightspace tab (Chrome started with --remote-debugging-port=9222) and writes
one zip per assignment, laid out as Brightspace's own download is:

    <Assignment> Download <Mon D, YYYY HMM AM> (Group Submission Folder).zip
      <group id>-<assignment id> - <team> - <submitter> - <Mon D, YYYY HMM PM>/<file>

Times are written in America/Indiana/Indianapolis, as Brightspace does.

    uv run group-attendance/fetch_submissions.py --ou 90549 --out DIR 194384 194698 ...
    uv run group-attendance/fetch_submissions.py --ou 90549 --list   # folder ids and names
"""
import argparse
import asyncio
import base64
import datetime as dt
import json
import re
import urllib.request
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo

import websockets

TZ = ZoneInfo("America/Indiana/Indianapolis")
API = "/d2l/api/le/1.67"


def page_ws(match="brightspace"):
    for t in json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/list")):
        if t["type"] == "page" and match in t["url"]:
            return t["webSocketDebuggerUrl"]
    raise SystemExit("no Brightspace tab on the Chrome debug port 9222")


async def evaluate(ws, expr, n=[0]):
    n[0] += 1
    await ws.send(json.dumps({"id": n[0], "method": "Runtime.evaluate", "params": {
        "expression": expr, "returnByValue": True, "awaitPromise": True}}))
    while True:
        r = json.loads(await ws.recv())
        if r.get("id") == n[0]:
            res = r["result"]
            if "exceptionDetails" in res:
                raise RuntimeError(res["exceptionDetails"])
            return res["result"].get("value")


def stamp(t: dt.datetime) -> str:
    """'Oct 14, 2026 147 PM': no zero padding, no colon."""
    h = t.hour % 12 or 12
    return f"{t:%b} {t.day}, {t.year} {h}{t:%M} {t:%p}"


def safe(name: str) -> str:
    """Brightspace drops ':' and '/' from names in a download."""
    return re.sub(r"[:/]", "", name)


async def fetch(ou: int, folder_ids: list[int], out: Path) -> None:
    async with websockets.connect(page_ws(), max_size=2**27) as ws:
        folders = await evaluate(ws, f"fetch('{API}/{ou}/dropbox/folders/').then(r=>r.json())")
        names = {f["Id"]: f["Name"] for f in folders}
        now = stamp(dt.datetime.now(TZ))
        for fid in folder_ids:
            subs = await evaluate(ws, f"fetch('{API}/{ou}/dropbox/folders/{fid}/submissions/').then(r=>r.json())")
            zpath = out / f"{safe(names[fid])} Download {now} (Group Submission Folder).zip"
            n = 0
            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
                for ent in subs:
                    team, gid = ent["Entity"]["Name"], ent["Entity"]["EntityId"]
                    for s in ent["Submissions"]:
                        t = dt.datetime.fromisoformat(s["SubmissionDate"].replace("Z", "+00:00")).astimezone(TZ)
                        folder = f"{gid}-{fid} - {team} - {s['SubmittedBy']['DisplayName']} - {stamp(t)}"
                        for f in s["Files"]:
                            if f.get("IsDeleted"):
                                continue
                            b64 = await evaluate(ws, (
                                f"fetch('{API}/{ou}/dropbox/folders/{fid}/submissions/{s['Id']}/files/{f['FileId']}')"
                                ".then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.arrayBuffer()})"
                                ".then(b=>{let s='';const u=new Uint8Array(b);for(let i=0;i<u.length;i+=32768)"
                                "s+=String.fromCharCode.apply(null,u.subarray(i,i+32768));return btoa(s)})"))
                            zi = zipfile.ZipInfo(f"{folder}/{f['FileName']}", date_time=t.timetuple()[:6])
                            zf.writestr(zi, base64.b64decode(b64), zipfile.ZIP_DEFLATED)
                            n += 1
            print(f"{zpath.name}: {n} files")


async def list_folders(ou: int) -> None:
    async with websockets.connect(page_ws(), max_size=2**27) as ws:
        for f in await evaluate(ws, f"fetch('{API}/{ou}/dropbox/folders/').then(r=>r.json())"):
            if f.get("GroupTypeId"):
                print(f["Id"], f["Name"], f.get("TotalUsersWithSubmissions"))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ou", type=int, required=True, help="course org unit id")
    p.add_argument("--out", type=Path, default=Path("."))
    p.add_argument("--list", action="store_true", help="list group folders and exit")
    p.add_argument("folders", type=int, nargs="*")
    a = p.parse_args()
    if a.list or not a.folders:
        asyncio.run(list_folders(a.ou))
    else:
        asyncio.run(fetch(a.ou, a.folders, a.out))


if __name__ == "__main__":
    main()
