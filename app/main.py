from typing import Optional
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.auth import TOKENS, create_default_users, get_current_user, login_user, require_admin
from app.database import get_connection, init_db
from app.importer import import_xlsx

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Moscow Violations Map", version="1.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class LoginRequest(BaseModel):
    username: str
    password: str


def get_optional_admin(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        return None

    token = authorization.replace("Bearer ", "", 1)
    user = TOKENS.get(token)
    if not user or user.get("role") != "admin":
        return None

    return user


@app.on_event("startup")
def startup():
    init_db()
    create_default_users()


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "map.html")


@app.get("/map")
def map_page():
    return FileResponse(STATIC_DIR / "map.html")


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


@app.post("/auth/login")
def login(data: LoginRequest):
    result = login_user(data.username, data.password)
    if not result:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return result


@app.get("/auth/me")
def me(user=Depends(get_current_user)):
    return user


@app.get("/api/filter-values")
def filter_values(user=Depends(get_optional_admin)):
    if not user:
        return {"status": [], "category": [], "object_group": [], "object_name": []}

    conn = get_connection()
    cur = conn.cursor()

    result = {}
    for field in ["status", "category", "object_group", "object_name"]:
        cur.execute(f"SELECT DISTINCT {field} FROM violations WHERE {field} IS NOT NULL AND {field} != '' ORDER BY {field}")
        result[field] = [row[0] for row in cur.fetchall()]

    conn.close()
    return result


@app.get("/api/violations")
def get_violations(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    object_group: Optional[str] = None,
    object_name: Optional[str] = None,
    user=Depends(get_optional_admin),
):
    if not user:
        return {"count": 0, "items": []}

    query = """
        SELECT id, task_id, category, object_group, object_name, status, assigned_at,
               latitude, longitude
        FROM violations
        WHERE 1 = 1
    """
    params = []

    if date_from:
        query += " AND assigned_at >= ?"
        params.append(date_from + " 00:00:00")
    if date_to:
        query += " AND assigned_at <= ?"
        params.append(date_to + " 23:59:59")
    if status:
        query += " AND status = ?"
        params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)
    if object_group:
        query += " AND object_group = ?"
        params.append(object_group)
    if object_name:
        query += " AND object_name = ?"
        params.append(object_name)

    query += " ORDER BY assigned_at DESC LIMIT 5000"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    return {"count": len(rows), "items": rows}


@app.get("/api/violation/{violation_id}")
def get_violation(violation_id: int, user=Depends(get_optional_admin)):
    if not user:
        raise HTTPException(status_code=403, detail="Данные доступны только в режиме администратора")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM violations WHERE id = ?", (violation_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Нарушение не найдено")

    return dict(row)


@app.post("/admin/upload")
def upload_xlsx(file: UploadFile = File(...), user=Depends(get_current_user)):
    require_admin(user)

    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Можно загружать только XLSX-файлы")

    with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    return import_xlsx(tmp_path, file.filename)
