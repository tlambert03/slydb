import fnmatch
import getpass
import hashlib
import os
import tempfile
import uuid
from collections.abc import Iterator, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import dropbox
import dropbox.exceptions
import meilisearch
import meilisearch.errors
from dropbox.files import FileMetadata, WriteMode
from rich import print

from slydb.keynote import KeynoteFile

ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN") or getpass.getpass(
    "Enter your Dropbox access token: "
)
if not ACCESS_TOKEN:
    raise ValueError("No access token provided")

dbx = dropbox.Dropbox(ACCESS_TOKEN)
meiliclient = meilisearch.Client("http://localhost:7700")
slides = meiliclient.index("slides")
# slides.delete()


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


def _make_id(*n: Any) -> str:
    x = ""
    for i in n:
        x += str(i)
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, x))


def process_file(entry: FileMetadata) -> list[dict]:
    print("Processing", entry.name)

    slides = []
    try:
        # Download the file to a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            dbx.files_download_to_file(temp_file.name, entry.path_lower)
            k = KeynoteFile(temp_file.name)
        url = dbx.sharing_create_shared_link(entry.path_lower, short_url=True)
        for n, slide in enumerate(k.slides):
            try:
                fpath, thumbdata = slide.get_thumb()
            except ValueError:
                thumb_url: str = ""
            else:
                # Create a hash of the thumbnail data
                hash_object = hashlib.sha256(thumbdata)
                hex_dig = hash_object.hexdigest()
                # Use the hash as the filename
                hashed_filename = f"/Apps/slide_thumbs/{hex_dig}.jpeg"

                # check if the thumbnail already exists on dropbox
                try:
                    thumb_url = dbx.sharing_create_shared_link(
                        hashed_filename, short_url=True
                    ).url
                except dropbox.exceptions.ApiError as e:
                    if e.error.is_path() and e.error.get_path().is_not_found():
                        dbx.files_upload(
                            thumbdata, hashed_filename, mode=WriteMode.overwrite
                        )
                        thumb_url = dbx.sharing_create_shared_link(
                            hashed_filename, short_url=True
                        ).url
                    else:
                        raise

                thumb_url = thumb_url.replace(
                    "www.dropbox.com", "dl.dropboxusercontent.com"
                ).split("&dl")[0]

            slides.append(
                {
                    "file": entry.name,
                    "dropbox": url.url,
                    "slide_number": n,
                    "text": "\n".join(slide.text_blocks).strip(),
                    "presenter_notes": "\n".join(slide.presenter_notes).strip(),
                    "thumbnail": thumb_url,
                    "id": _make_id(entry.path_lower, n),
                }
            )

    except Exception as e:
        print(f" ❌ Error processing {entry.name}: {e}")
    finally:
        # Delete the temporary file
        os.remove(temp_file.name)

    return slides


def index_result(fut: Future[list[dict]]):
    try:
        result = fut.result()
    except Exception:
        return
    if not result:
        return

    task_info = slides.add_documents(result)
    task = meiliclient.wait_for_task(task_info.task_uid)
    if task.status == "succeeded":
        print(f"👍 Added {len(result)} documents to the index")


def index_folder(fpath="/NIC Team", max_files=None, exclude_patterns=("handout",)):
    with ThreadPoolExecutor() as executor:
        n = 0
        for _i in recursive_glob(
            dbx, fpath, "*.key", exclude_patterns=exclude_patterns
        ):
            if max_files and n >= max_files:
                break
            try:
                slides.get_document(_make_id(_i.path_lower, 0))
                print(f"Skipping {_i.name} as it is already indexed")
                continue
            except meilisearch.errors.MeilisearchApiError:
                pass

            future = executor.submit(process_file, _i)
            future.add_done_callback(index_result)
            n += 1
