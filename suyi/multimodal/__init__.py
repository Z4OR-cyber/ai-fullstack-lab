"""Multimodal Support — unified input processing for text, image, audio, and video.

Public API:
    - MultimodalInput: unified input container
    - MediaContent: single media item (image/audio/video)
    - ModalityType: modality enum
    - InputProcessor: format detection, validation, processing
    - ProcessResult: processing result with warnings/errors
    - FormatConverter: base64/data URI/MIME conversion utilities
    - ValidationError: validation error
"""

from .base import (
    MultimodalInput,
    MediaContent,
    ImageContent,
    AudioContent,
    VideoContent,
    ModalityType,
)
from .processor import (
    InputProcessor,
    ProcessResult,
    ValidationError,
)
from .converter import FormatConverter

__all__ = [
    "MultimodalInput",
    "MediaContent",
    "ImageContent",
    "AudioContent",
    "VideoContent",
    "ModalityType",
    "InputProcessor",
    "ProcessResult",
    "ValidationError",
    "FormatConverter",
]
