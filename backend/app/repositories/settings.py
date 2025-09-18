from __future__ import annotations

from typing import Any, Dict, Optional
import json

from sqlmodel import Session, select

from app.models.setting import Setting
from app.models.app_settings import (
    AppSettingsModel,
    migrate_settings_dict,
    deep_merge_dict,
)


DEFAULT_SETTINGS: Dict[str, Any] = AppSettingsModel().to_dict()


APP_SETTINGS_KEY = "app_settings"


def _load_json_or_default(value_json: Optional[str]) -> Dict[str, Any]:
    if not value_json:
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    try:
        parsed = json.loads(value_json)
        # migrate legacy keys
        migrated = migrate_settings_dict(parsed)
        # deep-merge defaults to ensure new fields exist
        merged: Dict[str, Any] = json.loads(json.dumps(DEFAULT_SETTINGS))
        merged = deep_merge_dict(merged, migrated)
        # validate with Pydantic to coerce and ensure types
        model = AppSettingsModel(**merged)
        return model.to_dict()
    except Exception:
        return json.loads(json.dumps(DEFAULT_SETTINGS))


def get_app_settings(session: Session) -> Dict[str, Any]:
    stmt = select(Setting).where(Setting.key == APP_SETTINGS_KEY)
    row = session.exec(stmt).first()
    return _load_json_or_default(row.value_json if row else None)


def save_app_settings(session: Session, settings_data: Dict[str, Any]) -> Dict[str, Any]:
    # Merge with existing to avoid losing unknown fields
    current = get_app_settings(session)
    # migrate input patch too
    incoming = migrate_settings_dict(settings_data)
    merged = deep_merge_dict(current, incoming)
    # validate and normalize via Pydantic
    model = AppSettingsModel(**merged)
    normalized = model.to_dict()
    payload = json.dumps(normalized, ensure_ascii=False)
    stmt = select(Setting).where(Setting.key == APP_SETTINGS_KEY)
    row = session.exec(stmt).first()
    if row is None:
        row = Setting(key=APP_SETTINGS_KEY, value_json=payload)
        session.add(row)
    else:
        row.value_json = payload
    session.commit()
    return normalized


