"""Security tests for MCP file-path traversal handling (``files/write``).

The gateway proxies validated requests to upstream MCP file servers, so its
``files/write`` path check IS a security boundary. It must defeat traversal by
*normalisation*, not a substring denylist — an encoded (``..%2f``) or creative
path slips past ``"../" in path`` and would reach the upstream file server.

These import only ``mcprelay.mcp`` + ``mcprelay.auth`` (no ``server``/``license``),
so they run standalone in the OSS package.
"""

import json

import pytest

from mcprelay.auth import AuthContext
from mcprelay.mcp import MCPRequestValidator


def _ctx(user_id: str = "alice", is_admin: bool = False) -> AuthContext:
    return AuthContext(user_id=user_id, request_id="req-1", is_admin=is_admin)


@pytest.fixture()
def validator() -> MCPRequestValidator:
    return MCPRequestValidator()


class TestSafeFilePath:
    def test_legit_path_within_user_dir_is_allowed_and_normalised(self, validator):
        assert (
            validator._safe_file_path("/users/alice/./notes/x.txt", _ctx())
            == "/users/alice/notes/x.txt"
        )

    def test_literal_dotdot_traversal_rejected(self, validator):
        with pytest.raises(ValueError):
            validator._safe_file_path("/users/alice/../../etc/passwd", _ctx())

    def test_normalised_escape_rejected(self, validator):
        # normalises to /users/bob/x — outside alice's directory
        with pytest.raises(ValueError, match="restricted"):
            validator._safe_file_path("/users/alice/../bob/x", _ctx())

    def test_url_encoded_traversal_rejected(self, validator):
        # the classic denylist bypass: %2f is not "/", so "../" never appears
        with pytest.raises(ValueError, match="invalid characters"):
            validator._safe_file_path("/users/alice/..%2f..%2fetc%2fpasswd", _ctx())

    def test_nul_byte_rejected(self, validator):
        with pytest.raises(ValueError, match="invalid characters"):
            validator._safe_file_path("/users/alice/x\x00.txt", _ctx())

    def test_relative_path_rejected(self, validator):
        with pytest.raises(ValueError, match="absolute"):
            validator._safe_file_path("users/alice/x", _ctx())

    def test_prefix_confusion_rejected(self, validator):
        # /users/alicebob must NOT satisfy the /users/alice/ restriction
        with pytest.raises(ValueError, match="restricted"):
            validator._safe_file_path("/users/alicebob/secret", _ctx())

    def test_empty_path_rejected(self, validator):
        with pytest.raises(ValueError):
            validator._safe_file_path("", _ctx())

    def test_admin_may_write_outside_user_dirs(self, validator):
        assert (
            validator._safe_file_path("/etc/app/config.json", _ctx(is_admin=True))
            == "/etc/app/config.json"
        )


@pytest.mark.asyncio
class TestEndToEnd:
    async def _write(self, validator, path):
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "files/write",
                "params": {"path": path, "content": "x"},
            }
        ).encode()
        return await validator.validate_and_sanitize(body, _ctx())

    async def test_traversal_request_is_rejected_end_to_end(self, validator):
        with pytest.raises(ValueError):
            await self._write(validator, "/users/alice/..%2f..%2fetc%2fpasswd")

    async def test_legit_write_is_normalised_and_forwarded(self, validator):
        out = json.loads(await self._write(validator, "/users/alice/./notes/x.txt"))
        assert out["params"]["path"] == "/users/alice/notes/x.txt"
