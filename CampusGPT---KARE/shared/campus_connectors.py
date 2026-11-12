"""Reusable data-store and SMTP connectors.

Save credentials, test them, and open a client for the store an admin selected.
Secrets stay in the app's ``.env`` and ``data/integrations.json`` (both local).
API responses never return secret values.
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

ApplyFn = Callable[[str, dict[str, Any]], None]

_PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "supabase",
        "label": "Supabase",
        "kind": "database",
        "summary": "Postgres project URL, API key, and optional database URL.",
        "fields": [
            {"key": "url", "label": "Project URL", "type": "text", "env": "SUPABASE_URL", "placeholder": "https://xxxx.supabase.co", "required": True},
            {"key": "key", "label": "API key", "type": "password", "env": "SUPABASE_KEY", "secret": True, "required": True},
            {"key": "database_url", "label": "Database URL (optional)", "type": "password", "env": "SUPABASE_DB_URL", "secret": True, "placeholder": "postgresql://postgres:password@db.host:5432/postgres"},
        ],
    },
    {
        "id": "mongodb",
        "label": "MongoDB",
        "kind": "database",
        "summary": "MongoDB or Atlas connection string.",
        "fields": [
            {"key": "uri", "label": "Connection URI", "type": "password", "env": "MONGODB_URI", "secret": True, "required": True, "placeholder": "mongodb+srv://user:pass@cluster.mongodb.net"},
            {"key": "database", "label": "Database name", "type": "text", "env": "MONGODB_DB", "placeholder": "campus", "default": "campus"},
        ],
    },
    {
        "id": "s3",
        "label": "S3",
        "kind": "storage",
        "summary": "Amazon S3 or any S3-compatible endpoint (MinIO, Supabase Storage S3).",
        "fields": [
            {"key": "endpoint", "label": "Endpoint (optional)", "type": "text", "env": "S3_ENDPOINT", "placeholder": "https://s3.amazonaws.com"},
            {"key": "region", "label": "Region", "type": "text", "env": "S3_REGION", "placeholder": "us-east-1", "default": "us-east-1"},
            {"key": "bucket", "label": "Bucket", "type": "text", "env": "S3_BUCKET", "required": True},
            {"key": "access_key", "label": "Access key", "type": "password", "env": "S3_ACCESS_KEY", "secret": True, "required": True},
            {"key": "secret_key", "label": "Secret key", "type": "password", "env": "S3_SECRET_KEY", "secret": True, "required": True},
        ],
    },
    {
        "id": "smtp",
        "label": "Email (SMTP)",
        "kind": "email",
        "summary": "Alerts use this Gmail mailbox only: 99230041300@klu.ac.in. Host smtp.gmail.com, port 587, and a Google app password. Save it, then test. Every slip and alert uses this mailbox.",
        "fields": [
            {"key": "enabled", "label": "Enabled", "type": "bool", "env": "EMAIL_ENABLED", "default": True},
            {"key": "host", "label": "SMTP host", "type": "text", "env": "SMTP_HOST", "required": True, "default": "smtp.gmail.com"},
            {"key": "port", "label": "SMTP port", "type": "number", "env": "SMTP_PORT", "required": True, "default": 587},
            {"key": "user", "label": "SMTP user", "type": "text", "env": "SMTP_USER", "required": True, "placeholder": "99230041300@klu.ac.in", "default": "99230041300@klu.ac.in"},
            {"key": "password", "label": "Google app password", "type": "password", "env": "SMTP_PASSWORD", "secret": True, "required": True, "placeholder": "16-character app password"},
            {"key": "from_header", "label": "From header", "type": "text", "env": "SMTP_FROM", "placeholder": "KARE UIS <99230041300@klu.ac.in>", "default": "KARE UIS <99230041300@klu.ac.in>"},
        ],
    },
    {
        "id": "gemini",
        "label": "Gemini",
        "kind": "ai",
        "summary": "Campus-GPT uses this key for retrieval answers, admin thinking, and forecasts. The model may use only campus records and knowledge excerpts. It must refuse unethical requests and say when a figure was not measured.",
        "fields": [
            {"key": "api_key", "label": "Gemini API key", "type": "password", "env": "GEMINI_API_KEY", "secret": True, "required": True, "placeholder": "Paste the key from Google AI Studio"},
            {"key": "model", "label": "Chat model", "type": "text", "env": "GEMINI_CHAT_MODEL", "default": "gemini-flash-latest", "placeholder": "gemini-flash-latest"},
        ],
    },
]


def _is_data_store(kind: str) -> bool:
    return kind in {"database", "storage"}

_BY_ID = {p["id"]: p for p in _PROVIDERS}


def provider_ids() -> list[str]:
    return list(_BY_ID)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _format_env(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    text = "" if value is None else str(value)
    if text == "":
        return ""
    if any(ch in text for ch in " #\t\"'\\"):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def _parse_env_value(raw: str) -> str:
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1]
    return text.replace('\\"', '"').replace("\\\\", "\\")


def read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = _parse_env_value(value)
    return out


def update_env(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(updates)
    written: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            written.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in pending:
            written.append(f"{key}={_format_env(pending.pop(key))}")
        else:
            written.append(line)
    if pending and written and written[-1].strip():
        written.append("")
    for key, value in pending.items():
        written.append(f"{key}={_format_env(value)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(written) + "\n", encoding="utf-8")


class IntegrationHub:
    def __init__(self, store_path: Path, env_path: Path, on_apply: ApplyFn | None = None):
        self.store_path = store_path
        self.env_path = env_path
        self.on_apply = on_apply or (lambda _provider, _cfg: None)

    def _read_store(self) -> dict[str, Any]:
        if not self.store_path.exists():
            return {"active": "", "providers": {}}
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"active": "", "providers": {}}
        if not isinstance(data, dict):
            return {"active": "", "providers": {}}
        data.setdefault("active", "")
        data.setdefault("providers", {})
        return data

    def _write_store(self, data: dict[str, Any]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def resolved(self, provider_id: str) -> dict[str, Any]:
        spec = _BY_ID[provider_id]
        env = read_env(self.env_path)
        stored = (self._read_store().get("providers") or {}).get(provider_id) or {}
        values: dict[str, Any] = {}
        for field in spec["fields"]:
            key = field["key"]
            raw = stored.get(key)
            if raw in ("", None):
                raw = os.environ.get(field["env"])
            if raw in ("", None):
                raw = env.get(field["env"], field.get("default", ""))
            if field["type"] == "bool":
                values[key] = _truthy(raw) if raw not in ("", None) else bool(field.get("default", False))
            elif field["type"] == "number":
                try:
                    values[key] = int(raw) if raw not in ("", None) else int(field.get("default") or 0)
                except (TypeError, ValueError):
                    values[key] = int(field.get("default") or 0)
            else:
                values[key] = "" if raw is None else str(raw)
        return values

    def active(self) -> str:
        stored = (self._read_store().get("active") or "").strip()
        if stored in _BY_ID and _is_data_store(_BY_ID[stored]["kind"]):
            return stored
        env_active = read_env(self.env_path).get("ACTIVE_DATA_STORE", "").strip()
        if env_active in _BY_ID and _is_data_store(_BY_ID[env_active]["kind"]):
            return env_active
        return ""

    def _configured(self, provider_id: str, values: dict[str, Any]) -> bool:
        for field in _BY_ID[provider_id]["fields"]:
            if not field.get("required"):
                continue
            val = values.get(field["key"])
            if field["type"] == "bool":
                continue
            if val is None or str(val).strip() == "":
                return False
        return True

    def public(self) -> dict[str, Any]:
        providers = []
        for spec in _PROVIDERS:
            values = self.resolved(spec["id"])
            fields = []
            for field in spec["fields"]:
                secret = bool(field.get("secret"))
                raw = values.get(field["key"], "")
                fields.append(
                    {
                        "key": field["key"],
                        "label": field["label"],
                        "type": field["type"],
                        "placeholder": field.get("placeholder") or "",
                        "required": bool(field.get("required")),
                        "secret": secret,
                        "secret_set": bool(secret and str(raw).strip()),
                        "value": "" if secret else raw,
                    }
                )
            providers.append(
                {
                    "id": spec["id"],
                    "label": spec["label"],
                    "kind": spec["kind"],
                    "summary": spec["summary"],
                    "configured": self._configured(spec["id"], values),
                    "fields": fields,
                }
            )
        return {"active": self.active(), "providers": providers}

    def _merge(self, provider_id: str, incoming: dict[str, Any] | None) -> dict[str, Any]:
        current = self.resolved(provider_id)
        spec = _BY_ID[provider_id]
        secret_keys = {f["key"] for f in spec["fields"] if f.get("secret")}
        merged = dict(current)
        for key, value in (incoming or {}).items():
            if key not in {f["key"] for f in spec["fields"]}:
                continue
            field = next(f for f in spec["fields"] if f["key"] == key)
            if key in secret_keys and (value is None or str(value).strip() == ""):
                continue
            if field["type"] == "bool":
                merged[key] = _truthy(value)
            elif field["type"] == "number":
                merged[key] = int(value)
            else:
                merged[key] = str(value).strip()
        return merged

    def save(self, provider_id: str, incoming: dict[str, Any] | None, make_active: bool = False) -> dict[str, Any]:
        if provider_id not in _BY_ID:
            raise KeyError(provider_id)
        merged = self._merge(provider_id, incoming)
        data = self._read_store()
        data.setdefault("providers", {})[provider_id] = merged
        spec = _BY_ID[provider_id]
        if make_active and _is_data_store(spec["kind"]):
            data["active"] = provider_id
        self._write_store(data)
        env_updates = {field["env"]: merged.get(field["key"], "") for field in spec["fields"]}
        if _is_data_store(spec["kind"]) and (make_active or self.active() == provider_id):
            env_updates["ACTIVE_DATA_STORE"] = provider_id
            data["active"] = provider_id
            self._write_store(data)
        update_env(self.env_path, env_updates)
        self.on_apply(provider_id, merged)
        result = self.public()
        result["ok"] = True
        result["detail"] = f"Saved {spec['label']}."
        return result

    def test(self, provider_id: str, incoming: dict[str, Any] | None = None, send_to: str | None = None) -> dict[str, Any]:
        if provider_id not in _BY_ID:
            raise KeyError(provider_id)
        cfg = self._merge(provider_id, incoming)
        try:
            detail = _TESTERS[provider_id](cfg, send_to)
        except Exception as exc:  # noqa: BLE001 — return the connector error to the admin UI
            text = str(exc)[:500]
            if "getaddrinfo" in text or "Name or service not known" in text or "nodename nor servname" in text:
                text = "Could not resolve that host. Check the project URL or connection string."
            return {"ok": False, "provider": provider_id, "detail": text}
        return {"ok": True, "provider": provider_id, "detail": detail}

    def open_client(self, provider_id: str | None = None) -> Any:
        """Open the active data store, or a named one. SMTP is not a client."""
        chosen = provider_id or self.active()
        if chosen not in _BY_ID or not _is_data_store(_BY_ID[chosen]["kind"]):
            raise RuntimeError("Choose Supabase, MongoDB, or S3 before opening a client.")
        cfg = self.resolved(chosen)
        if not self._configured(chosen, cfg):
            raise RuntimeError(f"{_BY_ID[chosen]['label']} is not configured.")
        return _OPENERS[chosen](cfg)

    def apply_all(self) -> None:
        for spec in _PROVIDERS:
            self.on_apply(spec["id"], self.resolved(spec["id"]))


def _need(cfg: dict[str, Any], *keys: str) -> None:
    missing = [key for key in keys if not str(cfg.get(key) or "").strip()]
    if missing:
        raise ValueError("Missing " + ", ".join(missing))


def _clean_url(value: str) -> str:
    return str(value or "").strip().rstrip(".")


def _test_supabase(cfg: dict[str, Any], _send_to: str | None) -> str:
    _need(cfg, "url", "key")
    base = _clean_url(cfg["url"]).rstrip("/")
    response = httpx.get(
        f"{base}/auth/v1/health",
        headers={"apikey": cfg["key"], "Authorization": f"Bearer {cfg['key']}"},
        timeout=20.0,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Supabase health returned {response.status_code}: {response.text[:180]}")
    extra = ""
    database_url = str(cfg.get("database_url") or "").strip()
    if database_url:
        extra = " " + _ping_postgres(database_url)
    return f"Supabase API is reachable.{extra}".strip()


def _ping_postgres(database_url: str) -> str:
    import asyncio

    import asyncpg

    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgres://", "postgresql://")
    host = (urlparse(dsn).hostname or "").lower()
    ssl_mode: Any = "require" if "supabase" in host else None

    async def _run() -> int:
        conn = await asyncpg.connect(dsn, timeout=12, ssl=ssl_mode)
        try:
            return int(await conn.fetchval("select 1"))
        finally:
            await conn.close()

    if asyncio.run(_run()) != 1:
        raise RuntimeError("Postgres ping did not return 1.")
    return "Database URL accepted."


def _test_mongodb(cfg: dict[str, Any], _send_to: str | None) -> str:
    _need(cfg, "uri")
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise RuntimeError("Install pymongo in the backend environment to test MongoDB.") from exc
    client = MongoClient(cfg["uri"], serverSelectionTimeoutMS=8000)
    try:
        client.admin.command("ping")
        name = str(cfg.get("database") or "campus")
        client[name].command("ping")
    finally:
        client.close()
    return f"MongoDB ping succeeded for database '{cfg.get('database') or 'campus'}'."


def _test_s3(cfg: dict[str, Any], _send_to: str | None) -> str:
    _need(cfg, "bucket", "access_key", "secret_key")
    client = _s3_client(cfg)
    client.head_bucket(Bucket=cfg["bucket"])
    return f"S3 bucket '{cfg['bucket']}' is reachable."


def _test_gemini(cfg: dict[str, Any], _send_to: str | None) -> str:
    _need(cfg, "api_key")
    model = str(cfg.get("model") or "gemini-flash-latest").strip()
    if model.startswith("models/"):
        model = model.split("/", 1)[1]
    response = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": str(cfg["api_key"]).strip()},
        json={
            "contents": [{"parts": [{"text": "Reply with exactly: ready"}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 16},
        },
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Gemini returned {response.status_code}: {response.text[:180]}")
    return f"Gemini answered on {model}. Campus answers stay limited to measured records and knowledge excerpts."


def _test_smtp(cfg: dict[str, Any], send_to: str | None) -> str:
    if not _truthy(cfg.get("enabled", True)):
        raise RuntimeError("Email is disabled. Turn Enabled on, then test again.")
    _need(cfg, "host", "user", "password")
    host = str(cfg["host"]).strip()
    port = int(cfg.get("port") or 587)
    user = str(cfg["user"]).strip()
    password = str(cfg["password"]).replace(" ", "").strip()
    ctx = ssl.create_default_context()
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=25)
    else:
        server = smtplib.SMTP(host, port, timeout=25)
        server.ehlo()
        server.starttls(context=ctx)
        server.ehlo()
    try:
        server.login(user, password)
        target = (send_to or "").strip()
        if target:
            msg = MIMEText("Campus connector test. SMTP login and send succeeded.", "plain", "utf-8")
            msg["Subject"] = "SMTP connection test"
            msg["From"] = str(cfg.get("from_header") or user)
            msg["To"] = target
            server.send_message(msg, from_addr=user, to_addrs=[target])
            return f"SMTP login succeeded and a test message was sent to {target}."
    finally:
        try:
            server.quit()
        except Exception:
            pass
    return f"SMTP login succeeded for {user} via {host}:{port}."


def _open_supabase(cfg: dict[str, Any]) -> httpx.Client:
    base = _clean_url(cfg["url"]).rstrip("/")
    return httpx.Client(
        base_url=f"{base}/rest/v1",
        headers={"apikey": cfg["key"], "Authorization": f"Bearer {cfg['key']}"},
        timeout=30.0,
    )


def _open_mongodb(cfg: dict[str, Any]) -> Any:
    from pymongo import MongoClient

    client = MongoClient(cfg["uri"], serverSelectionTimeoutMS=8000)
    return client[str(cfg.get("database") or "campus")]


def _s3_client(cfg: dict[str, Any]) -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("Install boto3 in the backend environment to use S3.") from exc
    endpoint = str(cfg.get("endpoint") or "").strip() or None
    return boto3.client(
        "s3",
        region_name=str(cfg.get("region") or "us-east-1"),
        aws_access_key_id=cfg["access_key"],
        aws_secret_access_key=cfg["secret_key"],
        endpoint_url=endpoint,
    )


def _open_s3(cfg: dict[str, Any]) -> Any:
    return _s3_client(cfg)


_TESTERS = {
    "supabase": _test_supabase,
    "mongodb": _test_mongodb,
    "s3": _test_s3,
    "smtp": _test_smtp,
    "gemini": _test_gemini,
}
_OPENERS = {
    "supabase": _open_supabase,
    "mongodb": _open_mongodb,
    "s3": _open_s3,
}
