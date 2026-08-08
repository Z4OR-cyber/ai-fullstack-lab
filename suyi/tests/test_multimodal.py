"""Tests for Multimodal Support (Phase 11)."""

from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path

import pytest

from suyi.multimodal import (
    MultimodalInput,
    MediaContent,
    ModalityType,
    InputProcessor,
    ProcessResult,
    FormatConverter,
    ValidationError,
)


# ── ModalityType tests ────────────────────────────────────────

class TestModalityType:
    def test_values(self):
        assert ModalityType.TEXT.value == "text"
        assert ModalityType.IMAGE.value == "image"
        assert ModalityType.AUDIO.value == "audio"
        assert ModalityType.VIDEO.value == "video"

    def test_from_string(self):
        assert ModalityType("text") == ModalityType.TEXT
        assert ModalityType("image") == ModalityType.IMAGE


# ── MediaContent tests ────────────────────────────────────────

class TestMediaContent:
    def test_from_bytes(self):
        mc = MediaContent.from_bytes(b"fake_image_data", ModalityType.IMAGE, "image/png")
        assert mc.modality == ModalityType.IMAGE
        assert mc.mime_type == "image/png"
        assert mc.get_data() == b"fake_image_data"
        assert mc.get_size() == 15

    def test_from_base64(self):
        raw = b"test data"
        b64 = base64.b64encode(raw).decode()
        mc = MediaContent.from_base64(b64, ModalityType.IMAGE, "image/png")
        assert mc.get_data() == raw
        assert mc.get_base64() == b64

    def test_from_file(self, tmp_path):
        f = tmp_path / "test.png"
        f.write_bytes(b"\x89PNG fake data")
        mc = MediaContent.from_file(str(f))
        assert mc.modality == ModalityType.IMAGE
        assert mc.mime_type == "image/png"
        assert mc.get_data() == b"\x89PNG fake data"

    def test_from_file_jpeg(self, tmp_path):
        f = tmp_path / "photo.jpg"
        f.write_bytes(b"fake jpeg")
        mc = MediaContent.from_file(str(f))
        assert mc.mime_type == "image/jpeg"
        assert mc.modality == ModalityType.IMAGE

    def test_from_file_mp3(self, tmp_path):
        f = tmp_path / "audio.mp3"
        f.write_bytes(b"fake audio")
        mc = MediaContent.from_file(str(f))
        assert mc.modality == ModalityType.AUDIO
        assert mc.mime_type == "audio/mpeg"

    def test_from_file_mp4(self, tmp_path):
        f = tmp_path / "video.mp4"
        f.write_bytes(b"fake video")
        mc = MediaContent.from_file(str(f))
        assert mc.modality == ModalityType.VIDEO
        assert mc.mime_type == "video/mp4"

    def test_get_base64_lazy(self):
        mc = MediaContent.from_bytes(b"hello", ModalityType.IMAGE, "image/png")
        assert mc._base64_cache is None
        b64 = mc.get_base64()
        assert mc._base64_cache is not None
        assert mc.get_base64() == b64

    def test_get_size_from_file(self, tmp_path):
        f = tmp_path / "test.png"
        f.write_bytes(b"A" * 100)
        mc = MediaContent.from_file(str(f))
        assert mc.get_size() == 100

    def test_to_dict(self):
        mc = MediaContent.from_bytes(b"data", ModalityType.IMAGE, "image/png")
        mc.metadata = {"width": 100, "height": 200}
        d = mc.to_dict()
        assert d["modality"] == "image"
        assert d["mime_type"] == "image/png"
        assert d["size"] == 4
        assert d["metadata"]["width"] == 100

    def test_repr(self):
        mc = MediaContent.from_bytes(b"data", ModalityType.IMAGE, "image/png")
        r = repr(mc)
        assert "image" in r
        assert "image/png" in r

    def test_get_data_nonexistent_file(self):
        mc = MediaContent(modality=ModalityType.IMAGE, file_path="/nonexistent/file.png")
        assert mc.get_data() == b""
        assert mc.get_size() == 0

    def test_explicit_modality_override(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"data")
        mc = MediaContent.from_file(str(f), modality=ModalityType.IMAGE)
        assert mc.modality == ModalityType.IMAGE


# ── MultimodalInput tests ─────────────────────────────────────

class TestMultimodalInput:
    def test_text_factory(self):
        inp = MultimodalInput.from_text("Hello, world!")
        assert inp.text == "Hello, world!"
        assert inp.images == []
        assert inp.is_text_only()
        assert not inp.is_multimodal()

    def test_image_factory_with_file(self, tmp_path):
        f = tmp_path / "test.png"
        f.write_bytes(b"fake png")
        inp = MultimodalInput.from_image(file_path=str(f), text="What is this?")
        assert len(inp.images) == 1
        assert inp.text == "What is this?"
        assert inp.is_multimodal()

    def test_image_factory_with_bytes(self):
        inp = MultimodalInput.from_image(data=b"fake image", text="describe")
        assert len(inp.images) == 1
        assert inp.text == "describe"

    def test_image_factory_no_args_raises(self):
        with pytest.raises(ValueError, match="Either file_path or data"):
            MultimodalInput.from_image()

    def test_audio_factory(self, tmp_path):
        f = tmp_path / "audio.mp3"
        f.write_bytes(b"fake audio")
        inp = MultimodalInput.from_audio(file_path=str(f))
        assert len(inp.audio) == 1

    def test_audio_factory_with_bytes(self):
        inp = MultimodalInput.from_audio(data=b"fake audio")
        assert len(inp.audio) == 1

    def test_get_modalities(self):
        inp = MultimodalInput(
            text="hi",
            images=[MediaContent.from_bytes(b"x", ModalityType.IMAGE)],
        )
        mods = inp.get_modalities()
        assert ModalityType.TEXT in mods
        assert ModalityType.IMAGE in mods

    def test_is_multimodal_true(self):
        inp = MultimodalInput(
            text="hi",
            images=[MediaContent.from_bytes(b"x", ModalityType.IMAGE)],
        )
        assert inp.is_multimodal()

    def test_is_text_only_false_with_images(self):
        inp = MultimodalInput(
            text="hi",
            images=[MediaContent.from_bytes(b"x", ModalityType.IMAGE)],
        )
        assert not inp.is_text_only()

    def test_total_size(self):
        img1 = MediaContent.from_bytes(b"AAAA", ModalityType.IMAGE)
        img2 = MediaContent.from_bytes(b"BB", ModalityType.IMAGE)
        inp = MultimodalInput(images=[img1, img2])
        assert inp.total_size() == 6

    def test_to_dict(self):
        inp = MultimodalInput(
            text="hello",
            images=[MediaContent.from_bytes(b"data", ModalityType.IMAGE, "image/png")],
        )
        d = inp.to_dict()
        assert d["text"] == "hello"
        assert len(d["images"]) == 1
        assert "image" in d["modalities"]
        assert "text" in d["modalities"]
        assert d["total_size"] == 4

    def test_repr(self):
        inp = MultimodalInput(text="hi", images=[MediaContent.from_bytes(b"x", ModalityType.IMAGE)])
        r = repr(inp)
        assert "text" in r
        assert "image" in r

    def test_empty_input(self):
        inp = MultimodalInput()
        assert inp.text == ""
        assert inp.get_modalities() == []
        assert not inp.is_multimodal()

    def test_all_modalities(self):
        inp = MultimodalInput(
            text="test",
            images=[MediaContent.from_bytes(b"i", ModalityType.IMAGE)],
            audio=[MediaContent.from_bytes(b"a", ModalityType.AUDIO)],
            video=[MediaContent.from_bytes(b"v", ModalityType.VIDEO)],
        )
        mods = inp.get_modalities()
        assert len(mods) == 4

    def test_metadata(self):
        inp = MultimodalInput.from_text("hi", session_id="123", user="test")
        assert inp.metadata["session_id"] == "123"
        assert inp.metadata["user"] == "test"


# ── InputProcessor tests ──────────────────────────────────────

class TestInputProcessor:
    def test_init_defaults(self):
        proc = InputProcessor()
        assert proc.max_size_bytes == 20 * 1024 * 1024
        assert proc.allowed_mime_types == set()
        assert proc.allowed_modalities == set()

    def test_init_custom(self):
        proc = InputProcessor(max_size_mb=5, allowed_mime_types={"image/png"})
        assert proc.max_size_bytes == 5 * 1024 * 1024
        assert "image/png" in proc.allowed_mime_types

    def test_validate_file_valid(self, tmp_path):
        f = tmp_path / "test.png"
        f.write_bytes(b"\x89PNG")
        proc = InputProcessor()
        is_valid, issues = proc.validate_file(str(f))
        assert is_valid
        assert issues == []

    def test_validate_file_not_found(self):
        proc = InputProcessor()
        is_valid, issues = proc.validate_file("/nonexistent/file.png")
        assert not is_valid
        assert "not found" in issues[0].lower() or "File not found" in issues[0]

    def test_validate_file_too_large(self, tmp_path):
        f = tmp_path / "big.png"
        f.write_bytes(b"A" * (2 * 1024 * 1024))
        proc = InputProcessor(max_size_mb=1)
        is_valid, issues = proc.validate_file(str(f))
        assert not is_valid
        assert any("too large" in i.lower() for i in issues)

    def test_validate_file_not_a_file(self, tmp_path):
        d = tmp_path / "dir"
        d.mkdir()
        proc = InputProcessor()
        is_valid, issues = proc.validate_file(str(d))
        assert not is_valid

    def test_validate_file_restricted_mime(self, tmp_path):
        f = tmp_path / "test.bmp"
        f.write_bytes(b"data")
        proc = InputProcessor(allowed_mime_types={"image/png"})
        is_valid, issues = proc.validate_file(str(f))
        assert not is_valid
        assert any("image/bmp" in i for i in issues)

    def test_validate_file_restricted_modality(self, tmp_path):
        f = tmp_path / "test.png"
        f.write_bytes(b"data")
        proc = InputProcessor(allowed_modalities={ModalityType.TEXT})
        is_valid, issues = proc.validate_file(str(f))
        assert not is_valid
        assert any("image" in i.lower() for i in issues)

    def test_validate_bytes(self):
        proc = InputProcessor(max_size_mb=1)
        is_valid, issues = proc.validate_bytes(b"small data", "image/png", ModalityType.IMAGE)
        assert is_valid

    def test_validate_bytes_too_large(self):
        proc = InputProcessor(max_size_mb=1)
        is_valid, issues = proc.validate_bytes(b"A" * (2 * 1024 * 1024), "image/png", ModalityType.IMAGE)
        assert not is_valid

    def test_process_files(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"fake png")

        proc = InputProcessor()
        result = proc.process_files([str(img)], text="describe")
        assert result.is_valid
        assert len(result.input.images) == 1
        assert result.input.text == "describe"

    def test_process_files_multiple(self, tmp_path):
        img1 = tmp_path / "img1.png"
        img1.write_bytes(b"img1")
        img2 = tmp_path / "img2.jpg"
        img2.write_bytes(b"img2")
        aud = tmp_path / "audio.mp3"
        aud.write_bytes(b"audio")

        proc = InputProcessor()
        result = proc.process_files([str(img1), str(img2), str(aud)])
        assert result.is_valid
        assert len(result.input.images) == 2
        assert len(result.input.audio) == 1

    def test_process_files_with_errors(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"png")
        proc = InputProcessor(max_size_mb=0.001)
        result = proc.process_files([str(img), "/nonexistent.png"])
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_process_text(self):
        proc = InputProcessor()
        result = proc.process_text("Hello!")
        assert result.is_valid
        assert result.input.text == "Hello!"
        assert result.input.is_text_only()

    def test_process_bytes(self):
        proc = InputProcessor()
        result = proc.process_bytes(
            [(b"img data", "image/png", ModalityType.IMAGE)],
            text="desc",
        )
        assert result.is_valid
        assert len(result.input.images) == 1
        assert result.input.text == "desc"

    def test_process_bytes_multiple(self):
        proc = InputProcessor()
        result = proc.process_bytes([
            (b"img1", "image/png", ModalityType.IMAGE),
            (b"aud1", "audio/wav", ModalityType.AUDIO),
        ])
        assert result.is_valid
        assert len(result.input.images) == 1
        assert len(result.input.audio) == 1

    def test_get_mime_type(self):
        assert InputProcessor.get_mime_type("test.png") == "image/png"
        assert InputProcessor.get_mime_type("test.jpg") == "image/jpeg"
        assert InputProcessor.get_mime_type("test.mp3") == "audio/mpeg"
        assert InputProcessor.get_mime_type("test.mp4") == "video/mp4"

    def test_get_modality(self):
        assert InputProcessor.get_modality("test.png") == ModalityType.IMAGE
        assert InputProcessor.get_modality("test.wav") == ModalityType.AUDIO
        assert InputProcessor.get_modality("test.mp4") == ModalityType.VIDEO

    def test_is_supported_extension(self):
        assert InputProcessor.is_supported_extension(".png")
        assert InputProcessor.is_supported_extension("jpg")
        assert not InputProcessor.is_supported_extension(".xyz")

    def test_supported_extensions(self):
        exts = InputProcessor.supported_extensions()
        assert ".png" in exts
        assert ".mp3" in exts
        assert ".mp4" in exts

    def test_process_result_to_dict(self):
        proc = InputProcessor()
        result = proc.process_text("hi")
        d = result.to_dict()
        assert d["is_valid"] is True
        assert d["input"]["text"] == "hi"

    def test_process_result_is_valid(self):
        proc = InputProcessor()
        result = proc.process_text("hi")
        assert result.is_valid is True

        result2 = proc.process_files(["/nonexistent.png"])
        assert result2.is_valid is False


# ── FormatConverter tests ────────────────────────────────────

class TestFormatConverter:
    def test_to_base64(self):
        b64 = FormatConverter.to_base64(b"hello")
        assert b64 == base64.b64encode(b"hello").decode()

    def test_from_base64(self):
        b64 = base64.b64encode(b"hello").decode()
        data = FormatConverter.from_base64(b64)
        assert data == b"hello"

    def test_from_base64_no_padding(self):
        data = FormatConverter.from_base64("aGVsbG8")
        assert data == b"hello"

    def test_from_base64_data_uri(self):
        uri = "data:image/png;base64,aGVsbG8="
        mime, data = FormatConverter.from_data_uri(uri)
        assert mime == "image/png"
        assert data == b"hello"

    def test_to_data_uri(self):
        uri = FormatConverter.to_data_uri(b"hello", "image/png")
        assert uri.startswith("data:image/png;base64,")
        assert uri.endswith(base64.b64encode(b"hello").decode())

    def test_to_data_uri_no_base64(self):
        uri = FormatConverter.to_data_uri(b"hello", "text/plain", base64_encode=False)
        assert uri == "data:text/plain,hello"

    def test_from_data_uri(self):
        uri = "data:image/png;base64,aGVsbG8="
        mime, data = FormatConverter.from_data_uri(uri)
        assert mime == "image/png"
        assert data == b"hello"

    def test_from_data_uri_text(self):
        uri = "data:text/plain,hello world"
        mime, data = FormatConverter.from_data_uri(uri)
        assert mime == "text/plain"
        assert data == b"hello world"

    def test_from_data_uri_invalid(self):
        with pytest.raises(ValueError, match="Not a data URI"):
            FormatConverter.from_data_uri("not a data uri")

    def test_mime_to_extension(self):
        assert FormatConverter.mime_to_extension("image/png") == ".png"
        assert FormatConverter.mime_to_extension("image/jpeg") == ".jpg"
        assert FormatConverter.mime_to_extension("audio/mpeg") == ".mp3"
        assert FormatConverter.mime_to_extension("video/mp4") == ".mp4"

    def test_extension_to_mime(self):
        assert FormatConverter.extension_to_mime(".png") == "image/png"
        assert FormatConverter.extension_to_mime("jpg") == "image/jpeg"
        assert FormatConverter.extension_to_mime(".mp3") == "audio/mpeg"

    def test_round_trip_base64(self):
        original = b"\x89PNG\r\n\x1a\n fake image data"
        b64 = FormatConverter.to_base64(original)
        decoded = FormatConverter.from_base64(b64)
        assert decoded == original

    def test_round_trip_data_uri(self):
        original = b"test data here"
        mime = "image/jpeg"
        uri = FormatConverter.to_data_uri(original, mime)
        decoded_mime, decoded_data = FormatConverter.from_data_uri(uri)
        assert decoded_mime == mime
        assert decoded_data == original

    def test_convert_mime_same_type(self):
        data = b"fake image"
        mime, result = FormatConverter.convert_mime(data, "image/png", "image/jpeg")
        assert mime == "image/jpeg"
        assert result == data

    def test_convert_mime_different_type_raises(self):
        with pytest.raises(ValueError, match="different modality types"):
            FormatConverter.convert_mime(b"data", "image/png", "audio/wav")

    def test_media_to_base64(self):
        mc = MediaContent.from_bytes(b"hello", ModalityType.IMAGE, "image/png")
        b64 = FormatConverter.media_to_base64(mc)
        assert base64.b64decode(b64) == b"hello"

    def test_media_to_data_uri(self):
        mc = MediaContent.from_bytes(b"hello", ModalityType.IMAGE, "image/png")
        uri = FormatConverter.media_to_data_uri(mc)
        assert uri.startswith("data:image/png;base64,")

    def test_base64_to_media(self):
        b64 = base64.b64encode(b"test").decode()
        mc = FormatConverter.base64_to_media(b64, ModalityType.IMAGE, "image/png")
        assert mc.get_data() == b"test"
        assert mc.modality == ModalityType.IMAGE

    def test_data_uri_to_media(self):
        uri = "data:image/png;base64," + base64.b64encode(b"test").decode()
        mc = FormatConverter.data_uri_to_media(uri)
        assert mc.get_data() == b"test"
        assert mc.modality == ModalityType.IMAGE
        assert mc.mime_type == "image/png"

    def test_batch_to_base64(self):
        items = [
            MediaContent.from_bytes(b"a", ModalityType.IMAGE),
            MediaContent.from_bytes(b"b", ModalityType.IMAGE),
        ]
        b64_list = FormatConverter.batch_to_base64(items)
        assert len(b64_list) == 2
        assert base64.b64decode(b64_list[0]) == b"a"
        assert base64.b64decode(b64_list[1]) == b"b"

    def test_batch_to_data_uris(self):
        items = [
            MediaContent.from_bytes(b"x", ModalityType.IMAGE, "image/png"),
            MediaContent.from_bytes(b"y", ModalityType.IMAGE, "image/jpeg"),
        ]
        uris = FormatConverter.batch_to_data_uris(items)
        assert len(uris) == 2
        assert uris[0].startswith("data:image/png;base64,")
        assert uris[1].startswith("data:image/jpeg;base64,")

    def test_url_safe_base64(self):
        data = b"\xfb\xff"
        b64 = base64.urlsafe_b64encode(data).decode()
        decoded = FormatConverter.from_base64(b64)
        assert decoded == data

    def test_mime_to_extension_unknown(self):
        ext = FormatConverter.mime_to_extension("application/x-custom")
        assert isinstance(ext, str)

    def test_extension_to_mime_unknown(self):
        mime = FormatConverter.extension_to_mime(".unknown")
        assert mime == "application/octet-stream"
