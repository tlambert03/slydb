import itertools
import shutil
from pathlib import Path

import meilisearch

from slydb.keynote import KeynoteFile

root = "/Users/talley/Dropbox (HMS)/NIC Team/QI/QI 2022 - Dropbox/QI Lectures 2022"

shutil.rmtree("thumbnails", ignore_errors=True)
client = meilisearch.Client("http://localhost:7700", "aSampleMasterKey")
slides = client.index("slides")
slides.delete()
slides.update_displayed_attributes(["file", "slide_number", "text", "thumbnail"])

counter = itertools.count()
for path in Path(root).rglob("*.key"):
    print("Processing", path.name)
    docs = []
    try:
        k = KeynoteFile(path)
        for n, slide in enumerate(k.slides):
            thumb = slide.save_thumb("thumbnails")
            docs.append(
                {
                    "id": next(counter),
                    "file": path.name,
                    "slide_number": n,
                    "text": "\n".join(slide.text_blocks),
                    "thumbnail": f"http://localhost:8000/{thumb.name}",
                }
            )
    except Exception as e:
        print(f" ❌ Error processing {path}: {e}")
        continue
    else:
        slides.add_documents(docs)
        print(f"  Added {len(docs)} documents to the index")
