"""Multimodal input — unified input format for text, image, audio, and video.

This module defines the :class:`MultimodalInput` dataclass that unifies
different input modalities into a single representation.  It is designed to
be extensible: new modality types can be added without breaking existing
code.

Usage::

    from suyi.multimodal import MultimodalInput, ModalityType

    # Text-only
    inp = MultimodalInput.from_text("Hello, world!")

    # Image from file
    inp = MultimodalInput.from_image("/path/to/image.png")

    # Mixed input
    inp = MultimodalInput(
        text="What's in this image?",
        images=[ImageContent.from_file("photo.jpg")],
    )
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class ModalityType(str, Enum):
    """Supported modality types."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


@dataclass
class MediaContent:
    """A single media item (image, audio, or video).

    Attributes:
        modality: The modality type.
        data: Raw binary data (bytes), or None if using a file path.
        file_path: Path to the media file (alternative to ``data``).
        mime_type: MIME type (e.g. ``image/png``).
        base64_data: Base64-encoded string (lazily computed).
        metadata: Additional metadata (dimensions, duration, etc.).
    """

    modality: ModalityType = ModalityType.IMAGE
    data: Optional[bytes] = None
    file_path: Optional[str] = None
    mime_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    # base64 is computed on demand
    _base64_cache: Optional[str] = field(default=None, repr=False)

    @classmethod
    def from_file(
        cls,
        file_path: str,
        modality: Optional[ModalityType] = None,
        mime_type: Optional[str] = None,
    ) -> "MediaContent":
        """Create a MediaContent from a file path.

        The file is NOT read immediately — data is loaded lazily when
        :meth:`get_data` or :meth:`get_base64` is called.
        """
        detected = modality or _detect_modality(file_path)
        detected_mime = mime_type or _guess_mime(file_path)
        return cls(
            modality=detected,
            file_path=file_path,
            mime_type=detected_mime,
        )

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        modality: ModalityType = ModalityType.IMAGE,
        mime_type: str = "application/octet-stream",
    ) -> "MediaContent":
        """Create a MediaContent from raw bytes."""
        return cls(
            modality=modality,
            data=data,
            mime_type=mime_type,
        )

    @classmethod
    def from_base64(
        cls,
        b64_str: str,
        modality: ModalityType = ModalityType.IMAGE,
        mime_type: str = "application/octet-stream",
    ) -> "MediaContent":
        """Create a MediaContent from a base64-encoded string."""
        data = base64.b64decode(b64_str)
        return cls(
            modality=modality,
            data=data,
            mime_type=mime_type,
        )

    def get_data(self) -> bytes:
        """Return the raw binary data, loading from file if necessary."""
        if self.data is not None:
            return self.data
        if self.file_path and os.path.isfile(self.file_path):
            with open(self.file_path, "rb") as f:
                self.data = f.read()
            return self.data
        return b""

    def get_base64(self) -> str:
        """Return base64-encoded data string."""
        if self._base64_cache is not None:
            return self._base64_cache
        data = self.get_data()
        self._base64_cache = base64.b64encode(data).decode("ascii")
        return self._base64_cache

    def get_size(self) -> int:
        """Return the size of the media data in bytes."""
        if self.data is not None:
            return len(self.data)
        if self.file_path and os.path.isfile(self.file_path):
            return os.path.getsize(self.file_path)
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modality": self.modality.value,
            "file_path": self.file_path,
            "mime_type": self.mime_type,
            "size": self.get_size(),
            "metadata": dict(self.metadata),
        }

    def __repr__(self) -> str:
        return (
            f"MediaContent(modality={self.modality.value!r}, "
            f"mime={self.mime_type!r}, size={self.get_size()})"
        )


# Alias for backward compat
ImageContent = MediaContent
AudioContent = MediaContent
VideoContent = MediaContent


@dataclass
class MultimodalInput:
    """Unified multimodal input container.

    Attributes:
        text: Text content (may be empty).
        images: List of image content.
        audio: List of audio content.
        video: List of video content.
        metadata: Additional input metadata.
    """

    text: str = ""
    images: List[MediaContent] = field(default_factory=list)
    audio: List[MediaContent] = field(default_factory=list)
    video: List[MediaContent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── factory methods ──────────────────────────────────────

    @classmethod
    def from_text(cls, text: str, **metadata: Any) -> "MultimodalInput":
        """Create a text-only input."""
        return cls(text=text, metadata=dict(metadata))

    @classmethod
    def from_image(
        cls,
        file_path: Optional[str] = None,
        data: Optional[bytes] = None,
        text: str = "",
        **metadata: Any,
    ) -> "MultimodalInput":
        """Create an image input."""
        if file_path:
            img = MediaContent.from_file(file_path, ModalityType.IMAGE)
        elif data is not None:
            img = MediaContent.from_bytes(data, ModalityType.IMAGE)
        else:
            raise ValueError("Either file_path or data must be provided.")
        return cls(text=text, images=[img], metadata=dict(metadata))

    @classmethod
    def from_audio(
        cls,
        file_path: Optional[str] = None,
        data: Optional[bytes] = None,
        text: str = "",
        **metadata: Any,
    ) -> "MultimodalInput":
        """Create an audio input."""
        if file_path:
            aud = MediaContent.from_file(file_path, ModalityType.AUDIO)
        elif data is not None:
            aud = MediaContent.from_bytes(data, ModalityType.AUDIO)
        else:
            raise ValueError("Either file_path or data must be provided.")
        return cls(text=text, audio=[aud], metadata=dict(metadata))

    # ── queries ───────────────────────────────────────────────

    def get_modalities(self) -> List[ModalityType]:
        """Return list of modalities present in this input."""
        modalities: List[ModalityType] = []
        if self.text:
            modalities.append(ModalityType.TEXT)
        if self.images:
            modalities.append(ModalityType.IMAGE)
        if self.audio:
            modalities.append(ModalityType.AUDIO)
        if self.video:
            modalities.append(ModalityType.VIDEO)
        return modalities

    def is_text_only(self) -> bool:
        """Whether this input contains only text."""
        return bool(self.text) and not self.images and not self.audio and not self.video

    def is_multimodal(self) -> bool:
        """Whether this input contains more than one modality."""
        return len(self.get_modalities()) > 1

    def total_size(self) -> int:
        """Return total size of all media in bytes."""
        total = 0
        for item in self.images + self.audio + self.video:
            total += item.get_size()
        return total

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "images": [img.to_dict() for img in self.images],
            "audio": [aud.to_dict() for aud in self.audio],
            "video": [vid.to_dict() for vid in self.video],
            "modalities": [m.value for m in self.get_modalities()],
            "total_size": self.total_size(),
            "metadata": dict(self.metadata),
        }

    def __repr__(self) -> str:
        mods = [m.value for m in self.get_modalities()]
        return f"MultimodalInput(modalities={mods}, text_len={len(self.text)})"


# ── helpers ───────────────────────────────────────────────────

_MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
}

_EXT_MAP = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "audio/wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/flac": ".flac",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
}


def _guess_mime(file_path: str) -> str:
    """Guess MIME type from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    return _MIME_MAP.get(ext, "application/octet-stream")


def _detect_modality(file_path: str) -> ModalityType:
    """Detect modality from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"):
        return ModalityType.IMAGE
    if ext in (".wav", ".mp3", ".flac", ".ogg", ".aac", ".m4a"):
        return ModalityType.AUDIO
    if ext in (".mp4", ".webm", ".avi", ".mov", ".mkv"):
        return ModalityType.VIDEO
    return ModalityType.TEXT
