import fnmatch
import getpass
import os
import tempfile
from collections.abc import Iterator, Sequence

import dropbox
from dropbox.files import FileMetadata

from slydb.keynote import KeynoteFile


def recursive_glob(
    dbx: dropbox.Dropbox, path: str, pattern: str, exclude_patterns: Sequence[str] = ()
) -> Iterator[FileMetadata]:
    def _process_entries(entries):
        for entry in entries:
            if isinstance(entry, FileMetadata):
                if fnmatch.fnmatch(entry.path_lower, pattern):
                    if any(p in entry.path_lower for p in exclude_patterns):
                        continue
                    yield entry

    response = dbx.files_list_folder(path, recursive=True)
    yield from _process_entries(response.entries)
    while response.has_more:
        response = dbx.files_list_folder_continue(response.cursor)
        yield from _process_entries(response.entries)


def process_file(entry: FileMetadata):
    print("Processing", entry.name)
    slides = []
    try:
        # Download the file to a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            dbx.files_download_to_file(temp_file.name, entry.path_lower)
            k = KeynoteFile(temp_file.name)

        for n, slide in enumerate(k.slides):
            thumb = slide.save_thumb("thumbnails")
            slides.append(
                {
                    "id": entry.path_lower,
                    "file": entry.name,
                    "slide_number": n,
                    "presenter_notes": "\n".join(slide.presenter_notes),
                    "text": "\n".join(slide.text_blocks),
                    "thumbnail": f"http://localhost:8000/{thumb.name}",
                }
            )
    except Exception as e:
        print(f" ❌ Error processing {entry.name}: {e}")
    else:
        print(f" ✅ Added {len(slides)} documents to the index")
    finally:
        # Delete the temporary file
        os.remove(temp_file.name)

    return slides


ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN") or getpass.getpass(
    "Enter your Dropbox access token: "
)
if not ACCESS_TOKEN:
    raise ValueError("No access token provided")

dbx = dropbox.Dropbox(ACCESS_TOKEN)
fpath = "/NIC Team"
n = 0
for _i in recursive_glob(dbx, fpath, "*.key", exclude_patterns=("handout",)):
    process_file(_i)
    n += 1
    if n > 5:
        break
