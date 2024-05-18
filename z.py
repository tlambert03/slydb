import os
from pathlib import Path

from rich import print

from slydb.keynote import KeynoteFile

# root = Path("/Users/talley/Dropbox (HMS)/NIC Team/QI")
root = Path("/Users/talley/Desktop")


records = []
for _i, fpath in enumerate(root.rglob("*.key")):
    if os.stat(fpath).st_size == 0:
        continue
    if fpath.is_dir():
        continue
    if "handout" in str(fpath).lower():
        continue
    try:
        kf = KeynoteFile(fpath)
    except Exception as e:
        print(f" ❌ {fpath}: {e}")
        continue
    print("👍", fpath)
    for slide in kf.slides:
        records.append(slide.record())

print(records)
# import meilisearch
# client = meilisearch.Client("http://localhost:7700")
# slides = client.index("slides")
# slides.delete()
# task = slides.add_documents(records)
# task = client.wait_for_task(task.task_uid)
# print(task)
