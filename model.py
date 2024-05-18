import json
import os
from pathlib import Path

from rich import print

from slydb.model import KeynoteFile

root = Path("/Users/talley/Dropbox (HMS)/")
records = []
for _i, fpath in enumerate(root.rglob("*.key")):
    if os.stat(fpath).st_size == 0:
        continue
    if fpath.is_dir() or ".dropbox.cache" in fpath.parts:
        continue

    with KeynoteFile(fpath) as kf:
        records.append(kf.record())
    print("file", fpath)

Path("records.json").write_text(json.dumps(records, indent=2))
