import json
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd

from app.database import get_connection

COLUMN_ALIASES = {
    "task_id": ["ID задачи", "id задачи", "ID", "№ задачи", "Идентификатор задачи"],
    "category": ["Категория", "Категория задачи", "Категория нарушения", "category"],
    "object_group": ["Группа объекта", "Группа объектов", "Группа", "object_group"],
    "object_name": ["Объект", "Название объекта", "Наименование объекта", "object", "object_name"],
    "status": ["Статус", "Статус задачи", "status"],
    "assigned_at": ["Время назначения задачи", "Дата назначения", "Время назначения", "Назначено", "assigned_at"],
    "latitude": ["Широта", "Latitude", "lat", "latitude"],
    "longitude": ["Долгота", "Longitude", "lon", "lng", "longitude"],
    "task_link": ["Ссылка на карточку задачи", "Ссылка на задачу", "Карточка задачи", "task_link"],
    "violation_photo": ["Фото Нарушение", "Нарушение", "Фото нарушения", "violation_photo"],
    "fix_photo": ["Фото Устранение", "Устранение", "Фото устранения", "fix_photo"],
}
REQUIRED_FIELDS = ["task_id", "latitude", "longitude", "assigned_at"]


def normalize_name(value: str) -> str:
    return str(value).strip().lower().replace("ё", "е")


def find_columns(df: pd.DataFrame) -> Dict[str, str]:
    normalized_columns = {normalize_name(col): col for col in df.columns}
    result = {}

    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = normalize_name(alias)
            if key in normalized_columns:
                result[field] = normalized_columns[key]
                break

    return result


def clean_text(value: Any) -> Optional[str]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text.endswith(".0") and text.replace(".0", "").isdigit():
        text = text[:-2]
    return text if text else None


def parse_datetime(value: Any) -> Optional[str]:
    if pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def parse_float(value: Any) -> Optional[float]:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.replace(",", ".").strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def row_to_json(row: pd.Series) -> str:
    data = {}
    for key, value in row.items():
        if pd.isna(value):
            data[str(key)] = None
        elif isinstance(value, (pd.Timestamp, datetime)):
            data[str(key)] = value.strftime("%Y-%m-%d %H:%M:%S")
        else:
            data[str(key)] = str(value)
    return json.dumps(data, ensure_ascii=False)


def import_xlsx(file_path: str, filename: str) -> dict:
    df = pd.read_excel(file_path)
    columns = find_columns(df)

    missing = [field for field in REQUIRED_FIELDS if field not in columns]
    if missing:
        readable = ", ".join(missing)
        return {
            "ok": False,
            "accepted": 0,
            "errors_count": 1,
            "errors": [f"В файле отсутствуют обязательные поля: {readable}"],
        }

    accepted_rows = []
    errors = []

    for index, row in df.iterrows():
        excel_row_number = index + 2
        task_id = clean_text(row[columns["task_id"]])
        latitude = parse_float(row[columns["latitude"]])
        longitude = parse_float(row[columns["longitude"]])
        assigned_at = parse_datetime(row[columns["assigned_at"]])

        row_errors = []
        if not task_id:
            row_errors.append("пустой ID задачи")
        if latitude is None:
            row_errors.append("некорректная широта")
        if longitude is None:
            row_errors.append("некорректная долгота")
        if assigned_at is None:
            row_errors.append("некорректная дата назначения")
        if latitude is not None and not (55.0 <= latitude <= 56.2):
            row_errors.append("широта не похожа на координату Москвы")
        if longitude is not None and not (36.5 <= longitude <= 38.5):
            row_errors.append("долгота не похожа на координату Москвы")

        if row_errors:
            errors.append(f"Строка {excel_row_number}: " + "; ".join(row_errors))
            continue

        def optional(field: str):
            if field not in columns:
                return None
            return clean_text(row[columns[field]])

        accepted_rows.append((
            task_id,
            optional("category"),
            optional("object_group"),
            optional("object_name"),
            optional("status"),
            assigned_at,
            latitude,
            longitude,
            optional("task_link"),
            optional("violation_photo"),
            optional("fix_photo"),
            row_to_json(row),
        ))

    if not accepted_rows:
        return {
            "ok": False,
            "accepted": 0,
            "errors_count": len(errors),
            "errors": errors[:20],
        }

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM violations")
    cur.executemany("""
        INSERT INTO violations (
            task_id, category, object_group, object_name, status, assigned_at,
            latitude, longitude, task_link, violation_photo, fix_photo, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, accepted_rows)

    cur.execute("""
        INSERT INTO upload_log (filename, uploaded_at, accepted_count, error_count, errors_json)
        VALUES (?, ?, ?, ?, ?)
    """, (
        filename,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        len(accepted_rows),
        len(errors),
        json.dumps(errors[:100], ensure_ascii=False),
    ))

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "accepted": len(accepted_rows),
        "errors_count": len(errors),
        "errors": errors[:20],
    }
