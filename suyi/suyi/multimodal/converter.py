"""Multimodal format converter — base64 encode/decode and MIME conversion.

Provides utilities to convert between raw bytes, base64 strings, and data URIs.
These are commonly needed when interfacing with vision/audio APIs.

Usage::

    from suyi.multimodal import FormatConverter

    # Encode bytes to base64
    b64 = FormatConverter.to_base64(b"\\x89PNG...")

    # Decode base64
    data = FormatConverter.from_base64(b64)

    # Create a data URI
    uri = FormatConverter.to_data_uri(b"\\x89PNG...", "image/png")

    # Parse a data URI
    mime, data = FormatConverter.from_data_uri(uri)

    # Convert between MIME types
    new_mime = FormatConverter.convert_mime("image/jpeg", "image/png")
"""

from __future__ import annotations

import base64
import mimetypes
import os
from typing import Any, Dict, Optional, Tuple, Union

from .base import MediaContent, ModalityType, _MIME_MAP, _EXT_MAP


class FormatConverter:
    """Convert between media formats (bytes, base64, data URIs, MIME types)."""

    # ── base64 ────────────────────────────────────────────────

    @staticmethod
    def to_base64(data: bytes) -> str:
        """Encode bytes to a base64 string."""
        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def from_base64(b64_str: str) -> bytes:
        """Decode a base64 string to bytes.

        Handles both standard and URL-safe base64, with or without padding.
        """
        # Remove potential data URI prefix
        if b64_str.startswith("data:"):
            _, b64_str = FormatConverter.from_data_uri(b64_str)

        # Fix padding
        padding = 4 - len(b64_str) % 4
        if padding != 4:
            b64_str += "=" * padding

        try:
            return base64.b64decode(b64_str)
        except Exception:
            # Try URL-safe decoding
            return base64.urlsafe_b64decode(b64_str)

    # ── data URI ───────────────────────────────────────────────

    @staticmethod
    def to_data_uri(
        data: bytes,
        mime_type: str = "application/octet-stream",
        base64_encode: bool = True,
    ) -> str:
        """Create a data URI from bytes.

        Format: ``data:<mime>;base64,<encoded_data>``
        """
        if base64_encode:
            b64 = FormatConverter.to_base64(data)
            return f"data:{mime_type};base64,{b64}"
        else:
            text = data.decode("utf-8", errors="replace")
            return f"data:{mime_type},{text}"

    @staticmethod
    def from_data_uri(uri: str) -> Tuple[str, bytes]:
        """Parse a data URI into (mime_type, data).

        Returns:
            Tuple of (mime_type, raw_bytes).
        """
        if not uri.startswith("data:"):
            raise ValueError(f"Not a data URI: {uri[:30]}...")

        # data:<mime>;base64,<data>  or  data:<mime>,<data>
        header, _, payload = uri.partition(",")

        # Extract mime type
        # header = "data:image/png;base64" or "data:text/plain"
        meta = header[5:]  # strip "data:"
        if ";base64" in meta:
            mime_type = meta.replace(";base64", "")
            data = base64.b64decode(payload)
        elif ";charset=" in meta:
            mime_type = meta.split(";")[0]
            data = payload.encode("utf-8")
        else:
            mime_type = meta
            data = payload.encode("utf-8")

        return mime_type, data

    # ── MIME conversion ────────────────────────────────────────

    @staticmethod
    def mime_to_extension(mime_type: str) -> str:
        """Convert a MIME type to a file extension (with leading dot)."""
        ext = _EXT_MAP.get(mime_type)
        if ext:
            return ext
        # Try mimetypes as fallback
        ext = mimetypes.guess_extension(mime_type)
        return ext or ".bin"

    @staticmethod
    def extension_to_mime(ext: str) -> str:
        """Convert a file extension to a MIME type."""
        if not ext.startswith("."):
            ext = "." + ext
        ext = ext.lower()
        return _MIME_MAP.get(ext, "application/octet-stream")

    @staticmethod
    def convert_mime(
        data: bytes,
        source_mime: str,
        target_mime: str,
    ) -> Tuple[str, bytes]:
        """Convert media data between MIME types.

        Note: This only updates the MIME type label — it does NOT transcode
        the actual media data.  Real transcoding would require external
        libraries (Pillow, ffmpeg, etc.).

        Returns:
            Tuple of (target_mime, data).
        """
        # For now, we only support same-type conversion (just relabel)
        source_main = source_mime.split("/")[0]
        target_main = target_mime.split("/")[0]

        if source_main != target_main:
            raise ValueError(
                f"Cannot convert between different modality types: "
                f"{source_mime} → {target_mime}"
            )

        return target_mime, data

    # ── MediaContent helpers ──────────────────────────────────

    @staticmethod
    def media_to_base64(media: MediaContent) -> str:
        """Convert a MediaContent to a base64 string."""
        return media.get_base64()

    @staticmethod
    def media_to_data_uri(media: MediaContent) -> str:
        """Convert a MediaContent to a data URI."""
        return FormatConverter.to_data_uri(
            media.get_data(),
            media.mime_type or "application/octet-stream",
        )

    @staticmethod
    def base64_to_media(
        b64_str: str,
        modality: ModalityType = ModalityType.IMAGE,
        mime_type: str = "application/octet-stream",
    ) -> MediaContent:
        """Convert a base64 string to a MediaContent."""
        return MediaContent.from_base64(b64_str, modality, mime_type)

    @staticmethod
    def data_uri_to_media(uri: str) -> MediaContent:
        """Convert a data URI to a MediaContent."""
        mime, data = FormatConverter.from_data_uri(uri)
        modality = _mime_to_modality(mime)
        return MediaContent.from_bytes(data, modality, mime)

    # ── batch ──────────────────────────────────────────────────

    @staticmethod
    def batch_to_base64(items: list[MediaContent]) -> list[str]:
        """Convert a list of MediaContent to base64 strings."""
        return [item.get_base64() for item in items]

    @staticmethod
    def batch_to_data_uris(items: list[MediaContent]) -> list[str]:
        """Convert a list of MediaContent to data URIs."""
        return [FormatConverter.media_to_data_uri(item) for item in items]


def _mime_to_modality(mime_type: str) -> ModalityType:
    """Map a MIME type to a ModalityType."""
    main = mime_type.split("/")[0]
    if main == "image":
        return ModalityType.IMAGE
    elif main == "audio":
        return ModalityType.AUDIO
    elif main == "video":
        return ModalityType.VIDEO
    return ModalityType.TEXT
