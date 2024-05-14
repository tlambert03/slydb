from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message
from keynote_parser.codec import IWAArchiveSegment, IWACompressedChunk
from rich import print

from slydb.keynote import KeynoteFile

keynote = KeynoteFile(
    "/Users/talley/Dropbox (HMS)/Keynotes/magicgui_pyappkit_doepy.key"
)


def message_to_dict(message):
    if hasattr(message, "to_dict"):
        return message.to_dict()
    output = MessageToDict(message)
    output["_pbtype"] = type(message).DESCRIPTOR.full_name
    return output


for i, slide in enumerate(keynote.slides):
    print(i, slide)
    print(slide.text_blocks)
    # for archive in slide.iter_archives():
    #     header: Message = archive.header
    #     obj: Message = archive.objects[0]

    #     for obj in archive.objects:
    #         d = message_to_dict(obj)
    #         if "text" in d:
    #             print(d)


def has_field(msg: Message, field: str):
    return field in msg.DESCRIPTOR.fields_by_name
