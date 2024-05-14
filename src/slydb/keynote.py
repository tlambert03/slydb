from os import PathLike
from pathlib import Path
from typing import Iterator
from zipfile import ZipFile, ZipInfo


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
            iterator.set_description("Reading {}...".format(zipinfo.filename))
        with zipfile.open(zipinfo) as handle:
            yield (zipinfo.filename, handle)


class KeynoteFile:
    def __init__(self, path: str | PathLike) -> None:
        self.path = Path(path).expanduser().absolute()
        self.zipfile = ZipFile(self.path, "r")
        for _file in self.zipfile.filelist:
            _file.filename = _file.filename.encode("cp437").decode("utf-8")

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


class Slide:
    def __init__(self, zipfile: ZipFile, zipinfo: ZipInfo) -> None:
        self.zipfile = zipfile
        self.zipinfo = zipinfo

    @property
    def contents(self) -> bytes:
        from keynote_parser.codec import IWAFile

        with self.zipfile.open(self.zipinfo) as handle:
            return IWAFile.from_buffer(handle.read(), self.zipinfo.filename)

    def __repr__(self) -> str:
        return f"<Slide {self.zipinfo.filename}>"
