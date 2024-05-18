from __future__ import annotations

import base64
from hashlib import sha256
import logging
import uuid
from contextlib import suppress
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, TypeVar, Union
from zipfile import ZipFile

from keynote_parser.codec import IWAFile
from msgspec import Struct, convert

if TYPE_CHECKING:
    import os
    from collections.abc import Iterator

ArchObj = TypeVar("ArchObj", bound="ArchiveObject")
KW = {"kw_only": True, "frozen": True}


class Ver(NamedTuple):
    major: int
    minor: int
    patch: int

    def __rich_repr__(self) -> Iterator[str]:
        yield str(self)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


class UUID(Struct):
    lower: int
    upper: int

    def __rich_repr__(self) -> Iterator[str]:
        yield f"{self.upper:016x}{self.lower:016x}"


class ObjectUuidMapEntry(Struct, **KW):
    identifier: str
    uuid: UUID


class ExternalReference(Struct, **KW):
    componentIdentifier: str
    objectIdentifier: str | None = None
    isWeak: bool | None = None


class DataReference(Struct, **KW):
    dataIdentifier: str
    objectReferenceList: list[dict] | None = None


class Component(Struct, **KW):
    identifier: int
    documentReadVersion: Ver
    documentWriteVersion: Ver
    externalReferences: list[ExternalReference] | None = None
    isStoredOutsideObjectArchive: bool
    locator: str | None = None
    objectUuidMapEntries: list[ObjectUuidMapEntry] | None = None
    preferredLocator: str
    saveToken: str | None = None
    dataReferences: list[DataReference] | None = None
    featureInfos: list[dict] | None = None
    requiredPackageIdentifier: int | None = None


class DataItem(Struct):
    identifier: int
    digest: str
    preferredFileName: str
    fileName: str | None = None
    documentResourceLocator: str | None = None
    attributes: dict | None = None


class PBtype(
    Struct,
    tag_field="_pbtype",
    tag=lambda x: x.replace("_", "."),
    frozen=True,
    kw_only=True,
): ...


class Revision(Struct, **KW):
    identifier: uuid.UUID
    sequence32: int | None = None
    sequence64: int | None = None


class TSP_PackageMetadata(PBtype, **KW):
    components: list[Component]
    datas: list[DataItem]
    fileFormatVersion: Ver
    lastObjectIdentifier: str
    readVersion: Ver
    revision: Revision
    saveToken: str
    writeVersion: Ver
    dataMetadataMap: dict | None = None

    _component_map: dict[str, Component] = {}
    _data_map: dict[str, DataItem] = {}

    def __post_init__(self):
        for c in self.components:
            self._component_map[c.identifier] = c
        for d in self.datas:
            self._data_map[d.identifier] = d

    def get_component(self, identifier: str) -> Component:
        return self._component_map[identifier]

    def get_data_item(self, identifier: str) -> DataItem:
        return self._data_map[identifier]


class TSP_DataMetadataMap(PBtype, **KW):
    dataMetadataEntries: list[Any] = []


class TSP_DataMetadata(PBtype, **KW):
    fallbackColor: dict


class Ref(Struct, tag_field="_pbtype", tag="TSP.Reference", **KW):
    identifier: int

    def archive(self) -> Archive:
        return Archive._store[self.identifier]


class TSP_Size(Struct, **KW):
    height: float
    width: float


class KN_SlideTreeArchive(Struct, **KW):
    slides: list[Ref] = []
    rootSlideNode: Ref | None = None


class KN_DocumentArchive(PBtype, **KW):
    show: Ref
    super: dict

    def get_show(self) -> KN_ShowArchive:
        return self.show.archive().next_object_of_type(KN_ShowArchive)


class KN_ShowArchive(PBtype, **KW):
    automaticallyPlaysUponOpen: bool
    autoplayBuildDelay: float
    autoplayTransitionDelay: float
    idleTimerActive: bool
    idleTimerDelay: float
    loopPresentation: bool
    mode: str
    size: TSP_Size
    slideTree: KN_SlideTreeArchive
    soundtrack: Ref | None = None
    stylesheet: Ref
    theme: Ref


class KN_SlideNodeArchive(PBtype, **KW):
    backgroundIsNoFillOrColorFillWithAlpha: bool | None = None
    buildEventCountCacheVersion: int | None = None
    depth: int | None = None
    hasBuilds: bool
    hasExplicitBuilds: bool | None = None
    hasExplicitBuildsCacheVersion: int | None = None
    hasNote: bool
    hasTransition: bool
    isSkipped: bool
    isCollapsed: bool | None = None
    isCollapsedInOutlineView: bool | None = None
    isSlideNumberVisible: bool
    slide: Ref | None = None
    templateSlideId: UUID | None = None
    thumbnailSizes: list[TSP_Size] = []
    uniqueIdentifier: str | None = None
    thumbnails: list[Ref] = []
    thumbnailsAreDirty: bool
    copyFromSlideIdentifier: str | None = None
    buildEventCount: int | None = None
    buildEventCountIsUpToDate: bool | None = None
    hasExplicitBuildsIsUpToDate: bool | None = None
    children: list[Ref] = []
    slideSpecificHyperlinkCount: int | None = None
    hasBodyInOutlineView: bool | None = None


class TSWP_Reference(Struct):
    identifier: int
    deprecatedType: int | None = None
    deprecatedIsExternal: bool | None = None


class TSWP_ObjectAttribute(Struct, **KW):
    characterIndex: int
    object: TSWP_Reference | str | None = None


class TSWP_ObjectAttributeTable(Struct, **KW):
    entries: list[TSWP_ObjectAttribute] = []


class TSWP_ParaDataAttribute(Struct, **KW):
    characterIndex: int
    first: int
    second: int


class TSWP_ParaDataAttributeTable(Struct, **KW):
    entries: list[TSWP_ParaDataAttribute] = []


class TSWP_StorageArchive(PBtype, **KW):
    kind: str | None = "TEXTBOX"
    styleSheet: TSWP_Reference | None = None
    text: list[str] = []
    hasItext: bool | None = False
    inDocument: bool | None = False
    tableParaStyle: TSWP_ObjectAttributeTable | None = None
    tableParaData: TSWP_ParaDataAttributeTable | None = None
    tableListStyle: TSWP_ObjectAttributeTable | None = None
    tableCharStyle: TSWP_ObjectAttributeTable | None = None
    tableAttachment: TSWP_ObjectAttributeTable | None = None
    tableSmartfield: TSWP_ObjectAttributeTable | None = None
    tableLayoutStyle: TSWP_ObjectAttributeTable | None = None
    tableParaStarts: TSWP_ParaDataAttributeTable | None = None
    tableBookmark: TSWP_ObjectAttributeTable | None = None
    tableFootnote: TSWP_ObjectAttributeTable | None = None
    tableSection: TSWP_ObjectAttributeTable | None = None
    tableRubyfield: TSWP_ObjectAttributeTable | None = None
    tableLanguage: TSWP_ObjectAttributeTable | None = None
    tableDictation: TSWP_ObjectAttributeTable | None = None
    tableInsertion: TSWP_ObjectAttributeTable | None = None
    tableDeletion: TSWP_ObjectAttributeTable | None = None
    tableHighlight: TSWP_ObjectAttributeTable | None = None
    tableParaBidi: TSWP_ParaDataAttributeTable | None = None
    tableOverlappingHighlight: TSWP_ObjectAttributeTable | None = None
    tablePencilAnnotation: TSWP_ObjectAttributeTable | None = None
    tableTatechuyoko: TSWP_ObjectAttributeTable | None = None
    tableDropCapStyle: TSWP_ObjectAttributeTable | None = None


class TSP_FieldInfo(Struct, **KW):
    path: dict
    type: str | None = None
    unknownFieldRule: str | None = None
    knownFieldRule: str | None = None


class TSP_MessageInfo(Struct, **KW):
    type: int
    version: Ver
    fieldInfos: list[TSP_FieldInfo] = []
    objectReferences: list[int] = []
    dataReferences: list[int] = []
    baseMessageIndex: int | None = None


class TSP_ArchiveInfo(PBtype, **KW):
    identifier: int
    messageInfos: list[TSP_MessageInfo]


# fmt: off
# class TSP_Reference(PBtype): ...
class TSP_DataReference(PBtype): ...
class TSP_SparseReferenceArray(PBtype): ...
class TSP_Entry(PBtype): ...
class TSP_Point(PBtype): ...
# class TSP_Size(PBtype): ...
class TSP_Range(PBtype): ...
class TSP_Date(PBtype): ...
class TSP_IndexSet(PBtype): ...
class TSP_Color(PBtype): ...
class TSP_Path(PBtype): ...
class TSP_Element(PBtype): ...
class TSP_ReferenceDictionary(PBtype): ...
# class TSP_Entry(PBtype): ...
class TSP_UUID(PBtype): ...
class TSP_CFUUIDArchive(PBtype): ...
class TSP_UUIDSetArchive(PBtype): ...
class TSP_UUIDMapArchive(PBtype): ...
class TSP_UUIDMultiMapArchive(PBtype): ...
class TSP_UUIDCoordArchive(PBtype): ...
class TSP_UUIDRectArchive(PBtype): ...
class TSP_SparseUUIDArray(PBtype): ...
class TSP_UUIDPath(PBtype): ...
class TSP_SparseUUIDPathArray(PBtype): ...
class TSP_PasteboardObject(PBtype): ...
class TSP_ObjectCollection(PBtype): ...
class TSP_ObjectContainer(PBtype): ...
class TSP_DataAttributes(PBtype): ...
class TSP_LargeArraySegment(PBtype): ...
class TSP_LargeNumberArraySegment(PBtype): ...
class TSP_LargeStringArraySegment(PBtype): ...
class TSP_OptionalElement(PBtype): ...
class TSP_LargeUUIDArraySegment(PBtype): ...
class TSP_LargeLazyObjectArraySegment(PBtype): ...
class TSP_LargeObjectArraySegment(PBtype): ...
class TSP_LargeArray(PBtype): ...
class TSP_LargeNumberArray(PBtype): ...
class TSP_LargeStringArray(PBtype): ...
class TSP_LargeLazyObjectArray(PBtype): ...
class TSP_LargeObjectArray(PBtype): ...
class TSP_LargeUUIDArray(PBtype): ...
class TSP_FieldOptions(PBtype): ...
# class TSP_ArchiveInfo(PBtype): ...
# class TSP_MessageInfo(PBtype): ...
# class TSP_FieldInfo(PBtype): ...
class TSP_FieldPath(PBtype): ...
class TSP_ComponentInfo(PBtype): ...
class TSP_ComponentExternalReference(PBtype): ...
class TSP_ComponentDataReference(PBtype): ...
class TSP_ObjectReference(PBtype): ...
class TSP_ObjectUUIDMapEntry(PBtype): ...
class TSP_FeatureInfo(PBtype): ...
# class TSP_PackageMetadata(PBtype): ...
class TSP_DocumentRevision(PBtype): ...
class TSP_PasteboardMetadata(PBtype): ...
class TSP_DataInfo(PBtype): ...
# class TSP_DataMetadataMap(PBtype): ...
class TSP_DataMetadataMapEntry(PBtype): ...
# class TSP_DataMetadata(PBtype): ...
class TSP_EncryptionInfo(PBtype): ...
class TSP_EncryptionBlockInfo(PBtype): ...
class TSP_ViewStateMetadata(PBtype): ...
class TSP_ObjectSerializationMetadata(PBtype): ...
class TSP_ObjectSerializationDirectory(PBtype): ...
# class TSP_Entry(PBtype): ...
class TSP_DataPropertiesEntryV1(PBtype): ...
class TSP_DataPropertiesV1(PBtype): ...
class TSP_DocumentMetadata(PBtype): ...
class TSP_SupportMetadata(PBtype): ...
class TSP_DataCollaborationProperties(PBtype): ...

class TSA_FunctionBrowserStateArchive(PBtype): ...
class TSA_CaptionInfoArchive(PBtype): ...
class TSA_CaptionPlacementArchive(PBtype): ...

class TST_TableStylePresetArchive(PBtype): ...
class TST_TableStyleNetworkArchive(PBtype): ...

class TSK_TreeNode(PBtype): ...
class TSK_LocalCommandHistoryItem(PBtype): ...
class TSK_LocalCommandHistoryArray(PBtype): ...
class TSK_LocalCommandHistoryArraySegment(PBtype): ...
class TSK_LocalCommandHistory(PBtype): ...
class TSK_CollaborationCommandHistoryArray(PBtype): ...
class TSK_CollaborationCommandHistoryArraySegment(PBtype): ...
class TSK_CollaborationCommandHistory(PBtype): ...
class TSK_ItemList(PBtype): ...
class TSK_CollaborationCommandHistoryItem(PBtype): ...
class TSK_CollaborationCommandHistoryCoalescingGroup(PBtype): ...
class TSK_CollaborationCommandHistoryCoalescingGroupNode(PBtype): ...
class TSK_CollaborationCommandHistoryOriginatingCommandAcknowledgementObserver(PBtype): ...
class TSK_DocumentArchive(PBtype): ...
class TSK_FormattingSymbolsArchive(PBtype): ...
class TSK_CurrencySymbol(PBtype): ...
class TSK_DocumentSupportCollaborationState(PBtype): ...
class TSK_DocumentSupportArchive(PBtype): ...
class TSK_ViewStateArchive(PBtype): ...
class TSK_CommandArchive(PBtype): ...
class TSK_CommandGroupArchive(PBtype): ...
class TSK_InducedCommandCollectionArchive(PBtype): ...
class TSK_PropagatedCommandCollectionArchive(PBtype): ...
class TSK_FinalCommandPairArchive(PBtype): ...
class TSK_CommandContainerArchive(PBtype): ...
class TSK_ProgressiveCommandGroupArchive(PBtype): ...
class TSK_FormatStructArchive(PBtype): ...
class TSK_CustomFormatArchive(PBtype): ...
class TSK_Condition(PBtype): ...
class TSK_CustomFormatListArchive(PBtype): ...
class TSK_AnnotationAuthorArchive(PBtype): ...
class TSK_DeprecatedChangeAuthorArchive(PBtype): ...
class TSK_AnnotationAuthorStorageArchive(PBtype): ...
class TSK_SetAnnotationAuthorColorCommandArchive(PBtype): ...
class TSK_SetActivityAuthorShareParticipantIDCommandArchive(PBtype): ...
class TSK_CommandBehaviorSelectionPathStorageArchive(PBtype): ...
class TSK_CommandBehaviorArchive(PBtype): ...
class TSK_CommandSelectionBehaviorArchive(PBtype): ...
class TSK_SelectionPathTransformerArchive(PBtype): ...
class TSK_SelectionPathArchive(PBtype): ...
class TSK_DocumentSelectionArchive(PBtype): ...
class TSK_IdOperationArgs(PBtype): ...
class TSK_AddIdOperationArgs(PBtype): ...
class TSK_RemoveIdOperationArgs(PBtype): ...
class TSK_RearrangeIdOperationArgs(PBtype): ...
class TSK_IdPlacementOperationArgs(PBtype): ...
class TSK_NullCommandArchive(PBtype): ...
class TSK_GroupCommitCommandArchive(PBtype): ...
class TSK_UpgradeDocPostProcessingCommandArchive(PBtype): ...
class TSK_InducedCommandCollectionCommitCommandArchive(PBtype): ...
class TSK_ActivityCommitCommandArchive(PBtype): ...
class TSK_ExecuteTestBetweenRollbackAndReapplyCommandArchive(PBtype): ...
class TSK_ChangeDocumentPackageTypeCommandArchive(PBtype): ...
class TSK_CreateLocalStorageSnapshotCommandArchive(PBtype): ...
class TSK_BlockDiffsAtCurrentRevisionCommand(PBtype): ...
class TSK_RangeAddress(PBtype): ...
class TSK_Operation(PBtype): ...
class TSK_OperationTransformer(PBtype): ...
class TSK_TransformerEntry(PBtype): ...
class TSK_OutgoingCommandQueueItem(PBtype): ...
class TSK_OutgoingCommandQueueItemUUIDToDataMapEntry(PBtype): ...
class TSK_CollaborationAppliedCommandDocumentRevisionMapping(PBtype): ...
class TSK_CollaborationDocumentSessionState(PBtype): ...
class TSK_AcknowledgementObserverEntry(PBtype): ...
class TSK_NativeContentDescription(PBtype): ...
class TSK_StructuredTextImportSettings(PBtype): ...
class TSK_OperationStorageCommandOperationsEntry(PBtype): ...
class TSK_OperationStorageEntry(PBtype): ...
class TSK_OperationStorageEntryArray(PBtype): ...
class TSK_OperationStorageEntryArraySegment(PBtype): ...
class TSK_OperationStorage(PBtype): ...
class TSK_OutgoingCommandQueue(PBtype): ...
class TSK_OutgoingCommandQueueSegment(PBtype): ...
class TSK_DataReferenceRecord(PBtype): ...
class TSK_ContainerUUIDToReferencedDataPair(PBtype): ...
class TSK_CommandAssetChunkArchive(PBtype): ...
class TSK_AssetUploadStatusCommandArchive(PBtype): ...
class TSK_AssetUploadStatusInfo(PBtype): ...
class TSK_AssetUnmaterializedOnServerCommandArchive(PBtype): ...
class TSK_PencilAnnotationUIState(PBtype): ...
class TSK_CollaboratorCursorArchive(PBtype): ...
class TSK_ActivityStreamArchive(PBtype): ...
class TSK_ActivityStreamActivityArray(PBtype): ...
class TSK_ActivityStreamActivityArraySegment(PBtype): ...
class TSK_ActivityArchive(PBtype): ...
class TSK_ActivityAuthorArchive(PBtype): ...
class TSK_CommandActivityBehaviorArchive(PBtype): ...
class TSK_ActivityCursorCollectionArchive(PBtype): ...
class TSK_ActivityCursorCollectionPersistenceWrapperArchive(PBtype): ...
class TSK_ActivityNavigationInfoArchive(PBtype): ...
class TSK_CommentActivityNavigationInfoArchive(PBtype): ...
class TSK_ActivityAuthorCacheArchive(PBtype): ...
class TSK_ShareParticipantIDCache(PBtype): ...
class TSK_PublicIDCache(PBtype): ...
class TSK_IndexCache(PBtype): ...
class TSK_FirstJoinCache(PBtype): ...
class TSK_ActivityOnlyCommandArchive(PBtype): ...
class TSK_ActivityNotificationItemArchive(PBtype): ...
class TSK_ActivityNotificationParticipantCacheArchive(PBtype): ...
class TSK_UniqueIdentifierAndAttempts(PBtype): ...
class TSK_ActivityNotificationQueueArchive(PBtype): ...
class TSK_ActivityStreamTransformationStateArchive(PBtype): ...
class TSK_ActivityStreamActivityCounterArchive(PBtype): ...
class TSK_ActionTypeCounter(PBtype): ...
class TSK_CursorTypeCounter(PBtype): ...
class TSK_ActivityStreamRemovedAuthorAuditorPendingStateArchive(PBtype): ...
class TSK_DateToAuditAndType(PBtype): ...


class TSWP_SelectionArchive(PBtype): ...
# class TSWP_ObjectAttributeTable(PBtype): ...
# class TSWP_ObjectAttribute(PBtype): ...
class TSWP_StringAttributeTable(PBtype): ...
class TSWP_StringAttribute(PBtype): ...
# class TSWP_ParaDataAttributeTable(PBtype): ...
# class TSWP_ParaDataAttribute(PBtype): ...
class TSWP_OverlappingFieldAttributeTable(PBtype): ...
class TSWP_OverlappingFieldAttribute(PBtype): ...
# class TSWP_StorageArchive(PBtype): ...
class TSWP_HighlightArchive(PBtype): ...
class TSWP_PencilAnnotationArchive(PBtype): ...
class TSWP_FontFeatureArchive(PBtype): ...
class TSWP_CharacterStylePropertiesArchive(PBtype): ...
class TSWP_CharacterStyleArchive(PBtype): ...
class TSWP_TabArchive(PBtype): ...
class TSWP_TabsArchive(PBtype): ...
class TSWP_LineSpacingArchive(PBtype): ...
class TSWP_ParagraphStylePropertiesArchive(PBtype): ...
class TSWP_ParagraphStyleArchive(PBtype): ...
class TSWP_ListStyleArchive(PBtype): ...
class TSWP_LabelGeometry(PBtype): ...
class TSWP_LabelImage(PBtype): ...
class TSWP_TextStylePresetArchive(PBtype): ...
class TSWP_ColumnsArchive(PBtype): ...
class TSWP_EqualColumnsArchive(PBtype): ...
class TSWP_NonEqualColumnsArchive(PBtype): ...
class TSWP_GapWidthArchive(PBtype): ...
class TSWP_PaddingArchive(PBtype): ...
class TSWP_ColumnStylePropertiesArchive(PBtype): ...
class TSWP_ColumnStyleArchive(PBtype): ...
class TSWP_ShapeStylePropertiesArchive(PBtype): ...
class TSWP_ShapeStyleArchive(PBtype): ...
class TSWP_ThemePresetsArchive(PBtype): ...
class TSWP_TextPresetDisplayItemArchive(PBtype): ...
class TSWP_TOCEntryStylePropertiesArchive(PBtype): ...
class TSWP_TOCEntryStyleArchive(PBtype): ...
class TSWP_TOCSettingsArchive(PBtype): ...
class TSWP_TOCEntryData(PBtype): ...
class TSWP_TOCEntryInstanceArchive(PBtype): ...
class TSWP_UndoTransaction(PBtype): ...
class TSWP_GenericTransaction(PBtype): ...
class TSWP_TextTransaction(PBtype): ...
class TSWP_CharIndexTransaction(PBtype): ...
class TSWP_ReplaceCharIndexTransaction(PBtype): ...
class TSWP_AttributeIndexTransaction(PBtype): ...
class TSWP_InsertAttributeTransaction(PBtype): ...
class TSWP_InsertNilTransaction(PBtype): ...
class TSWP_CharDeltaTransaction(PBtype): ...
class TSWP_ParagraphDataTransaction(PBtype): ...
class TSWP_ObjectDOLCTransaction(PBtype): ...
class TSWP_CTDateTransaction(PBtype): ...
class TSWP_UnionTransaction(PBtype): ...
class TSWP_StorageAction(PBtype): ...
class TSWP_StorageActionGroup(PBtype): ...
class TSWP_UndoTransactionWrapperArchive(PBtype): ...
class TSWP_ShapeInfoArchive(PBtype): ...
class TSWP_CommentInfoArchive(PBtype): ...
class TSWP_TOCInfoArchive(PBtype): ...
class TSWP_TOCLayoutHintArchive(PBtype): ...
class TSWP_EquationInfoArchive(PBtype): ...
class TSWP_TextualAttachmentArchive(PBtype): ...
class TSWP_TSWPTOCPageNumberAttachmentArchive(PBtype): ...
class TSWP_UIGraphicalAttachment(PBtype): ...
class TSWP_DrawableAttachmentArchive(PBtype): ...
class TSWP_TOCAttachmentArchive(PBtype): ...
class TSWP_FootnoteReferenceAttachmentArchive(PBtype): ...
class TSWP_NumberAttachmentArchive(PBtype): ...
class TSWP_SmartFieldArchive(PBtype): ...
class TSWP_HyperlinkFieldArchive(PBtype): ...
class TSWP_PlaceholderSmartFieldArchive(PBtype): ...
class TSWP_UnsupportedHyperlinkFieldArchive(PBtype): ...
class TSWP_BibliographySmartFieldArchive(PBtype): ...
class TSWP_CitationRecordArchive(PBtype): ...
class TSWP_CitationSmartFieldArchive(PBtype): ...
class TSWP_DateTimeSmartFieldArchive(PBtype): ...
class TSWP_BookmarkFieldArchive(PBtype): ...
class TSWP_FilenameSmartFieldArchive(PBtype): ...
class TSWP_MergeFieldTypeArchive(PBtype): ...
class TSWP_MergeSmartFieldArchive(PBtype): ...
class TSWP_TOCSmartFieldArchive(PBtype): ...
class TSWP_TOCEntry(PBtype): ...
class TSWP_RubyFieldArchive(PBtype): ...
class TSWP_TateChuYokoFieldArchive(PBtype): ...
class TSWP_ChangeArchive(PBtype): ...
class TSWP_ChangeSessionArchive(PBtype): ...
class TSWP_SectionPlaceholderArchive(PBtype): ...
class TSWP_HyperlinkSelectionArchive(PBtype): ...
class TSWP_DateTimeSelectionArchive(PBtype): ...
class TSWP_FlowInfoArchive(PBtype): ...
class TSWP_FlowInfoContainerArchive(PBtype): ...
class TSWP_DropCapArchive(PBtype): ...
class TSWP_DropCapStylePropertiesArchive(PBtype): ...
class TSWP_DropCapStyleArchive(PBtype): ...
class TSWP_CollaboratorTextCursorSubselectionArchive(PBtype): ...

class KN_AnimationAttributesArchive(PBtype): ...
class KN_TransitionAttributesArchive(PBtype): ...
class KN_TransitionArchive(PBtype): ...
class KN_BuildChunkArchive(PBtype): ...
class KN_BuildChunkIdentifierArchive(PBtype): ...
class KN_BuildAttributeValueArchive(PBtype): ...
class KN_BuildAttributeTupleArchive(PBtype): ...
class KN_BuildAttributesArchive(PBtype): ...
class KN_BuildArchive(PBtype): ...
class KN_PlaceholderArchive(PBtype): ...
class KN_NoteArchive(PBtype): ...
class KN_ClassicStylesheetRecordArchive(PBtype): ...
class KN_ClassicThemeRecordArchive(PBtype): ...
class KN_SlideArchive(PBtype): ...
class KN_SageTagMapEntry(PBtype): ...
class KN_InstructionalTextMap(PBtype): ...
class KN_InstructionalTextMapEntry(PBtype): ...
# class KN_SlideNodeArchive(PBtype): ...
class KN_SlideSpecificHyperlinkMapEntry(PBtype): ...
class KN_DesktopUILayoutArchive(PBtype): ...
class KN_UIStateArchive(PBtype): ...
class KN_IOSRestorableViewStateRootArchive(PBtype): ...
class KN_IOSSavedPlaybackStateArchive(PBtype): ...
class KN_CanvasSelectionArchive(PBtype): ...
class KN_ActionGhostSelectionArchive(PBtype): ...
class KN_ThemeCustomTimingCurveArchive(PBtype): ...
class KN_ThemeArchive(PBtype): ...
# class KN_SlideTreeArchive(PBtype): ...
# class KN_ShowArchive(PBtype): ...
# class KN_DocumentArchive(PBtype): ...
class KN_SlideStylePropertiesArchive(PBtype): ...
class KN_SlideStyleArchive(PBtype): ...
class KN_PasteboardNativeStorageArchive(PBtype): ...
class KN_LiveVideoSourcePair(PBtype): ...
class KN_PrototypeForUndoTemplateChangeArchive(PBtype): ...
class KN_RecordingArchive(PBtype): ...
class KN_RecordingSyncState(PBtype): ...
class KN_RecordingCorrectionHistory(PBtype): ...
class KN_RecordingEventTrackArchive(PBtype): ...
class KN_RecordingEventArchive(PBtype): ...
class KN_RecordingNavigationEventArchive(PBtype): ...
class KN_RecordingLaserEventArchive(PBtype): ...
class KN_RecordingPauseEventArchive(PBtype): ...
class KN_RecordingMovieEventArchive(PBtype): ...
class KN_RecordingMovieTrackArchive(PBtype): ...
class KN_MovieSegmentArchive(PBtype): ...
class KN_Soundtrack(PBtype): ...
class KN_SlideNumberAttachmentArchive(PBtype): ...
class KN_SlideCollectionSelectionArchive(PBtype): ...
class KN_OutlineSelection(PBtype): ...
class KN_PresenterNotesSelectionArchive(PBtype): ...
class KN_MixedIdOperationArgs(PBtype): ...
class KN_LiveVideoInfo(PBtype): ...
class KN_LiveVideoSource(PBtype): ...
class KN_LiveVideoSourceCollaborationCommandUsageState(PBtype): ...
class KN_LiveVideoCaptureDeviceDescription(PBtype): ...
class KN_LiveVideoSourceCollection(PBtype): ...
class KN_LiveVideoSourceUsageEntry(PBtype): ...
class KN_MotionBackgroundStylePropertiesArchive(PBtype): ...
class KN_MotionBackgroundStyleArchive(PBtype): ...
class KN_MotionBackgroundFillArchive(PBtype): ...


class TSD_EdgeInsetsArchive(PBtype): ...
class TSD_GeometryArchive(PBtype): ...
class TSD_PointPathSourceArchive(PBtype): ...
class TSD_ScalarPathSourceArchive(PBtype): ...
class TSD_BezierPathSourceArchive(PBtype): ...
class TSD_CalloutPathSourceArchive(PBtype): ...
class TSD_ConnectionLinePathSourceArchive(PBtype): ...
class TSD_EditableBezierPathSourceArchive(PBtype): ...
class TSD_Node(PBtype): ...
class TSD_Subpath(PBtype): ...
class TSD_PathSourceArchive(PBtype): ...
class TSD_AngleGradientArchive(PBtype): ...
class TSD_TransformGradientArchive(PBtype): ...
class TSD_GradientArchive(PBtype): ...
class TSD_GradientStop(PBtype): ...
class TSD_ImageFillArchive(PBtype): ...
class TSD_FillArchive(PBtype): ...
class TSD_StrokePatternArchive(PBtype): ...
class TSD_StrokeArchive(PBtype): ...
class TSD_SmartStrokeArchive(PBtype): ...
class TSD_FrameArchive(PBtype): ...
class TSD_PatternedStrokeArchive(PBtype): ...
class TSD_LineEndArchive(PBtype): ...
class TSD_ShadowArchive(PBtype): ...
class TSD_DropShadowArchive(PBtype): ...
class TSD_ContactShadowArchive(PBtype): ...
class TSD_CurvedShadowArchive(PBtype): ...
class TSD_ReflectionArchive(PBtype): ...
class TSD_ImageAdjustmentsArchive(PBtype): ...
class TSD_ShapeStylePropertiesArchive(PBtype): ...
class TSD_ShapeStyleArchive(PBtype): ...
class TSD_MediaStylePropertiesArchive(PBtype): ...
class TSD_MediaStyleArchive(PBtype): ...
class TSD_ThemePresetsArchive(PBtype): ...
class TSD_ThemeReplaceFillPresetCommandArchive(PBtype): ...
class TSD_DrawableArchive(PBtype): ...
class TSD_ContainerArchive(PBtype): ...
class TSD_GroupArchive(PBtype): ...
class TSD_FreehandDrawingAnimationArchive(PBtype): ...
class TSD_FreehandDrawingArchive(PBtype): ...
class TSD_ShapeArchive(PBtype): ...
class TSD_ConnectionLineArchive(PBtype): ...
class TSD_ImageArchive(PBtype): ...
class TSD_MaskArchive(PBtype): ...
class TSD_ImageDataAttributes(PBtype): ...
class TSD_MovieArchive(PBtype): ...
class TSD_ExteriorTextWrapArchive(PBtype): ...
class TSD_DrawableContentDescription(PBtype): ...
class TSD_FreehandDrawingContentDescription(PBtype): ...
class TSD_FreehandDrawingToolkitUIState(PBtype): ...
class TSD_StandinCaptionArchive(PBtype): ...
class TSD_GuideArchive(PBtype): ...
class TSD_UserDefinedGuideArchive(PBtype): ...
class TSD_GuideStorageArchive(PBtype): ...
class TSD_CanvasSelectionArchive(PBtype): ...
class TSD_DrawableSelectionArchive(PBtype): ...
class TSD_GroupSelectionArchive(PBtype): ...
class TSD_PathSelectionArchive(PBtype): ...
class TSD_InfoHyperlinkSelectionArchive(PBtype): ...
class TSD_CommentStorageArchive(PBtype): ...
class TSD_ReplaceAnnotationAuthorCommandArchive(PBtype): ...
class TSD_PencilAnnotationArchive(PBtype): ...
class TSD_PencilAnnotationSelectionArchive(PBtype): ...
class TSD_PencilAnnotationStorageArchive(PBtype): ...
class TSD_SpecColorFillSetColorArchive(PBtype): ...
class TSD_SpecFrameSetAssetScaleArchive(PBtype): ...
class TSD_SpecGradientFillSetAngleArchive(PBtype): ...
class TSD_SpecImageFillSetTechniqueArchive(PBtype): ...
class TSD_SpecReflectionSetOpacityArchive(PBtype): ...
class TSD_SpecShadowSetAngleArchive(PBtype): ...
class TSD_SpecShadowSetColorArchive(PBtype): ...
class TSD_SpecShadowSetOffsetArchive(PBtype): ...
class TSD_SpecShadowSetOpacityArchive(PBtype): ...
class TSD_SpecShadowSetRadiusArchive(PBtype): ...
class TSD_SpecStrokeSetColorArchive(PBtype): ...
class TSD_SpecStrokeSetPatternArchive(PBtype): ...
class TSD_SpecStrokeSetWidthArchive(PBtype): ...
class TSD_Attribution(PBtype): ...
class TSD_MovieFingerprint(PBtype): ...
class TSD_MovieFingerprintTrack(PBtype): ...


class TSCH_ChartDrawableArchive(PBtype): ...
class TSCH_ChartArchive(PBtype): ...
class TSCH_ChartMultiDataIndexUpgrade(PBtype): ...
class TSCH_ChartGarlicMinMaxUpgrade(PBtype): ...
class TSCH_ChartGarlicLabelFormatUpgrade(PBtype): ...
class TSCH_ChartPasteboardAdditionsArchive(PBtype): ...
class TSCH_ChartPreserveAppearanceForPresetArchive(PBtype): ...
class TSCH_ChartSupportsProportionalBendedCalloutLinesArchive(PBtype): ...
class TSCH_ChartSupportsRoundedCornersArchive(PBtype): ...
class TSCH_ChartSupportsSeriesPropertySpacingArchive(PBtype): ...
class TSCH_ChartSupportsStackedSummaryLabelsArchive(PBtype): ...
class TSCH_ChartGridArchive(PBtype): ...
class TSCH_ChartGridRowColumnIdMap(PBtype): ...
class TSCH_Entry(PBtype): ...
class TSCH_ChartMediatorArchive(PBtype): ...
class TSCH_ChartFillSetArchive(PBtype): ...
class TSCH_ChartStylePreset(PBtype): ...
class TSCH_ChartPresetsArchive(PBtype): ...
class TSCH_PropertyValueStorageContainerArchive(PBtype): ...
class TSCH_StylePasteboardDataArchive(PBtype): ...
class TSCH_ChartSelectionPathTypeArchive(PBtype): ...
class TSCH_ChartAxisIDArchive(PBtype): ...
class TSCH_ChartSelectionPathArgumentArchive(PBtype): ...
class TSCH_ChartSelectionPathArchive(PBtype): ...
class TSCH_ChartSelectionArchive(PBtype): ...
class TSCH_ChartCDESelectionArchive(PBtype): ...
class TSCH_ChartUIState(PBtype): ...
class TSCH_ChartUIStateMultiDataIndexUpgrade(PBtype): ...
class TSCH_ChartFormatStructExtensions(PBtype): ...
class TSCH_ChartReferenceLineNonStyleItem(PBtype): ...
class TSCH_ChartAxisReferenceLineNonStylesArchive(PBtype): ...
class TSCH_ChartAxisReferenceLineStylesArchive(PBtype): ...
class TSCH_ChartReferenceLinesArchive(PBtype): ...
class TSCH_ChartPresetReferenceLineStylesArchive(PBtype): ...
class TSCH_ChartAxisReferenceLineSparseNonStylesArchive(PBtype): ...
class TSCH_PropertyValueStorageContainerReferenceLinesArchive(PBtype): ...
class TSCH_CollaboratorCDECursorSubselectionArchive(PBtype): ...
class TSCH_CollaboratorChartTitleCursorSubselectionArchive(PBtype): ...

# fmt: on


ArchiveObject = Union[*PBtype.__subclasses__()]  # type: ignore


class Archive(Struct, **KW):
    """Archive in a chunk."""

    header: TSP_ArchiveInfo
    objects: list[ArchiveObject]

    _store: ClassVar[dict[str, Archive]] = {}

    def __post_init__(self):
        Archive._store[self.header.identifier] = self

    def next_object_of_type(self, type_: type[ArchObj]) -> ArchObj:
        return next(obj for obj in self.objects if isinstance(obj, type_))


class Chunk(Struct, **KW):
    """Chunk in a protobuf file."""

    archives: list[Archive]

    def next_object_of_type(self, type_: type[ArchObj]) -> ArchObj:
        for archive in self.archives:
            return next(obj for obj in archive.objects if isinstance(obj, type_))


class Document(Chunk):
    @property
    def document_archive(self) -> KN_DocumentArchive:
        return self.next_object_of_type(KN_DocumentArchive)

    def show(self) -> KN_ShowArchive:
        return self.document_archive.get_show()

    def slide_nodes(self) -> Iterator[KN_SlideNodeArchive]:
        for slide_id in self.show().slideTree.slides:
            with suppress(StopIteration):
                yield slide_id.archive().next_object_of_type(KN_SlideNodeArchive)


class Metadata(Chunk):
    @property
    def package_metadata(self) -> TSP_PackageMetadata:
        return self.next_object_of_type(TSP_PackageMetadata)


class Slide(Chunk):
    number: int
    _node_archive: KN_SlideNodeArchive
    _keynote: KeynoteFile

    @property
    def identifier(self) -> int:
        return self.archives[0].header.identifier

    @property
    def thumbnail_digest(self) -> str:
        return self._thumbnail_data.digest

    @property
    def _thumbnail_data(self) -> DataItem:
        thumb_id = self._node_archive.thumbnails[0].identifier
        return self._keynote.metadata.package_metadata.get_data_item(thumb_id)

    @property
    def safe_thumb_hash(self) -> str:
        return _safe_hash(self.thumbnail_digest)

    @property
    def thumbnail_bytes(self) -> bytes:
        return self._keynote.zip.read(f"Data/{self._thumbnail_data.fileName}")

    @property
    def text_blocks(self) -> list[str]:
        return [
            val
            for archive in self.archives
            for obj in archive.objects
            if isinstance(obj, TSWP_StorageArchive)
            and (val := "\n".join(obj.text).strip("\n\ufffc "))
        ]

    @property
    def presenter_notes(self) -> str:
        for archive in self.archives:
            for obj in archive.objects:
                if isinstance(obj, TSWP_StorageArchive) and obj.kind == "NOTE":
                    return "\n".join(obj.text).strip("\n\ufffc ")
        return ""

    def record(self) -> dict:
        return {
            "slide_number": self.number,
            "text_blocks": "\n".join(self.text_blocks),
            "presenter_notes": self.presenter_notes,
            "thumb_digest": self.safe_thumb_hash,
            "is_skipped": self._node_archive.isSkipped,
            "id": self._keynote.slide_uuid(self.identifier),
            "slide_ident": self.identifier,
        }


class KeynoteFile:
    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path).expanduser().absolute()
        self._slides: dict[str, Slide] = {}
        try:
            self.zip = ZipFile(self.path, "r")
        except Exception as e:
            raise type(e)(f"Could not open {self.path}: {e}") from e

    @cached_property
    def document_identifier(self) -> UUID:
        return uuid.UUID(self.zip.read("Metadata/DocumentIdentifier").decode("utf-8"))

    @cached_property
    def revision(self) -> UUID | None:
        return self.metadata.package_metadata.revision.identifier

    @cached_property
    def file_format_version(self) -> Ver:
        return self.metadata.package_metadata.fileFormatVersion

    @cached_property
    def document(self) -> Document:
        return convert(self._iwa_to_dict("Index/Document.iwa"), Document, strict=False)

    @cached_property
    def metadata(self) -> Metadata:
        return convert(self._iwa_to_dict("Index/Metadata.iwa"), Metadata, strict=False)

    def slide_uuid(self, slide_id: int):
        return _global_slide_uuid(self, slide_id)

    @cached_property
    def slides(self) -> list[Slide]:
        slides = []
        for i, node in enumerate(self.document.slide_nodes()):
            slide_id = node.slide.identifier
            comp = self.metadata.package_metadata.get_component(slide_id)
            slide_path = f"Index/{comp.locator or comp.preferredLocator}.iwa"
            try:
                data = self._iwa_to_dict(slide_path)
                data.update(
                    number=i,
                    _keynote=self,
                    _node_archive=node,
                    uuid=_global_slide_uuid(self, slide_id),
                )

                slides.append(convert(data, Slide, strict=False))
            except Exception as e:
                logging.warn(f"Error reading slide {i} in {self.path}: {str(e)[:100]}")
        return slides

    def __enter__(self) -> KeynoteFile:
        return self

    def __exit__(self, *_) -> None:
        self.zip.close()

    def _iwa_to_dict(self, path: str) -> dict:
        return IWAFile.from_buffer(self.zip.read(path)).chunks[0].to_dict()

    def export_thumbnails(self, dest: str | os.PathLike) -> None:
        dest = Path(dest).expanduser().absolute()
        dest.mkdir(exist_ok=True)
        for slide in self.slides:
            with suppress(KeyError):
                thumb_path = dest / f"{slide.safe_thumb_hash}.jpg"
                thumb_path.write_bytes(slide.thumbnail_bytes)

    def record(self) -> dict:
        path = str(self.path).split("Dropbox (HMS)")[-1]
        return {
            "path": path,
            "id": str(self.document_identifier),
            "revision": str(self.revision),
            "file_format_version": str(self.file_format_version),
            "slides": [slide.record() for slide in self.slides],
        }


def _global_slide_uuid(kf: KeynoteFile, slide_id: int) -> str:
    combo = str(kf.document_identifier) + str(kf.revision) + str(slide_id)
    # Step 2: Hash the combined string using SHA-256
    hash_object = sha256(combo.encode("utf-8"))
    hash_bytes = hash_object.digest()[:16]
    return base64.urlsafe_b64encode(hash_bytes).rstrip(b"=").decode("utf-8")


def _safe_hash(data: str) -> str:
    return data.replace("/", "_").replace("+", "-").replace("=", "")
