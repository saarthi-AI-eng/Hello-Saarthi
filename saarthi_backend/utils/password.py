"""Password hashing using bcrypt (no passlib to avoid version clashes)."""

import bcrypt

# Bcrypt has a 72-byte limit; truncate to avoid ValueError
BCRYPT_MAX_PASSWORD_BYTES = 72


def _to_bytes(password: str) -> bytes:
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > BCRYPT_MAX_PASSWORD_BYTES:
        pwd_bytes = pwd_bytes[:BCRYPT_MAX_PASSWORD_BYTES]
    return pwd_bytes


def hash_password(password: str) -> str:
    pwd_bytes = _to_bytes(password)
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pwd_bytes = _to_bytes(plain)
    return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
