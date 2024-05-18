import json
from collections.abc import Iterable
from pathlib import Path

import tqdm

from slydb.model import KeynoteFile


def _index_file(fpath: Path, thumbnails: str | Path | None = None) -> dict | None:
    with KeynoteFile(fpath) as kf:
        if thumbnails is not None:
            kf.export_thumbnails(dest=thumbnails)
        return kf.record()


def index_path(
    root: str | Path,
    output: str | Path | None,
    exclude: Iterable[str] = (".dropbox.cache", "handout"),
    thumbnails: str | Path | None = None,
) -> list[dict]:
    paths = (
        p for p in Path(root).rglob("*.key") if p.stat().st_size > 0 and not p.is_dir()
    )
    paths = [p for p in paths if not any(ex in str(p).lower() for ex in exclude)]

    records = [_index_file(p, thumbnails) for p in tqdm.tqdm(paths)]

    if output is not None:
        Path(output).write_text(json.dumps(records, indent=2))

    return records
