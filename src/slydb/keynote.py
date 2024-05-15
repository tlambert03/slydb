from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, cast
from zipfile import ZipFile, ZipInfo

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message
from keynote_parser.codec import IWAFile

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from os import PathLike


DOC_PATH = "Index/Document.iwa"
META_PATH = "Index/Metadata.iwa"


class KeynoteFile:
    def __init__(self, path: str | PathLike) -> None:
        self.path = Path(path).expanduser().absolute()
        self.zip = ZipFile(self.path, "r")
        for _file in self.zip.filelist:
            _file.filename = _file.filename.encode("cp437").decode("utf-8")

        self.datas = {}
        for arch in self.metadata.chunks[0].archives:
            for obj in arch.objects:
                if (
                    hasattr(obj, "DESCRIPTOR")
                    and obj.DESCRIPTOR.full_name == "TSP.PackageMetadata"
                ):
                    for item in obj.datas:
                        self.datas[item.identifier] = item

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
                    iwa = IWAFile.from_buffer(handle.read(), fn)
                slides.append(Slide(iwa, self))

        slides.sort(key=lambda x: slide_info[x.identifier].number)
        return slides

    def __repr__(self) -> str:
        return f"<KeynoteFile {self.path}>"


class SlideInfo(NamedTuple):
    number: int
    identifier: str
    node_identifier: str
    thumbnail_ids: Sequence[int] = ()


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
                            n + 1, slide_id, node_id, thumbnails
                        )

                    break


class Slide:
    def __init__(self, iwa: IWAFile, keynote: KeynoteFile) -> None:
        self.iwa = iwa
        self.keynote = keynote

    def save_thumb(self, path: str | PathLike) -> Path:
        path = Path(path).expanduser().absolute()
        if not path.is_dir():
            path.mkdir(parents=True)

        for thumb in self.keynote.document.slides_info[self.identifier].thumbnail_ids:
            if thumb in self.keynote.datas:
                filename = self.keynote.datas[thumb].file_name
                dest = path / filename
                with self.keynote.zip.open(f"Data/{filename}") as handle:
                    with open(dest, "wb") as f:
                        f.write(handle.read())
                        return dest

    @property
    def identifier(self) -> str:
        return self.iwa.chunks[0].archives[0].header.identifier

    def __repr__(self) -> str:
        return f"<Slide {self.iwa.filename}>"

    @property
    def text_blocks(self) -> list[str]:
        if not hasattr(self, "_text_blocks"):
            blocks = []
            for archive in self.iwa.chunks[0].archives:
                objects = cast(list[Message], archive.objects)
                for obj in objects:
                    if (
                        hasattr(obj, "DESCRIPTOR")
                        and obj.DESCRIPTOR.full_name == "TSWP.StorageArchive"
                        and "text" in obj.DESCRIPTOR.fields_by_name
                        and (txt := MessageToDict(obj).get("text"))
                    ):
                        blocks.extend(txt)
            self._text_blocks = blocks
        return self._text_blocks
