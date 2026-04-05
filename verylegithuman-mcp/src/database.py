"""Async SQLite database manager for persona persistence.

Uses raw aiosqlite instead of SQLAlchemy async to avoid greenlet
compatibility issues with Python 3.14.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

import aiosqlite

from .config import DB_DIR

logger = logging.getLogger(__name__)

DB_PATH = DB_DIR / "verylegithuman.db"

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS personas (
    id TEXT PRIMARY KEY,
    codename TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    gender TEXT,
    date_of_birth TEXT,
    age INTEGER,
    email_personal TEXT,
    phone TEXT,
    address_street TEXT,
    address_city TEXT,
    address_state TEXT,
    address_zip TEXT,
    address_country TEXT,
    nationality TEXT,
    locale TEXT,
    occupation TEXT,
    company TEXT,
    bio TEXT,
    face_url TEXT,
    face_source TEXT DEFAULT 'none',
    usernames_json TEXT DEFAULT '{}',
    username_availability_json TEXT DEFAULT '{}',
    metadata_json TEXT DEFAULT '{}',
    status TEXT DEFAULT 'active',
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_personas_codename ON personas(codename);
CREATE INDEX IF NOT EXISTS idx_personas_status ON personas(status);

CREATE TABLE IF NOT EXISTS persona_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    persona_id TEXT NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_notes_persona ON persona_notes(persona_id);

CREATE TABLE IF NOT EXISTS email_accounts (
    id TEXT PRIMARY KEY,
    persona_id TEXT REFERENCES personas(id) ON DELETE SET NULL,
    provider TEXT NOT NULL,
    address TEXT NOT NULL,
    password TEXT,
    token TEXT,
    domain TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT,
    last_checked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_email_persona ON email_accounts(persona_id);
CREATE INDEX IF NOT EXISTS idx_email_address ON email_accounts(address);

CREATE TABLE IF NOT EXISTS email_messages (
    id TEXT PRIMARY KEY,
    email_account_id TEXT NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
    from_address TEXT,
    subject TEXT,
    body_text TEXT,
    body_html TEXT,
    received_at TEXT,
    is_read INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_email_msg_account ON email_messages(email_account_id);

CREATE TABLE IF NOT EXISTS phone_numbers (
    id TEXT PRIMARY KEY,
    persona_id TEXT REFERENCES personas(id) ON DELETE SET NULL,
    provider TEXT NOT NULL,
    number TEXT NOT NULL,
    country TEXT,
    capabilities_json TEXT DEFAULT '{}',
    status TEXT DEFAULT 'active',
    provider_id TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_phone_persona ON phone_numbers(persona_id);

CREATE TABLE IF NOT EXISTS sms_messages (
    id TEXT PRIMARY KEY,
    phone_number_id TEXT NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    from_number TEXT,
    body TEXT,
    received_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sms_phone ON sms_messages(phone_number_id);

CREATE TABLE IF NOT EXISTS proxy_configs (
    id TEXT PRIMARY KEY,
    persona_id TEXT REFERENCES personas(id) ON DELETE SET NULL,
    provider TEXT NOT NULL,
    proxy_url TEXT,
    country TEXT,
    city TEXT,
    sticky_session TEXT,
    rotation_minutes INTEGER DEFAULT 0,
    last_rotated_at TEXT,
    verified_ip TEXT,
    verified_country TEXT,
    verified_at TEXT,
    status TEXT DEFAULT 'active',
    metadata_json TEXT DEFAULT '{}',
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_proxy_persona ON proxy_configs(persona_id);
CREATE INDEX IF NOT EXISTS idx_proxy_provider ON proxy_configs(provider);

CREATE TABLE IF NOT EXISTS social_accounts (
    id TEXT PRIMARY KEY,
    persona_id TEXT REFERENCES personas(id) ON DELETE SET NULL,
    platform TEXT NOT NULL,
    username TEXT,
    credentials_json TEXT DEFAULT '{}',
    postiz_integration_id TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_social_persona ON social_accounts(persona_id);
CREATE INDEX IF NOT EXISTS idx_social_platform ON social_accounts(platform);

CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    social_account_id TEXT REFERENCES social_accounts(id) ON DELETE SET NULL,
    platform TEXT NOT NULL,
    content TEXT,
    media_urls_json TEXT DEFAULT '[]',
    scheduled_at TEXT,
    posted_at TEXT,
    postiz_post_id TEXT,
    status TEXT DEFAULT 'draft',
    engagement_json TEXT DEFAULT '{}',
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_posts_account ON social_posts(social_account_id);
CREATE INDEX IF NOT EXISTS idx_posts_status ON social_posts(status);
"""

_PERSONA_COLS = [
    "id", "codename", "first_name", "last_name", "full_name",
    "gender", "date_of_birth", "age", "email_personal", "phone",
    "address_street", "address_city", "address_state", "address_zip",
    "address_country", "nationality", "locale", "occupation", "company",
    "bio", "face_url", "face_source", "usernames_json",
    "username_availability_json", "metadata_json", "status",
    "created_at", "updated_at",
]


def _row_to_dict(row: aiosqlite.Row) -> dict:
    """Convert a database row to a persona dict."""
    d = dict(row)
    d["address"] = {
        "street": d.pop("address_street", ""),
        "city": d.pop("address_city", ""),
        "state": d.pop("address_state", ""),
        "zip": d.pop("address_zip", ""),
        "country": d.pop("address_country", ""),
    }
    d["usernames"] = json.loads(d.pop("usernames_json", "{}") or "{}")
    d["username_availability"] = json.loads(d.pop("username_availability_json", "{}") or "{}")
    d["metadata"] = json.loads(d.pop("metadata_json", "{}") or "{}")
    d["notes"] = []
    return d


def _row_to_summary(row: aiosqlite.Row) -> dict:
    d = dict(row)
    return {
        "id": d["id"],
        "codename": d["codename"],
        "full_name": d["full_name"],
        "gender": d.get("gender"),
        "age": d.get("age"),
        "locale": d.get("locale"),
        "status": d.get("status"),
        "face_source": d.get("face_source", "none"),
        "created_at": d.get("created_at"),
    }


class DatabaseManager:
    """Manages async SQLite operations for persona storage."""

    def __init__(self) -> None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self._db_path = str(DB_PATH)

    async def _conn(self) -> aiosqlite.Connection:
        """Open a fresh connection. Caller must close it."""
        conn = await aiosqlite.connect(self._db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        return conn

    async def init_db(self) -> None:
        conn = await self._conn()
        try:
            await conn.executescript(_CREATE_TABLES)
            await conn.commit()
        finally:
            await conn.close()
        logger.info("Database initialized at %s", self._db_path)

    async def close(self) -> None:
        pass  # Connections are per-operation

    # --- Persona CRUD ---

    async def create_persona(self, data: dict) -> dict:
        now = datetime.utcnow().isoformat()
        data["created_at"] = now
        data["updated_at"] = now

        cols = [c for c in _PERSONA_COLS if c in data]
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        values = [data[c] for c in cols]

        conn = await self._conn()
        try:
            await conn.execute(f"INSERT INTO personas ({col_names}) VALUES ({placeholders})", values)
            await conn.commit()
            cursor = await conn.execute("SELECT * FROM personas WHERE id = ?", (data["id"],))
            row = await cursor.fetchone()
            return _row_to_dict(row)
        finally:
            await conn.close()

    async def get_persona(self, persona_id: Optional[str] = None, codename: Optional[str] = None) -> Optional[dict]:
        if not persona_id and not codename:
            return None

        conn = await self._conn()
        try:
            if persona_id:
                cursor = await conn.execute("SELECT * FROM personas WHERE id = ?", (persona_id,))
            else:
                cursor = await conn.execute("SELECT * FROM personas WHERE codename = ?", (codename,))
            row = await cursor.fetchone()
            if not row:
                return None
            persona = _row_to_dict(row)
            cursor2 = await conn.execute(
                "SELECT id, persona_id, note, created_at FROM persona_notes WHERE persona_id = ? ORDER BY created_at",
                (persona["id"],),
            )
            notes = await cursor2.fetchall()
            persona["notes"] = [dict(n) for n in notes]
            return persona
        finally:
            await conn.close()

    async def update_persona(self, persona_id: str, updates: dict) -> Optional[dict]:
        col_map = {
            "usernames": "usernames_json",
            "username_availability": "username_availability_json",
            "metadata": "metadata_json",
            "extra_metadata": "metadata_json",
        }
        sets = []
        values = []
        for key, val in updates.items():
            col = col_map.get(key, key)
            if col in ("usernames_json", "username_availability_json", "metadata_json"):
                val = json.dumps(val)
            if col in _PERSONA_COLS:
                sets.append(f"{col} = ?")
                values.append(val)

        if not sets:
            return None

        sets.append("updated_at = ?")
        values.append(datetime.utcnow().isoformat())
        values.append(persona_id)

        conn = await self._conn()
        try:
            sql = f"UPDATE personas SET {', '.join(sets)} WHERE id = ?"
            await conn.execute(sql, values)
            await conn.commit()
        finally:
            await conn.close()

        return await self.get_persona(persona_id=persona_id)

    async def list_personas(
        self,
        status: Optional[str] = None,
        locale: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if locale:
            conditions.append("locale = ?")
            params.append(locale)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM personas {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = await self._conn()
        try:
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [_row_to_summary(r) for r in rows]
        finally:
            await conn.close()

    async def delete_persona(self, persona_id: str) -> bool:
        conn = await self._conn()
        try:
            cursor = await conn.execute("DELETE FROM personas WHERE id = ?", (persona_id,))
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    # --- Notes ---

    async def add_note(self, persona_id: str, note: str) -> dict:
        now = datetime.utcnow().isoformat()
        conn = await self._conn()
        try:
            cursor = await conn.execute(
                "INSERT INTO persona_notes (persona_id, note, created_at) VALUES (?, ?, ?)",
                (persona_id, note, now),
            )
            await conn.commit()
            return {"id": cursor.lastrowid, "persona_id": persona_id, "note": note, "created_at": now}
        finally:
            await conn.close()

    # --- Username updates ---

    async def assign_username(self, persona_id: str, platform: str, username: str) -> Optional[dict]:
        persona = await self.get_persona(persona_id=persona_id)
        if not persona:
            return None
        current = persona["usernames"]
        current[platform] = username
        return await self.update_persona(persona_id, {"usernames": current})

    async def update_face(self, persona_id: str, face_url: str, face_source: str) -> Optional[dict]:
        return await self.update_persona(persona_id, {"face_url": face_url, "face_source": face_source})

    # --- Email Accounts ---

    async def create_email_account(self, data: dict) -> dict:
        data.setdefault("id", str(uuid.uuid4()))
        data.setdefault("created_at", datetime.utcnow().isoformat())
        data.setdefault("status", "active")
        cols = ["id", "persona_id", "provider", "address", "password", "token", "domain", "status", "created_at"]
        present = [c for c in cols if c in data]
        conn = await self._conn()
        try:
            await conn.execute(
                f"INSERT INTO email_accounts ({', '.join(present)}) VALUES ({', '.join(['?'] * len(present))})",
                [data[c] for c in present],
            )
            await conn.commit()
            cursor = await conn.execute("SELECT * FROM email_accounts WHERE id = ?", (data["id"],))
            row = await cursor.fetchone()
            return dict(row)
        finally:
            await conn.close()

    async def get_email_account(self, email_id: Optional[str] = None, address: Optional[str] = None) -> Optional[dict]:
        conn = await self._conn()
        try:
            if email_id:
                cursor = await conn.execute("SELECT * FROM email_accounts WHERE id = ?", (email_id,))
            elif address:
                cursor = await conn.execute("SELECT * FROM email_accounts WHERE address = ?", (address,))
            else:
                return None
            row = await cursor.fetchone()
            return dict(row) if row else None
        finally:
            await conn.close()

    async def list_email_accounts(self, persona_id: Optional[str] = None, provider: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
        conditions, params = [], []
        if persona_id:
            conditions.append("persona_id = ?")
            params.append(persona_id)
        if provider:
            conditions.append("provider = ?")
            params.append(provider)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        conn = await self._conn()
        try:
            cursor = await conn.execute(f"SELECT * FROM email_accounts {where} ORDER BY created_at DESC", params)
            return [dict(r) for r in await cursor.fetchall()]
        finally:
            await conn.close()

    async def update_email_account(self, email_id: str, updates: dict) -> Optional[dict]:
        sets, values = [], []
        for k, v in updates.items():
            sets.append(f"{k} = ?")
            values.append(v)
        if not sets:
            return None
        values.append(email_id)
        conn = await self._conn()
        try:
            await conn.execute(f"UPDATE email_accounts SET {', '.join(sets)} WHERE id = ?", values)
            await conn.commit()
            cursor = await conn.execute("SELECT * FROM email_accounts WHERE id = ?", (email_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
        finally:
            await conn.close()

    async def save_email_message(self, data: dict) -> dict:
        data.setdefault("is_read", 0)
        cols = ["id", "email_account_id", "from_address", "subject", "body_text", "body_html", "received_at", "is_read"]
        present = [c for c in cols if c in data]
        conn = await self._conn()
        try:
            await conn.execute(
                f"INSERT OR IGNORE INTO email_messages ({', '.join(present)}) VALUES ({', '.join(['?'] * len(present))})",
                [data[c] for c in present],
            )
            await conn.commit()
            cursor = await conn.execute("SELECT * FROM email_messages WHERE id = ?", (data["id"],))
            row = await cursor.fetchone()
            return dict(row) if row else data
        finally:
            await conn.close()

    async def get_email_messages(self, email_account_id: str, limit: int = 20) -> list[dict]:
        conn = await self._conn()
        try:
            cursor = await conn.execute(
                "SELECT * FROM email_messages WHERE email_account_id = ? ORDER BY received_at DESC LIMIT ?",
                (email_account_id, limit),
            )
            return [dict(r) for r in await cursor.fetchall()]
        finally:
            await conn.close()

    async def get_email_message(self, message_id: str) -> Optional[dict]:
        conn = await self._conn()
        try:
            cursor = await conn.execute("SELECT * FROM email_messages WHERE id = ?", (message_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
        finally:
            await conn.close()

    # --- Phone Numbers ---

    async def create_phone_number(self, data: dict) -> dict:
        data.setdefault("id", str(uuid.uuid4()))
        data.setdefault("created_at", datetime.utcnow().isoformat())
        data.setdefault("status", "active")
        if "capabilities" in data and isinstance(data["capabilities"], dict):
            data["capabilities_json"] = json.dumps(data.pop("capabilities"))
        cols = ["id", "persona_id", "provider", "number", "country", "capabilities_json", "status", "provider_id", "created_at"]
        present = [c for c in cols if c in data]
        conn = await self._conn()
        try:
            await conn.execute(
                f"INSERT INTO phone_numbers ({', '.join(present)}) VALUES ({', '.join(['?'] * len(present))})",
                [data[c] for c in present],
            )
            await conn.commit()
            cursor = await conn.execute("SELECT * FROM phone_numbers WHERE id = ?", (data["id"],))
            row = await cursor.fetchone()
            d = dict(row)
            d["capabilities"] = json.loads(d.pop("capabilities_json", "{}") or "{}")
            return d
        finally:
            await conn.close()

    async def get_phone_number(self, phone_id: str) -> Optional[dict]:
        conn = await self._conn()
        try:
            cursor = await conn.execute("SELECT * FROM phone_numbers WHERE id = ?", (phone_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["capabilities"] = json.loads(d.pop("capabilities_json", "{}") or "{}")
            return d
        finally:
            await conn.close()

    async def list_phone_numbers(self, persona_id: Optional[str] = None, provider: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
        conditions, params = [], []
        if persona_id:
            conditions.append("persona_id = ?")
            params.append(persona_id)
        if provider:
            conditions.append("provider = ?")
            params.append(provider)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        conn = await self._conn()
        try:
            cursor = await conn.execute(f"SELECT * FROM phone_numbers {where} ORDER BY created_at DESC", params)
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["capabilities"] = json.loads(d.pop("capabilities_json", "{}") or "{}")
                result.append(d)
            return result
        finally:
            await conn.close()

    async def update_phone_status(self, phone_id: str, status: str) -> Optional[dict]:
        conn = await self._conn()
        try:
            await conn.execute("UPDATE phone_numbers SET status = ? WHERE id = ?", (status, phone_id))
            await conn.commit()
        finally:
            await conn.close()
        return await self.get_phone_number(phone_id)

    async def save_sms_message(self, data: dict) -> dict:
        data.setdefault("id", str(uuid.uuid4()))
        cols = ["id", "phone_number_id", "from_number", "body", "received_at"]
        present = [c for c in cols if c in data]
        conn = await self._conn()
        try:
            await conn.execute(
                f"INSERT OR IGNORE INTO sms_messages ({', '.join(present)}) VALUES ({', '.join(['?'] * len(present))})",
                [data[c] for c in present],
            )
            await conn.commit()
            return data
        finally:
            await conn.close()

    async def get_sms_messages(self, phone_number_id: str, limit: int = 20) -> list[dict]:
        conn = await self._conn()
        try:
            cursor = await conn.execute(
                "SELECT * FROM sms_messages WHERE phone_number_id = ? ORDER BY received_at DESC LIMIT ?",
                (phone_number_id, limit),
            )
            return [dict(r) for r in await cursor.fetchall()]
        finally:
            await conn.close()

    # --- Proxy Configs ---

    async def create_proxy_config(self, data: dict) -> dict:
        data.setdefault("id", str(uuid.uuid4()))
        data.setdefault("created_at", datetime.utcnow().isoformat())
        data.setdefault("status", "active")
        if "metadata" in data and isinstance(data["metadata"], dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"))
        cols = ["id", "persona_id", "provider", "proxy_url", "country", "city",
                "sticky_session", "rotation_minutes", "status", "metadata_json", "created_at"]
        present = [c for c in cols if c in data]
        conn = await self._conn()
        try:
            await conn.execute(
                f"INSERT INTO proxy_configs ({', '.join(present)}) VALUES ({', '.join(['?'] * len(present))})",
                [data[c] for c in present],
            )
            await conn.commit()
            cursor = await conn.execute("SELECT * FROM proxy_configs WHERE id = ?", (data["id"],))
            row = await cursor.fetchone()
            d = dict(row)
            d["metadata"] = json.loads(d.pop("metadata_json", "{}") or "{}")
            return d
        finally:
            await conn.close()

    async def get_proxy_config(self, proxy_id: str) -> Optional[dict]:
        conn = await self._conn()
        try:
            cursor = await conn.execute("SELECT * FROM proxy_configs WHERE id = ?", (proxy_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["metadata"] = json.loads(d.pop("metadata_json", "{}") or "{}")
            return d
        finally:
            await conn.close()

    async def get_proxy_for_persona(self, persona_id: str) -> Optional[dict]:
        conn = await self._conn()
        try:
            cursor = await conn.execute(
                "SELECT * FROM proxy_configs WHERE persona_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                (persona_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["metadata"] = json.loads(d.pop("metadata_json", "{}") or "{}")
            return d
        finally:
            await conn.close()

    async def list_proxy_configs(self, persona_id: Optional[str] = None, provider: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
        conditions, params = [], []
        if persona_id:
            conditions.append("persona_id = ?")
            params.append(persona_id)
        if provider:
            conditions.append("provider = ?")
            params.append(provider)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        conn = await self._conn()
        try:
            cursor = await conn.execute(f"SELECT * FROM proxy_configs {where} ORDER BY created_at DESC", params)
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["metadata"] = json.loads(d.pop("metadata_json", "{}") or "{}")
                result.append(d)
            return result
        finally:
            await conn.close()

    async def update_proxy_config(self, proxy_id: str, updates: dict) -> Optional[dict]:
        if "metadata" in updates and isinstance(updates["metadata"], dict):
            updates["metadata_json"] = json.dumps(updates.pop("metadata"))
        sets, values = [], []
        for k, v in updates.items():
            sets.append(f"{k} = ?")
            values.append(v)
        if not sets:
            return None
        values.append(proxy_id)
        conn = await self._conn()
        try:
            await conn.execute(f"UPDATE proxy_configs SET {', '.join(sets)} WHERE id = ?", values)
            await conn.commit()
        finally:
            await conn.close()
        return await self.get_proxy_config(proxy_id)

    async def delete_proxy_config(self, proxy_id: str) -> bool:
        conn = await self._conn()
        try:
            cursor = await conn.execute("DELETE FROM proxy_configs WHERE id = ?", (proxy_id,))
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    # --- Social Accounts ---

    async def create_social_account(self, data: dict) -> dict:
        data.setdefault("id", str(uuid.uuid4()))
        data.setdefault("created_at", datetime.utcnow().isoformat())
        data.setdefault("status", "active")
        if "credentials" in data and isinstance(data["credentials"], dict):
            data["credentials_json"] = json.dumps(data.pop("credentials"))
        cols = ["id", "persona_id", "platform", "username", "credentials_json", "postiz_integration_id", "status", "created_at"]
        present = [c for c in cols if c in data]
        conn = await self._conn()
        try:
            await conn.execute(
                f"INSERT INTO social_accounts ({', '.join(present)}) VALUES ({', '.join(['?'] * len(present))})",
                [data[c] for c in present],
            )
            await conn.commit()
            cursor = await conn.execute("SELECT * FROM social_accounts WHERE id = ?", (data["id"],))
            row = await cursor.fetchone()
            d = dict(row)
            d["credentials"] = json.loads(d.pop("credentials_json", "{}") or "{}")
            return d
        finally:
            await conn.close()

    async def get_social_account(self, account_id: str) -> Optional[dict]:
        conn = await self._conn()
        try:
            cursor = await conn.execute("SELECT * FROM social_accounts WHERE id = ?", (account_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["credentials"] = json.loads(d.pop("credentials_json", "{}") or "{}")
            return d
        finally:
            await conn.close()

    async def get_social_account_for_persona(self, persona_id: str, platform: str) -> Optional[dict]:
        conn = await self._conn()
        try:
            cursor = await conn.execute(
                "SELECT * FROM social_accounts WHERE persona_id = ? AND platform = ? AND status = 'active' LIMIT 1",
                (persona_id, platform),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["credentials"] = json.loads(d.pop("credentials_json", "{}") or "{}")
            return d
        finally:
            await conn.close()

    async def list_social_accounts(self, persona_id: Optional[str] = None, platform: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
        conditions, params = [], []
        if persona_id:
            conditions.append("persona_id = ?")
            params.append(persona_id)
        if platform:
            conditions.append("platform = ?")
            params.append(platform)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        conn = await self._conn()
        try:
            cursor = await conn.execute(f"SELECT * FROM social_accounts {where} ORDER BY created_at DESC", params)
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["credentials"] = json.loads(d.pop("credentials_json", "{}") or "{}")
                result.append(d)
            return result
        finally:
            await conn.close()

    async def update_social_account(self, account_id: str, updates: dict) -> Optional[dict]:
        if "credentials" in updates and isinstance(updates["credentials"], dict):
            updates["credentials_json"] = json.dumps(updates.pop("credentials"))
        sets, values = [], []
        for k, v in updates.items():
            sets.append(f"{k} = ?")
            values.append(v)
        if not sets:
            return None
        values.append(account_id)
        conn = await self._conn()
        try:
            await conn.execute(f"UPDATE social_accounts SET {', '.join(sets)} WHERE id = ?", values)
            await conn.commit()
        finally:
            await conn.close()
        return await self.get_social_account(account_id)

    # --- Social Posts ---

    async def create_social_post(self, data: dict) -> dict:
        data.setdefault("id", str(uuid.uuid4()))
        data.setdefault("created_at", datetime.utcnow().isoformat())
        data.setdefault("status", "draft")
        if "media_urls" in data and isinstance(data["media_urls"], list):
            data["media_urls_json"] = json.dumps(data.pop("media_urls"))
        if "engagement" in data and isinstance(data["engagement"], dict):
            data["engagement_json"] = json.dumps(data.pop("engagement"))
        cols = ["id", "social_account_id", "platform", "content", "media_urls_json",
                "scheduled_at", "posted_at", "postiz_post_id", "status", "engagement_json", "created_at"]
        present = [c for c in cols if c in data]
        conn = await self._conn()
        try:
            await conn.execute(
                f"INSERT INTO social_posts ({', '.join(present)}) VALUES ({', '.join(['?'] * len(present))})",
                [data[c] for c in present],
            )
            await conn.commit()
            cursor = await conn.execute("SELECT * FROM social_posts WHERE id = ?", (data["id"],))
            row = await cursor.fetchone()
            d = dict(row)
            d["media_urls"] = json.loads(d.pop("media_urls_json", "[]") or "[]")
            d["engagement"] = json.loads(d.pop("engagement_json", "{}") or "{}")
            return d
        finally:
            await conn.close()

    async def list_social_posts(self, social_account_id: Optional[str] = None, platform: Optional[str] = None, status: Optional[str] = None, limit: int = 50) -> list[dict]:
        conditions, params = [], []
        if social_account_id:
            conditions.append("social_account_id = ?")
            params.append(social_account_id)
        if platform:
            conditions.append("platform = ?")
            params.append(platform)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        conn = await self._conn()
        try:
            cursor = await conn.execute(f"SELECT * FROM social_posts {where} ORDER BY created_at DESC LIMIT ?", params)
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["media_urls"] = json.loads(d.pop("media_urls_json", "[]") or "[]")
                d["engagement"] = json.loads(d.pop("engagement_json", "{}") or "{}")
                result.append(d)
            return result
        finally:
            await conn.close()

    async def update_social_post(self, post_id: str, updates: dict) -> Optional[dict]:
        if "engagement" in updates and isinstance(updates["engagement"], dict):
            updates["engagement_json"] = json.dumps(updates.pop("engagement"))
        if "media_urls" in updates and isinstance(updates["media_urls"], list):
            updates["media_urls_json"] = json.dumps(updates.pop("media_urls"))
        sets, values = [], []
        for k, v in updates.items():
            sets.append(f"{k} = ?")
            values.append(v)
        if not sets:
            return None
        values.append(post_id)
        conn = await self._conn()
        try:
            await conn.execute(f"UPDATE social_posts SET {', '.join(sets)} WHERE id = ?", values)
            await conn.commit()
            cursor = await conn.execute("SELECT * FROM social_posts WHERE id = ?", (post_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["media_urls"] = json.loads(d.pop("media_urls_json", "[]") or "[]")
            d["engagement"] = json.loads(d.pop("engagement_json", "{}") or "{}")
            return d
        finally:
            await conn.close()

    async def get_activity_summary(self, persona_id: str, days_back: int = 30) -> dict:
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        conn = await self._conn()
        try:
            # Get accounts for persona
            cursor = await conn.execute("SELECT id, platform FROM social_accounts WHERE persona_id = ?", (persona_id,))
            accounts = await cursor.fetchall()
            account_ids = [dict(a)["id"] for a in accounts]
            platforms = list(set(dict(a)["platform"] for a in accounts))

            if not account_ids:
                return {"persona_id": persona_id, "post_count": 0, "platforms_active": [], "days_back": days_back}

            placeholders = ", ".join(["?"] * len(account_ids))
            cursor2 = await conn.execute(
                f"SELECT COUNT(*) as cnt FROM social_posts WHERE social_account_id IN ({placeholders}) AND created_at >= ?",
                account_ids + [cutoff],
            )
            row = await cursor2.fetchone()
            post_count = dict(row)["cnt"]

            cursor3 = await conn.execute(
                f"SELECT MAX(posted_at) as last_post FROM social_posts WHERE social_account_id IN ({placeholders}) AND posted_at IS NOT NULL",
                account_ids,
            )
            row3 = await cursor3.fetchone()
            last_post = dict(row3).get("last_post")

            return {
                "persona_id": persona_id,
                "post_count": post_count,
                "platforms_active": platforms,
                "avg_posts_per_day": round(post_count / max(days_back, 1), 2),
                "last_post_time": last_post,
                "days_back": days_back,
            }
        finally:
            await conn.close()
