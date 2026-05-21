import hashlib
import secrets
from fastapi import Header, HTTPException
from app.database import get_connection

TOKENS = {}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_default_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ("admin", hash_password("admin123"), "admin"),
    )

    conn.commit()
    conn.close()


def login_user(username: str, password: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ? AND role = 'admin'", (username,))
    user = cur.fetchone()
    conn.close()

    if not user or user["password_hash"] != hash_password(password):
        return None

    token = secrets.token_hex(32)
    TOKENS[token] = {"username": user["username"], "role": user["role"]}
    return {"token": token, "username": user["username"], "role": user["role"]}


def get_current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Не выполнен вход администратора")

    token = authorization.replace("Bearer ", "", 1)
    user = TOKENS.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Недействительный токен")

    return user


def require_admin(user: dict):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Доступ разрешён только администратору")
