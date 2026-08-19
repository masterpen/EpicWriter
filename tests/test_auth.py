"""Auth 单元测试：密码哈希与 JWT token 的安全关键逻辑。

不依赖 Neo4j —— 仅测试 hash_password / verify_password / create_token / decode_token。
"""
import jwt
import pytest
from api.routers.auth import (
    hash_password,
    verify_password,
    create_token,
    decode_token,
)
from fastapi import HTTPException


class TestPasswordHashing:
    def test_hash_returns_hash_and_salt(self):
        password_hash, salt = hash_password("myPassword123")
        assert isinstance(password_hash, str)
        assert isinstance(salt, str)
        assert len(password_hash) > 0
        assert len(salt) > 0

    def test_each_call_generates_unique_salt(self):
        hash1, salt1 = hash_password("samePassword")
        hash2, salt2 = hash_password("samePassword")
        assert salt1 != salt2
        assert hash1 != hash2

    def test_verify_correct_password(self):
        password_hash, salt = hash_password("correctPassword")
        assert verify_password("correctPassword", password_hash, salt) is True

    def test_verify_wrong_password(self):
        password_hash, salt = hash_password("correctPassword")
        assert verify_password("wrongPassword", password_hash, salt) is False

    def test_verify_with_tampered_hash(self):
        password_hash, salt = hash_password("correctPassword")
        tampered = "a" * len(password_hash)
        assert verify_password("correctPassword", tampered, salt) is False

    def test_explicit_salt_reproducible(self):
        fixed_salt = "abcdef0123456789"
        hash1, salt1 = hash_password("testPassword", salt=fixed_salt)
        hash2, salt2 = hash_password("testPassword", salt=fixed_salt)
        assert salt1 == fixed_salt
        assert salt2 == fixed_salt
        assert hash1 == hash2

    def test_empty_password_hashes_safely(self):
        password_hash, salt = hash_password("")
        assert verify_password("", password_hash, salt) is True
        assert verify_password("nonempty", password_hash, salt) is False


class TestJwtTokens:
    def test_create_and_decode_token_roundtrip(self):
        token = create_token("user-123", "testuser")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["username"] == "testuser"
        assert "exp" in payload

    def test_decode_invalid_token_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid.token.here")
        assert exc_info.value.status_code == 401
        assert "Invalid" in exc_info.value.detail

    def test_decode_token_with_wrong_signature_raises_401(self):
        token = create_token("user-123", "testuser")
        # 篡改签名：修改最后一段
        parts = token.split(".")
        parts[2] = "x" * len(parts[2])
        tampered_token = ".".join(parts)
        with pytest.raises(HTTPException) as exc_info:
            decode_token(tampered_token)
        assert exc_info.value.status_code == 401

    def test_decode_expired_token_raises_401(self):
        import time
        # 创建一个已过期的 token（直接构造 payload）
        import jwt as jwt_lib
        from datetime import datetime, timedelta
        from app.core.config import settings
        expired_payload = {
            "sub": "user-123",
            "username": "testuser",
            "exp": datetime.utcnow() - timedelta(hours=1),
        }
        expired_token = jwt_lib.encode(
            expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_token(expired_token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()
