"""Authentication service with secure password hashing and PostgreSQL persistence."""

from __future__ import annotations

import hashlib
import re
import secrets
from typing import Optional

from app.models.user import User
from app.services.database import get_connection


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a plaintext password using PBKDF2-HMAC-SHA256 with a secure salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        iterations=100_000,
    )
    return key.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify that a plaintext password matches the stored hash and salt."""
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, stored_hash)


def register_user(
    full_name: str,
    email: str,
    username: str,
    password: str,
    role: str = "Quản trị viên",
) -> tuple[bool, str, Optional[User]]:
    """Register a new user in the PostgreSQL database."""
    full_name = full_name.strip()
    email = email.strip().lower()
    username = username.strip()

    if not full_name:
        return False, "Vui lòng nhập họ và tên.", None
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return False, "Email không đúng định dạng.", None
    if len(username) < 6:
        return False, "Tên đăng nhập phải có ít nhất 6 ký tự.", None
    if len(password) < 8:
        return False, "Mật khẩu phải có ít nhất 8 ký tự.", None

    pwd_hash, salt = hash_password(password)

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            # Check for existing username
            cur.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(%s);", (username,))
            if cur.fetchone() is not None:
                conn.close()
                return False, f"Tên đăng nhập '{username}' đã được sử dụng.", None

            # Check for existing email
            cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s);", (email,))
            if cur.fetchone() is not None:
                conn.close()
                return False, f"Email '{email}' đã được đăng ký tài khoản.", None

            # Insert new user
            cur.execute(
                """
                INSERT INTO users (username, email, full_name, password_hash, salt, role)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, created_at;
                """,
                (username, email, full_name, pwd_hash, salt, role),
            )
            user_id, created_at = cur.fetchone()
            conn.commit()

        conn.close()
        new_user = User(
            id=user_id,
            username=username,
            email=email,
            full_name=full_name,
            role=role,
            created_at=created_at,
        )
        return True, "Đăng ký tài khoản thành công!", new_user
    except Exception as error:
        return False, f"Lỗi cơ sở dữ liệu khi đăng ký: {error}", None


def authenticate_user(account: str, password: str) -> tuple[bool, str, Optional[User]]:
    """Authenticate a user by username or email and password."""
    account = account.strip()
    if not account:
        return False, "Vui lòng nhập tài khoản hoặc email.", None
    if not password:
        return False, "Vui lòng nhập mật khẩu.", None

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, email, full_name, password_hash, salt, role, created_at, last_login
                FROM users
                WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s);
                """,
                (account, account),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return False, "Tài khoản hoặc email không tồn tại trong hệ thống.", None

            user_id, username, email, full_name, stored_hash, salt, role, created_at, last_login = row

            if not verify_password(password, stored_hash, salt):
                conn.close()
                return False, "Mật khẩu không chính xác. Vui lòng thử lại.", None

            # Update last_login
            cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s;", (user_id,))
            conn.commit()

        conn.close()
        user = User(
            id=user_id,
            username=username,
            email=email,
            full_name=full_name,
            role=role,
            created_at=created_at,
            last_login=last_login,
        )
        return True, "Đăng nhập thành công!", user
    except Exception as error:
        return False, f"Lỗi cơ sở dữ liệu khi đăng nhập: {error}", None


def ensure_default_admin() -> tuple[bool, str]:
    """Create a default administrator account if the users table is completely empty."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users;")
            count = cur.fetchone()[0]
            if count == 0:
                pwd_hash, salt = hash_password("Admin@123")
                cur.execute(
                    """
                    INSERT INTO users (username, email, full_name, password_hash, salt, role)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    ("admin", "admin@soc.local", "Quản trị viên hệ thống", pwd_hash, salt, "Quản trị viên"),
                )
                conn.commit()
                conn.close()
                return True, "Đã tạo tài khoản mặc định: admin / Admin@123"
        conn.close()
        return True, "Tài khoản người dùng đã tồn tại."
    except Exception as error:
        return False, f"Không thể tạo tài khoản mặc định: {error}"

