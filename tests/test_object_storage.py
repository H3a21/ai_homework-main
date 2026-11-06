"""Unit tests for the private MinIO object storage adapter."""

import asyncio

from app import object_storage


class MissingObjectError(Exception):
    code = "NoSuchKey"


class FakeResponse:
    def __init__(self, content: bytes, content_type: str):
        self.content = content
        self.headers = {"content-type": content_type}
        self.closed = False
        self.released = False

    def read(self):
        return self.content

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


class FakeMinio:
    def __init__(self):
        self.bucket_created = False
        self.objects = {}
        self.last_response = None

    def bucket_exists(self, bucket):
        return self.bucket_created

    def make_bucket(self, bucket):
        self.bucket_created = True

    def put_object(self, bucket, object_name, stream, length, content_type):
        self.objects[object_name] = (stream.read(length), content_type)

    def stat_object(self, bucket, object_name):
        if object_name not in self.objects:
            raise MissingObjectError()
        return object()

    def get_object(self, bucket, object_name):
        content, content_type = self.objects[object_name]
        self.last_response = FakeResponse(content, content_type)
        return self.last_response


def test_store_check_and_read_submission_image(monkeypatch):
    client = FakeMinio()
    monkeypatch.setattr(object_storage, "get_minio_client", lambda: client)

    async def run():
        object_name = await object_storage.store_submission_image(
            8, b"image-bytes", ".png", "image/png"
        )
        assert object_name.startswith("submissions/8/")
        assert object_name.endswith(".png")
        assert client.bucket_created is True
        assert await object_storage.object_exists(object_name) is True
        assert await object_storage.object_exists("missing.png") is False

        stored = await object_storage.read_object(object_name)
        assert stored.content == b"image-bytes"
        assert stored.content_type == "image/png"
        assert client.last_response.closed is True
        assert client.last_response.released is True

    asyncio.run(run())
