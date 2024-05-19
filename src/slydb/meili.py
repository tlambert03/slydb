import http.server
import json
import socket
import subprocess
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path
from threading import Thread
import webbrowser

import meilisearch
import meilisearch.errors


def meili_main(
    records: list[dict] | str | Path,
    meili_port: int = 7700,
    meili_host: str = "localhost",
    meili_key: str | None = None,
    thumb_dir: str | Path | None = "thumbnails",
    thumb_port: int = 8888,
    thumb_host: str = "localhost",
    index: str = "slides",
):
    if isinstance(records, str | Path):
        records = json.loads(Path(records).read_text())

    # Setup thumbnail server
    if thumb_dir is not None:
        if not Path(thumb_dir).exists():
            raise FileNotFoundError(f"Directory not found: {thumb_dir}")
        if is_server_running(thumb_host, thumb_port):
            raise RuntimeError(
                f"Server is already running at {thumb_host}:{thumb_port}"
            )
        thumb_server = thumbnail_server(thumb_host, thumb_port, thumb_dir)
    else:
        thumb_server = nullcontext(None)

    with meili_client(meili_host, meili_port, meili_key) as client:
        idx = client.index(index)
        idx.delete()

        with thumb_server as thumb_url:
            task = idx.add_documents(_arrange_records(records, thumb_url))
            task = client.wait_for_task(task.task_uid)
            if task.status != "succeeded":
                print("Failed to index documents", task.error)
            else:
                print("\nDocuments indexed successfully", task.details)
                print("MeiliSearch server running at", client.config.url)
                print("Press Ctrl+C to stop the server")
                webbrowser.open(client.config.url)
                while True:
                    pass


def _arrange_records(
    records: list[dict], thumb_url: str | None, skip_dupes: bool = True
) -> list[dict]:
    docs = []
    seen = set()
    for record in records:
        for slide in record.pop("slides"):
            record = {**record, **slide}
            if thumb_url and (digest := record.pop("thumb_digest", None)):
                if skip_dupes and digest in seen:
                    continue
                record["thumbnail"] = f"{thumb_url}/{digest}.jpg"
                seen.add(digest)
            docs.append(record)
    return docs


def is_server_running(host: str, port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((host, port)) == 0


@contextmanager
def meili_client(host, port, key=None):
    client = meilisearch.Client(f"http://{host}:{port}", key)
    proc = None
    if not client.is_healthy():
        cmd = ["meilisearch", "--http-addr", f"{host}:{port}"]
        if key:
            cmd.extend(["--master-key", key])
        proc = subprocess.Popen(cmd)
        i = 0
        while not client.is_healthy():
            time.sleep(0.1)
            i += 1
            if i > 20:
                raise TimeoutError("MeiliSearch server did not start")

    try:
        yield client
    finally:
        if proc is not None:
            proc.terminate()
            proc.wait()


@contextmanager
def thumbnail_server(host: str, port: int, directory: str | Path):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

    server = http.server.HTTPServer((host, port), Handler)
    server_thread = Thread(target=server.serve_forever)
    server_thread.start()

    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server_thread.join()
