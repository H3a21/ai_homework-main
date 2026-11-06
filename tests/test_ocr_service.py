"""Fast OCR endpoint tests without loading PaddleOCR models."""

import importlib.util
import os
import sys
import types

if importlib.util.find_spec("multipart") is None:
    multipart = types.ModuleType("multipart")
    multipart.__version__ = "0.0-test"
    multipart_submodule = types.ModuleType("multipart.multipart")
    multipart_submodule.parse_options_header = lambda value: (value, {})
    sys.modules["multipart"] = multipart
    sys.modules["multipart.multipart"] = multipart_submodule

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ocr"))

import ocr_server


def test_validate_png_and_reject_non_images():
    png = b"\x89PNG\r\n\x1a\n" + b"test"
    assert ocr_server._validate_image("answer.png", png) == ".png"

    try:
        ocr_server._validate_image("answer.txt", b"plain text")
    except Exception as exc:
        assert exc.status_code == 415
    else:
        raise AssertionError("Expected a 415 response for non-image content")


def test_image_extension_must_match_magic_bytes():
    jpeg = b"\xff\xd8\xff" + b"test"
    assert ocr_server._validate_image("answer.jpg", jpeg) == ".jpg"

    for filename, content in (("answer.png", jpeg), ("answer.jpg", b"\x89PNG\r\n\x1a\n")):
        try:
            ocr_server._validate_image(filename, content)
        except Exception as exc:
            assert exc.status_code == 415
        else:
            raise AssertionError("Expected a 415 response for mismatched image content")


def test_empty_and_oversized_images_are_rejected():
    try:
        ocr_server._validate_image("answer.png", b"")
    except Exception as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected a 400 response for an empty image")

    original_limit = ocr_server.MAX_IMAGE_BYTES
    ocr_server.MAX_IMAGE_BYTES = 8
    try:
        try:
            ocr_server._validate_image("answer.png", b"\x89PNG\r\n\x1a\nX")
        except Exception as exc:
            assert exc.status_code == 413
        else:
            raise AssertionError("Expected a 413 response for an oversized image")
    finally:
        ocr_server.MAX_IMAGE_BYTES = original_limit


if __name__ == "__main__":
    test_validate_png_and_reject_non_images()
    print("PASS: test_validate_png_and_reject_non_images")
    test_empty_and_oversized_images_are_rejected()
    print("PASS: test_empty_and_oversized_images_are_rejected")
