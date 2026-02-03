from typing import List, Optional
from pydantic import BaseModel, Field

class ScriptureReference(BaseModel):
    book: str = ""
    book_zh: str = ""
    chapter: int = 0
    verse_start: int = 0
    verse_end: int = 0
    reference: str = ""
    reference_zh: str = ""

class SeriesInfo(BaseModel):
    name: str = ""
    name_en: str = ""
    number: int = 0
    total_in_series: int = 0

class AudioMetadata(BaseModel):
    format: str = "mp3"
    bitrate: int = 0
    sample_rate: int = 0
    channels: int = 0
    duration_seconds: int = 0

class Sermon(BaseModel):
    id: str
    original_path: str
    new_path: Optional[str] = None
    audio_hash: Optional[str] = None
    title: str
    title_en: str = ""
    date: str = ""  # YYYY-MM-DD
    duration_seconds: int = 0
    file_size_bytes: int = 0
    language: str = "zh"
    series: SeriesInfo = Field(default_factory=SeriesInfo)
    scripture_references: List[ScriptureReference] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    audio_metadata: AudioMetadata = Field(default_factory=AudioMetadata)

class PreacherInfo(BaseModel):
    name: str
    name_en: str = ""
    language: str = "zh"
    total_sermons: int = 0

class PreacherMetadata(BaseModel):
    preacher: PreacherInfo
    last_updated: str = ""
    sermons: dict[str, Sermon] = Field(default_factory=dict)
