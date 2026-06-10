"""
敏感信息加解密工具 — 使用 Fernet 对称加密

密钥来源（优先级）:
1. ENCRYPTION_KEY 环境变量
2. DB_PASSWORD 环境变量派生
"""

from __future__ import annotations

import base64
import logging
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

_SALT = b"edu-companion-llm-key-v1"


def _derive_key(secret: str) -> bytes:
    """从 secret 派生 Fernet 密钥（32 bytes url-safe-base64）"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))


def _get_key() -> bytes:
    """获取加密密钥"""
    key = os.environ.get("ENCRYPTION_KEY")
    if key:
        try:
            return base64.urlsafe_b64decode(key)
        except Exception:
            return _derive_key(key)
    # fallback: 从 DB_PASSWORD 派生
    db_pw = os.environ.get("DB_PASSWORD", "default-dev-key-change-me")
    return _derive_key(db_pw)


_fernet = Fernet(_get_key())


def encrypt(plaintext: str) -> str:
    """加密字符串 -> base64 密文"""
    if not plaintext:
        return ""
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """解密 base64 密文 -> 原始字符串"""
    if not ciphertext:
        return ""
    try:
        return _fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error("解密失败: %s", e)
        return ""