from collections.abc import Iterator
from functools import cached_property
from os import PathLike
from pathlib import Path
from re import M
from typing import cast
from zipfile import ZipFile, ZipInfo

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message
from keynote_parser.codec import IWAArchiveSegment, IWACompressedChunk, IWAFile


def message_to_dict(message: Message):
    output = MessageToDict(message)
    output["_pbtype"] = type(message).DESCRIPTOR.full_name
    return output


def zip_file_reader(path, progress=False):
    zipfile = ZipFile(path, "r")
    for _file in zipfile.filelist:
        _file.filename = _file.filename.encode("cp437").decode("utf-8")
    iterator = sorted(zipfile.filelist, key=lambda x: x.filename)
    if progress:
        iterator = tqdm(iterator)
    for zipinfo in iterator:
        if zipinfo.filename.endswith("/"):
            continue
        if progress:
            iterator.set_description(f"Reading {zipinfo.filename}...")
        with zipfile.open(zipinfo) as handle:
            yield (zipinfo.filename, handle)


class KeynoteFile:
    def __init__(self, path: str | PathLike) -> None:
        self.path = Path(path).expanduser().absolute()
        self.zipfile = ZipFile(self.path, "r")
        for _file in self.zipfile.filelist:
            _file.filename = _file.filename.encode("cp437").decode("utf-8")

    @cached_property
    def document(self) -> "Document":
        contents = self.zipfile.read("Index/Document.iwa")
        iwa = IWAFile.from_buffer(contents, "Index/Document.iwa")
        return Document(iwa)

    @property
    def filelist(self) -> list[ZipInfo]:
        return sorted(self.zipfile.filelist, key=lambda x: x.filename)

    @property
    def slides(self) -> Iterator["Slide"]:
        slide_prefix = "Index/Slide-"
        for zinfo in self.filelist:
            fname = zinfo.filename
            if fname.startswith(slide_prefix) and fname.endswith(".iwa"):
                yield Slide(self.zipfile, zinfo)

    def __repr__(self) -> str:
        return f"<KeynoteFile {self.path}>"


class Document:
    def __init__(self, iwa: IWAFile) -> None:
        self.iwa = iwa

    @cached_property
    def slide_ids(self) -> list[int]:
        chunk: IWACompressedChunk
        archive: IWAArchiveSegment
        msg: Message

        for chunk in self.iwa.chunks:
            for archive in chunk.archives:
                for msg in archive.objects:
                    if msg.DESCRIPTOR.full_name == "KN.ShowArchive":
                        d = MessageToDict(msg)
                        slides = d["slideTree"]["slides"]
                        return [slide["identifier"] for slide in slides]


class Slide:
    def __init__(self, zipfile: ZipFile, zipinfo: ZipInfo) -> None:
        self.zipfile = zipfile
        self.zipinfo = zipinfo
        with self.zipfile.open(self.zipinfo) as handle:
            self.iwa = IWAFile.from_buffer(handle.read(), self.zipinfo.filename)

    def __repr__(self) -> str:
        return f"<Slide {self.zipinfo.filename}>"

    @property
    def chunks(self) -> list[IWACompressedChunk]:
        return self.iwa.chunks

    def iter_archives(self) -> Iterator[IWAArchiveSegment]:
        for chunk in self.chunks:
            yield from chunk.archives

    @property
    def text_blocks(self) -> list[str]:
        if not hasattr(self, "_text_blocks"):
            blocks = []
            for archive in self.iter_archives():
                objects = cast(list[Message], archive.objects)
                for obj in objects:
                    if (
                        obj.DESCRIPTOR.full_name == "TSWP.StorageArchive"
                        and "text" in obj.DESCRIPTOR.fields_by_name
                        and (txt := MessageToDict(obj).get("text"))
                    ):
                        blocks.extend(txt)
            self._text_blocks = blocks
        return self._text_blocks
