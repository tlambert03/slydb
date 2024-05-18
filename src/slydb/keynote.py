from __future__ import annotations

import base64
import hashlib
from contextlib import suppress
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, cast
from zipfile import ZipFile, ZipInfo

from google.protobuf.message import Message
from keynote_parser.codec import IWAFile

if TYPE_CHECKING:
    from collections.abc import Iterator
    from os import PathLike


DOC_PATH = "Index/Document.iwa"
META_PATH = "Index/Metadata.iwa"
PRESENTER_KIND = 4


class KeynoteFile:
    def __init__(self, path: str | PathLike) -> None:
        self.path = Path(path).expanduser().absolute()
        self.zip = ZipFile(self.path, "r")
        for _file in self.zip.filelist:
            _file.filename = _file.filename.encode("cp437").decode("utf-8")

        self.datas: dict[int, Message] = {}
        for arch in self.metadata.chunks[0].archives:
            for obj in arch.objects:
                if (
                    hasattr(obj, "DESCRIPTOR")
                    and obj.DESCRIPTOR.full_name == "TSP.PackageMetadata"
                ):
                    for item in obj.datas:
                        self.datas[item.identifier] = item

    @cached_property
    def timestamp(self) -> str: ...
    @cached_property
    def author(self) -> str | None:
        with suppress(Exception):
            with self.zip.open("Index/AnnotationAuthorStorage.iwa") as handle:
                iwa = IWAFile.from_buffer(handle.read())
                for arch in iwa.chunks[0].archives:
                    for msg in arch.objects:
                        if msg.DESCRIPTOR.full_name == "TSK.AnnotationAuthorArchive":
                            return msg.name

    @cached_property
    def document_identifier(self) -> str:
        return self.zip.read("Metadata/DocumentIdentifier").decode("utf-8")

    @cached_property
    def revision(self) -> str | None:
        with suppress(Exception):
            return self.metadata.chunks[0].archives[0].objects[0].revision.identifier

    @cached_property
    def file_format_version(self) -> str | None:
        with suppress(Exception):
            parts = self.metadata.chunks[0].archives[0].objects[0].file_format_version
            return ".".join(map(str, parts))

    @property
    def iwas(self) -> Iterator[IWAFile]:
        for zinfo in self.filelist:
            if zinfo.filename.endswith(".iwa"):
                with self.zip.open(zinfo) as handle:
                    yield IWAFile.from_buffer(handle.read(), zinfo.filename)

    @cached_property
    def document(self) -> Document:
        return Document(IWAFile.from_buffer(self.zip.read(DOC_PATH), DOC_PATH))

    @cached_property
    def metadata(self) -> IWAFile:
        return IWAFile.from_buffer(self.zip.read(META_PATH), META_PATH)

    @property
    def filelist(self) -> list[ZipInfo]:
        return sorted(self.zip.filelist, key=lambda x: x.filename)

    @cached_property
    def slides(self) -> list[Slide]:
        slides = []
        slide_info = self.document.slides_info
        for zinfo in self.filelist:
            if (fn := zinfo.filename).startswith("Index/Slide") and fn.endswith(".iwa"):
                with self.zip.open(zinfo) as handle:
                    with suppress(Exception):
                        iwa = IWAFile.from_buffer(handle.read(), fn)
                        slides.append(Slide(iwa, self))

        slides.sort(key=lambda x: slide_info[x.identifier].number)
        return slides

    def __repr__(self) -> str:
        return f"<KeynoteFile {self.path}>"


class SlideInfo(NamedTuple):
    number: int
    identifier: int
    node_identifier: str
    thumbnail_id: int | None
    is_skipped: bool = False
    has_note: bool = False


class Document:
    def __init__(self, iwa: IWAFile) -> None:
        self.iwa = iwa
        # mapping of slide identifier to SlideInfo
        self.slides_info: dict[int, SlideInfo] = {}
        # ID of the theme
        self.theme_id = None

        chunk0 = self.iwa.chunks[0]
        self.archive_map = {a.header.identifier: a for a in chunk0.archives}

        for archive in chunk0.archives:
            for msg in archive.objects:
                if msg.DESCRIPTOR.full_name == "KN.ShowArchive":
                    slide_node_ids = [s.identifier for s in msg.slideTree.slides]
                    self.theme_id = msg.theme.identifier

                    for n, node_id in enumerate(slide_node_ids):
                        node = self.archive_map[node_id].objects[0]
                        slide_id = node.slide.identifier
                        thumbnails = [t.identifier for t in node.thumbnails]
                        self.slides_info[slide_id] = SlideInfo(
                            n + 1,
                            slide_id,
                            node_id,
                            thumbnails[0] if thumbnails else None,
                            is_skipped=getattr(node, "isSkipped", False),
                            has_note=getattr(node, "hasNote", False),
                        )

                    break


class Slide:
    def __init__(self, iwa: IWAFile, keynote: KeynoteFile) -> None:
        self.iwa = iwa
        self.keynote = keynote
        self.info = keynote.document.slides_info[self.identifier]

    @cached_property
    def uuid(self) -> str:
        combo = (
            str(self.keynote.document_identifier)
            + str(self.keynote.revision)
            + str(self.info.identifier)
        )
        # Step 2: Hash the combined string using SHA-256
        hash_object = hashlib.sha256(combo.encode("utf-8"))
        hash_bytes = hash_object.digest()[:16]
        return base64.urlsafe_b64encode(hash_bytes).rstrip(b"=").decode("utf-8")

    def record(self) -> dict[str, str]:
        path = str(self.keynote.path).split("Dropbox (HMS)")[-1]
        return {
            "path": path,
            "slide_number": self.info.number,
            # "node_identifier": self.info.node_identifier,
            # "thumbnail_id": self.info.thumbnail_id,
            # "has_note": self.info.has_note,
            "text_blocks": "\n\n".join(self.text_blocks).rstrip("\n\ufffc "),
            "presenter_notes": "\n".join(self.presenter_notes).rstrip("\n\ufffc "),
            # "thumbnail_path": self.thumbnail_path,
            # "expected_thumb_hash": self.expected_thumb_hash,
            # "thumb_hash": self.thumb_hash,
            "is_skipped": self.info.is_skipped,
            "thumb_hash": self.safe_thumb_hash,
            "id": self.uuid,
            "slide_ident": self.info.identifier,
            "doc_uuident": self.keynote.document_identifier,
            "doc_revision": self.keynote.revision,
            # "author": self.keynote.author,
            "doc_format": self.keynote.file_format_version,
        }

    @cached_property
    def thumbnail_path(self) -> str:
        return self.keynote.datas[self.info.thumbnail_id].file_name

    @cached_property
    def expected_thumb_hash(self) -> str:
        digest = self.keynote.datas[self.info.thumbnail_id].digest
        return base64.b64encode(digest).decode("utf-8")

    @property
    def safe_thumb_hash(self) -> str:
        return _safe_hash(self.expected_thumb_hash)

    @cached_property
    def thumbnail_bytes(self) -> bytes:
        return self.keynote.zip.read(f"Data/{self.thumbnail_path}")

    @cached_property
    def thumb_hash(self) -> str:
        digest = hashlib.sha1(self.thumbnail_bytes).digest()
        return base64.b64encode(digest).decode("utf-8")

    def save_thumb(self, path: str | PathLike) -> Path:
        path = Path(path).expanduser().absolute()
        if not path.is_dir():
            path.mkdir(parents=True)

        with suppress(ValueError):
            dest = path / self.thumbnail_path
            with open(dest, "wb") as f:
                f.write(self.thumbnail_bytes)
            return dest

    @property
    def identifier(self) -> str:
        return self.iwa.chunks[0].archives[0].header.identifier

    def __repr__(self) -> str:
        return f"<Slide {self.iwa.filename}>"

    @property
    def text_blocks(self) -> list[str]:
        if not hasattr(self, "_text_blocks"):
            self._find_text()
        return self._text_blocks

    @property
    def presenter_notes(self) -> list[str]:
        if not hasattr(self, "_presenter_notes"):
            self._find_text()
        return self._presenter_notes

    def _find_text(self):
        blocks = []
        presenter_notes = []
        for archive in self.iwa.chunks[0].archives:
            objects = cast(list[Message], archive.objects)
            for msg in objects:
                if (
                    hasattr(msg, "DESCRIPTOR")
                    and msg.DESCRIPTOR.full_name == "TSWP.StorageArchive"
                    and "text" in msg.DESCRIPTOR.fields_by_name
                ):
                    # presenter notes will have       kind: NOTE
                    if txt := msg.text:
                        if msg.kind == PRESENTER_KIND:
                            presenter_notes.extend(txt)
                        else:
                            blocks.extend(txt)
        self._text_blocks = blocks
        self._presenter_notes = presenter_notes


def _safe_hash(data: str) -> str:
    return data.replace("/", "_").replace("+", "-").replace("=", "")
