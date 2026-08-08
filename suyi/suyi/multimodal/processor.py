"""Multimodal input processor — format detection, size validation, MIME handling.

The :class:`InputProcessor` takes raw user input (files, bytes, text) and
produces a validated :class:`~.base.MultimodalInput` instance.

Usage::

    from suyi.multimodal import InputProcessor

    proc = InputProcessor(max_size_mb=10)
    result = proc.process_files(["image.png", "audio.mp3"], text="Describe this")
    print(result.input)
    print(result.warnings)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .base import (
    MediaContent,
    ModalityType,
    MultimodalInput,
    _detect_modality,
    _guess_mime,
    _MIME_MAP,
)


class ValidationError(Exception):
    """Raised when input validation fails."""


@dataclass
class ProcessResult:
    """Result of processing multimodal input.

    Attributes:
        input: The validated :class:`MultimodalInput`.
        warnings: List of warning messages (non-fatal issues).
        errors: List of error messages (fatal issues that prevented processing).
    """

    input: MultimodalInput
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input": self.input.to_dict(),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "is_valid": self.is_valid,
        }


class InputProcessor:
    """Process and validate multimodal input.

    Attributes:
        max_size_bytes: Maximum allowed size per file in bytes.
        allowed_mime_types: Set of allowed MIME types (empty = all allowed).
        allowed_modalities: Set of allowed modalities (empty = all allowed).
    """

    def __init__(
        self,
        max_size_mb: float = 20.0,
        allowed_mime_types: Optional[set] = None,
        allowed_modalities: Optional[set] = None,
    ) -> None:
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.allowed_mime_types = allowed_mime_types or set()
        self.allowed_modalities = allowed_modalities or set()

    # ── validation ────────────────────────────────────────────

    def validate_file(self, file_path: str) -> Tuple[bool, List[str]]:
        """Validate a single file.

        Returns:
            (is_valid, list_of_issues) — issues may be warnings or errors.
        """
        issues: List[str] = []

        if not os.path.exists(file_path):
            return False, [f"File not found: {file_path}"]

        if not os.path.isfile(file_path):
            return False, [f"Not a file: {file_path}"]

        size = os.path.getsize(file_path)
        if size > self.max_size_bytes:
            issues.append(
                f"File too large: {size} bytes (max {self.max_size_bytes})"
            )

        mime = _guess_mime(file_path)
        if self.allowed_mime_types and mime not in self.allowed_mime_types:
            issues.append(f"Unsupported MIME type: {mime}")

        modality = _detect_modality(file_path)
        if self.allowed_modalities and modality not in self.allowed_modalities:
            issues.append(f"Unsupported modality: {modality.value}")

        return len(issues) == 0, issues

    def validate_bytes(
        self,
        data: bytes,
        mime_type: str = "application/octet-stream",
        modality: ModalityType = ModalityType.TEXT,
    ) -> Tuple[bool, List[str]]:
        """Validate raw bytes."""
        issues: List[str] = []

        if len(data) > self.max_size_bytes:
            issues.append(
                f"Data too large: {len(data)} bytes (max {self.max_size_bytes})"
            )

        if self.allowed_mime_types and mime_type not in self.allowed_mime_types:
            issues.append(f"Unsupported MIME type: {mime_type}")

        if self.allowed_modalities and modality not in self.allowed_modalities:
            issues.append(f"Unsupported modality: {modality.value}")

        return len(issues) == 0, issues

    # ── processing ────────────────────────────────────────────

    def process_files(
        self,
        file_paths: List[str],
        text: str = "",
        **metadata: Any,
    ) -> ProcessResult:
        """Process a list of file paths into a MultimodalInput.

        Files that fail validation are skipped (with errors recorded).
        """
        images: List[MediaContent] = []
        audio: List[MediaContent] = []
        video: List[MediaContent] = []
        warnings: List[str] = []
        errors: List[str] = []

        for fp in file_paths:
            is_valid, issues = self.validate_file(fp)
            if not is_valid:
                errors.extend(issues)
                continue
            if issues:
                warnings.extend(issues)

            modality = _detect_modality(fp)
            media = MediaContent.from_file(fp, modality)

            if modality == ModalityType.IMAGE:
                images.append(media)
            elif modality == ModalityType.AUDIO:
                audio.append(media)
            elif modality == ModalityType.VIDEO:
                video.append(media)
            else:
                warnings.append(f"Unknown file type, skipping: {fp}")

        result_input = MultimodalInput(
            text=text,
            images=images,
            audio=audio,
            video=video,
            metadata=dict(metadata),
        )

        return ProcessResult(
            input=result_input,
            warnings=warnings,
            errors=errors,
        )

    def process_bytes(
        self,
        data_list: List[Tuple[bytes, str, ModalityType]],
        text: str = "",
        **metadata: Any,
    ) -> ProcessResult:
        """Process raw bytes into a MultimodalInput.

        Args:
            data_list: List of (bytes, mime_type, modality) tuples.
        """
        images: List[MediaContent] = []
        audio: List[MediaContent] = []
        video: List[MediaContent] = []
        warnings: List[str] = []
        errors: List[str] = []

        for data, mime, modality in data_list:
            is_valid, issues = self.validate_bytes(data, mime, modality)
            if not is_valid:
                errors.extend(issues)
                continue
            if issues:
                warnings.extend(issues)

            media = MediaContent.from_bytes(data, modality, mime)
            if modality == ModalityType.IMAGE:
                images.append(media)
            elif modality == ModalityType.AUDIO:
                audio.append(media)
            elif modality == ModalityType.VIDEO:
                video.append(media)

        result_input = MultimodalInput(
            text=text,
            images=images,
            audio=audio,
            video=video,
            metadata=dict(metadata),
        )

        return ProcessResult(
            input=result_input,
            warnings=warnings,
            errors=errors,
        )

    def process_text(self, text: str, **metadata: Any) -> ProcessResult:
        """Process text-only input."""
        return ProcessResult(
            input=MultimodalInput.from_text(text, **metadata),
        )

    # ── MIME utilities ────────────────────────────────────────

    @staticmethod
    def get_mime_type(file_path: str) -> str:
        """Guess MIME type from file path."""
        return _guess_mime(file_path)

    @staticmethod
    def get_modality(file_path: str) -> ModalityType:
        """Detect modality from file path."""
        return _detect_modality(file_path)

    @staticmethod
    def is_supported_extension(ext: str) -> bool:
        """Check if a file extension is supported."""
        if not ext.startswith("."):
            ext = "." + ext
        return ext.lower() in _MIME_MAP

    @staticmethod
    def supported_extensions() -> Dict[str, str]:
        """Return all supported extensions and their MIME types."""
        return dict(_MIME_MAP)
