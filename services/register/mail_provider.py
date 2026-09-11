from __future__ import annotations

import hashlib
import random
import re
import string
import time
from datetime import datetime, timezone
from email import message_from_string, policy
from email.utils import parsedate_to_datetime
from threading import Lock
from typing import Any, Callable, TypeVar

import requests
from curl_cffi import requests as curl_requests

from services.register.browser_relay import browser_relay


ResultT = TypeVar("ResultT")
domain_lock = Lock()
provider_lock = Lock()
domain_index = 0
provider_index = 0


def _config(mail_config: dict) -> dict:
    return {
        "request_timeout": float(mail_config.get("request_timeout") or 30),
        "wait_timeout": float(mail_config.get("wait_timeout") or 30),
        "wait_interval": float(mail_config.get("wait_interval") or 2),
        "user_agent": str(mail_config.get("user_agent") or "Mozilla/5.0"),
    }


def _random_mailbox_name() -> str:
    return f"{''.join(random.choices(string.ascii_lowercase, k=5))}{''.join(random.choices(string.digits, k=random.randint(1, 3)))}{''.join(random.choices(string.ascii_lowercase, k=random.randint(1, 3)))}"


def _random_subdomain_label() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(4, 10)))


def _next_domain(domains: list[str]) -> str:
    global domain_index
    domains = [str(item).strip() for item in domains if str(item).strip()]
    if not domains:
        raise RuntimeError("mail.domain không được để trống")
    if len(domains) == 1:
        return domains[0]
    with domain_lock:
        value = domains[domain_index % len(domains)]
        domain_index = (domain_index + 1) % len(domains)
        return value


def _parse_received_at(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    text = str(value or "").strip()
    if not text:
        return None
    try:
        date = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
        return date if date.tzinfo else date.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    try:
        date = parsedate_to_datetime(text)
        return date if date.tzinfo else date.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _extract_content(data: dict[str, Any]) -> tuple[str, str]:
    text_content = str(data.get("text_content") or data.get("text") or data.get("body") or data.get("content") or "")
    html_content = str(data.get("html_content") or data.get("html") or data.get("html_body") or data.get("body_html") or "")
    if text_content or html_content:
        return text_content, html_content
    raw = data.get("raw")
    if not isinstance(raw, str) or not raw.strip():
        return "", ""
    try:
        parsed = message_from_string(raw, policy=policy.default)
    except Exception:
        return raw, ""
    plain: list[str] = []
    html: list[str] = []
    for part in parsed.walk() if parsed.is_multipart() else [parsed]:
        if part.get_content_maintype() == "multipart":
            continue
        try:
            payload = part.get_content()
        except Exception:
            payload = ""
        if not payload:
            continue
        if part.get_content_type() == "text/html":
            html.append(str(payload))
        else:
            plain.append(str(payload))
    return "\n".join(plain).strip(), "\n".join(html).strip()


def _extract_text_candidates(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for key in ("address", "email", "name", "value"):
            if value.get(key):
                out.extend(_extract_text_candidates(value.get(key)))
        return out
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_extract_text_candidates(item))
        return out
    return []


def _message_matches_email(data: dict[str, Any], email: str) -> bool:
    target = str(email or "").strip().lower()
    candidates: list[str] = []
    for key in ("to", "mailTo", "receiver", "receivers", "address", "email", "envelope_to"):
        if key in data:
            candidates.extend(_extract_text_candidates(data.get(key)))
    return not target or not candidates or any(target in str(item).strip().lower() for item in candidates if str(item).strip())


def _extract_code(message: dict[str, Any]) -> str | None:
    content = f"{message.get('subject', '')}\n{message.get('text_content', '')}\n{message.get('html_content', '')}".strip()
    if not content:
        return None
    match = re.search(r"background-color:\s*#F3F3F3[^>]*>[\s\S]*?(\d{6})[\s\S]*?</p>", content, re.I)
    if match:
        return match.group(1)
    match = re.search(r"(?:Verification code|code is|mã xác thực|ma xac thuc|mã xác nhận|ma xac nhan|代码为|验证码)[:\s]*(\d{6})", content, re.I)
    if match and match.group(1) != "177010":
        return match.group(1)
    for code in re.findall(r">\s*(\d{6})\s*<|(?<![#&])\b(\d{6})\b", content):
        value = code[0] or code[1]
        if value and value != "177010":
            return value
    return None


def _message_tracking_ref(message: dict[str, Any]) -> str:
    provider = str(message.get("provider") or "").strip()
    mailbox = str(message.get("mailbox") or "").strip()
    message_id = str(message.get("message_id") or "").strip()
    if message_id:
        return f"id:{provider}:{mailbox}:{message_id}"
    received_at = message.get("received_at")
    received_value = received_at.isoformat() if isinstance(received_at, datetime) else str(received_at or "")
    content = "\n".join(str(message.get(key) or "") for key in ("subject", "sender", "text_content", "html_content"))
    digest = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    return f"content:{provider}:{mailbox}:{received_value}:{digest}"


class BaseMailProvider:
    name = "unknown"

    def __init__(self, conf: dict, provider_ref: str = ""):
        self.conf = conf
        self.provider_ref = provider_ref

    def wait_for(self, mailbox: dict[str, Any], on_message: Callable[[dict[str, Any]], ResultT | None]) -> ResultT | None:
        deadline = time.monotonic() + self.conf["wait_timeout"]
        while time.monotonic() < deadline:
            message = self.fetch_latest_message(mailbox)
            if message:
                result = on_message(message)
                if result is not None:
                    return result
            time.sleep(max(0.2, self.conf["wait_interval"]))
        return None

    def wait_for_code(self, mailbox: dict[str, Any]) -> str | None:
        seen_value = mailbox.setdefault("_seen_code_message_refs", [])
        if not isinstance(seen_value, list):
            seen_value = []
            mailbox["_seen_code_message_refs"] = seen_value
        seen_refs = {str(item) for item in seen_value}

        def extract_unseen_code(message: dict[str, Any]) -> str | None:
            ref = _message_tracking_ref(message)
            if ref in seen_refs:
                return None
            code = _extract_code(message)
            if code:
                seen_value.append(ref)
                seen_refs.add(ref)
            return code

        return self.wait_for(mailbox, extract_unseen_code)

    def close(self) -> None:
        pass


class CloudflareTempMailProvider(BaseMailProvider):
    name = "cloudflare_temp_email"

    def __init__(self, entry: dict, conf: dict):
        super().__init__(conf, str(entry.get("provider_ref") or ""))
        self.api_base = str(entry["api_base"]).rstrip("/")
        self.admin_password = str(entry["admin_password"]).strip()
        self.domain = entry.get("domain") or []
        self.session = curl_requests.Session(impersonate="chrome")

    def _request(self, method: str, path: str, headers: dict | None = None, params: dict | None = None, payload: dict | None = None, expected: tuple[int, ...] = (200,)):
        resp = self.session.request(method.upper(), f"{self.api_base}{path}", headers={"Content-Type": "application/json", "User-Agent": self.conf["user_agent"], **(headers or {})}, params=params, json=payload, timeout=self.conf["request_timeout"], verify=False)
        if resp.status_code not in expected:
            raise RuntimeError(f"Yêu cầu CloudflareTempMail thất bại: {method} {path}, HTTP {resp.status_code}, body={resp.text[:300]}")
        return {} if resp.status_code == 204 else resp.json()

    def create_mailbox(self, username: str | None = None) -> dict[str, Any]:
        data = self._request("POST", "/admin/new_address", headers={"x-admin-auth": self.admin_password}, payload={"enablePrefix": True, "name": username or _random_mailbox_name(), "domain": _next_domain(self.domain)})
        address = str(data.get("address") or "").strip()
        token = str(data.get("jwt") or "").strip()
        if not address or not token:
            raise RuntimeError("CloudflareTempMail thiếu address hoặc jwt")
        return {"provider": self.name, "provider_ref": self.provider_ref, "address": address, "token": token}

    def fetch_latest_message(self, mailbox: dict[str, Any]) -> dict[str, Any] | None:
        data = self._request("GET", "/api/mails", headers={"Authorization": f"Bearer {mailbox['token']}"}, params={"limit": 10, "offset": 0})
        raw = list(data.get("results") or []) if isinstance(data, dict) else data if isinstance(data, list) else []
        messages = [item for item in raw if isinstance(item, dict) and _message_matches_email(item, str(mailbox.get("address") or ""))]
        if not messages:
            return None
        item = messages[0]
        text_content, html_content = _extract_content(item)
        sender = item.get("from") or item.get("sender") or ""
        if isinstance(sender, dict):
            sender = sender.get("address") or sender.get("email") or sender.get("name") or ""
        return {"provider": self.name, "mailbox": mailbox["address"], "message_id": str(item.get("id") or item.get("_id") or ""), "subject": str(item.get("subject") or ""), "sender": str(sender), "text_content": text_content, "html_content": html_content, "received_at": _parse_received_at(item.get("createdAt") or item.get("created_at") or item.get("receivedAt") or item.get("date") or item.get("timestamp")), "raw": item}

    def close(self) -> None:
        self.session.close()


class TempMailLolProvider(BaseMailProvider):
    name = "tempmail_lol"

    def __init__(self, entry: dict, conf: dict):
        super().__init__(conf, str(entry.get("provider_ref") or ""))
        self.api_key = str(entry.get("api_key") or "").strip()
        self.domain = [str(item).strip() for item in (entry.get("domain") or []) if str(item).strip()]
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({"User-Agent": conf["user_agent"], "Accept": "application/json", "Content-Type": "application/json"})
        if self.api_key:
            self.session.headers["Authorization"] = f"Bearer {self.api_key}"

    @staticmethod
    def _resolve_domain(domain: str) -> tuple[str, bool]:
        text = str(domain or "").strip().lower()
        if text.startswith("*.") and len(text) > 2:
            return f"{_random_subdomain_label()}.{text[2:]}", True
        return text, False

    def _request(self, method: str, path: str, params: dict | None = None, payload: dict | None = None, expected: tuple[int, ...] = (200,)):
        resp = self.session.request(method.upper(), f"https://api.tempmail.lol/v2{path}", params=params, json=payload, timeout=self.conf["request_timeout"], verify=False)
        if resp.status_code not in expected:
            raise RuntimeError(f"Yêu cầu TempMail.lol thất bại: {method} {path}, HTTP {resp.status_code}, body={resp.text[:300]}")
        data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"TempMail.lol {method} {path} kết quả trả về không phải là đối tượng")
        return data

    def create_mailbox(self, username: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.domain:
            domain, force_random_prefix = self._resolve_domain(random.choice(self.domain))
            payload["domain"] = domain
            if force_random_prefix:
                payload["prefix"] = _random_mailbox_name()
        if username and "prefix" not in payload:
            payload["prefix"] = username
        data = self._request("POST", "/inbox/create", payload=payload, expected=(200, 201))
        address = str(data.get("address") or "").strip()
        token = str(data.get("token") or "").strip()
        if not address or not token:
            raise RuntimeError("TempMail.lol thiếu address hoặc token")
        return {"provider": self.name, "provider_ref": self.provider_ref, "address": address, "token": token}

    def fetch_latest_message(self, mailbox: dict[str, Any]) -> dict[str, Any] | None:
        data = self._request("GET", "/inbox", params={"token": mailbox["token"]})
        items = data.get("emails") or data.get("messages") or []
        messages = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
        if not messages:
            return None
        item = max(messages, key=lambda value: ((_parse_received_at(value.get("created_at") or value.get("createdAt") or value.get("date") or value.get("received_at") or value.get("timestamp")) or datetime.fromtimestamp(0, tz=timezone.utc)).timestamp(), str(value.get("id") or value.get("token") or "")))
        text_content, html_content = _extract_content(item)
        return {"provider": self.name, "mailbox": mailbox["address"], "message_id": str(item.get("id") or item.get("token") or ""), "subject": str(item.get("subject") or ""), "sender": str(item.get("from") or item.get("from_address") or ""), "text_content": text_content, "html_content": html_content, "received_at": _parse_received_at(item.get("created_at") or item.get("createdAt") or item.get("date") or item.get("received_at") or item.get("timestamp")), "raw": item}

    def close(self) -> None:
        self.session.close()


class DuckMailProvider(BaseMailProvider):
    name = "duckmail"

    def __init__(self, entry: dict, conf: dict):
        super().__init__(conf, str(entry.get("provider_ref") or ""))
        self.api_key = str(entry["api_key"]).strip()
        self.default_domain = str(entry.get("default_domain") or "duckmail.sbs").strip() or "duckmail.sbs"
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({"User-Agent": conf["user_agent"], "Accept": "application/json", "Content-Type": "application/json"})

    def _request(self, method: str, path: str, token: str = "", use_api_key: bool = False, params: dict | None = None, payload: dict | None = None, expected: tuple[int, ...] = (200, 201, 204)):
        headers = {"Authorization": f"Bearer {self.api_key if use_api_key else token}"} if use_api_key or token else {}
        resp = self.session.request(method.upper(), f"https://api.duckmail.sbs{path}", headers=headers, params=params, json=payload, timeout=self.conf["request_timeout"], verify=False)
        if resp.status_code not in expected:
            raise RuntimeError(f"Yêu cầu DuckMail thất bại: {method} {path}, HTTP {resp.status_code}, body={resp.text[:300]}")
        return {} if resp.status_code == 204 else resp.json()

    @staticmethod
    def _items(data):
        return data if isinstance(data, list) else data.get("hydra:member") or data.get("member") or data.get("data") or []

    def create_mailbox(self, username: str | None = None) -> dict[str, Any]:
        password = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        address = f"{username or _random_mailbox_name()}@{self.default_domain}"
        payload = {"address": address, "password": password}
        account = self._request("POST", "/accounts", use_api_key=True, payload=payload)
        token_data = self._request("POST", "/token", use_api_key=True, payload=payload)
        return {"provider": self.name, "provider_ref": self.provider_ref, "address": address, "token": str(token_data.get("token") or ""), "password": password, "account_id": str(account.get("id") or "")}

    def fetch_latest_message(self, mailbox: dict[str, Any]) -> dict[str, Any] | None:
        data = self._request("GET", "/messages", token=str(mailbox.get("token") or ""), params={"page": 1})
        items = self._items(data)
        if not items:
            return None
        item = items[0]
        message_id = str(item.get("id") or item.get("@id") or "").replace("/messages/", "")
        if message_id:
            item = self._request("GET", f"/messages/{message_id}", token=str(mailbox.get("token") or ""))
        sender = item.get("from") or ""
        if isinstance(sender, dict):
            sender = sender.get("address") or sender.get("name") or ""
        html_content = item.get("html") or ""
        if isinstance(html_content, list):
            html_content = "".join(str(value) for value in html_content)
        return {"provider": self.name, "mailbox": mailbox["address"], "message_id": message_id, "subject": str(item.get("subject") or ""), "sender": str(sender), "text_content": str(item.get("text") or item.get("text_content") or ""), "html_content": str(html_content), "received_at": _parse_received_at(item.get("createdAt") or item.get("created_at") or item.get("receivedAt") or item.get("date")), "raw": item}

    def close(self) -> None:
        self.session.close()


class GptMailProvider(BaseMailProvider):
    name = "gptmail"

    def __init__(self, entry: dict, conf: dict):
        super().__init__(conf, str(entry.get("provider_ref") or ""))
        self.api_key = str(entry["api_key"]).strip()
        self.default_domain = str(entry.get("default_domain") or "").strip()
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({"User-Agent": conf["user_agent"], "Accept": "application/json", "Content-Type": "application/json", "X-API-Key": self.api_key})

    def _request(self, method: str, path: str, params: dict | None = None, payload: dict | None = None):
        query = dict(params or {})
        resp = self.session.request(method.upper(), f"https://mail.chatgpt.org.uk{path}", params=query, json=payload, timeout=self.conf["request_timeout"], verify=False)
        if resp.status_code != 200:
            raise RuntimeError(f"Yêu cầu GPTMail thất bại: {method} {path}, HTTP {resp.status_code}, body={resp.text[:300]}")
        data = resp.json()
        return data["data"] if isinstance(data, dict) and "data" in data else data

    def create_mailbox(self, username: str | None = None) -> dict[str, Any]:
        payload = {key: value for key, value in {"prefix": username, "domain": self.default_domain}.items() if value}
        data = self._request("POST" if payload else "GET", "/api/generate-email", payload=payload or None)
        return {"provider": self.name, "provider_ref": self.provider_ref, "address": str(data["email"])}

    def fetch_latest_message(self, mailbox: dict[str, Any]) -> dict[str, Any] | None:
        data = self._request("GET", "/api/emails", params={"email": mailbox["address"]})
        emails = data if isinstance(data, list) else data.get("emails") or []
        if not emails:
            return None
        item = max(emails, key=lambda value: (float(value.get("timestamp") or 0), str(value.get("id") or "")))
        if item.get("id"):
            item = self._request("GET", f"/api/email/{item['id']}")
        return {"provider": self.name, "mailbox": mailbox["address"], "message_id": str(item.get("id") or ""), "subject": str(item.get("subject") or ""), "sender": str(item.get("from_address") or ""), "text_content": str(item.get("content") or ""), "html_content": str(item.get("html_content") or ""), "received_at": _parse_received_at(item.get("timestamp") or item.get("created_at")), "raw": item}

    def close(self) -> None:
        self.session.close()


class MoEmailProvider(BaseMailProvider):
    name = "moemail"

    def __init__(self, entry: dict, conf: dict):
        super().__init__(conf, str(entry.get("provider_ref") or ""))
        self.api_base = str(entry["api_base"]).rstrip("/")
        self.api_key = str(entry["api_key"]).strip()
        raw_domains = entry.get("domain") or []
        if isinstance(raw_domains, list):
            self.domain = [str(item).strip() for item in raw_domains if str(item).strip()]
        else:
            self.domain = [str(raw_domains).strip()] if str(raw_domains).strip() else []
        self.expiry_time = int(entry.get("expiry_time") or 0)
        self.session = curl_requests.Session(impersonate="chrome")

    def _request(self, method: str, path: str, params: dict | None = None, payload: dict | None = None, expected: tuple[int, ...] = (200,)):
        resp = self.session.request(method.upper(), f"{self.api_base}{path}", headers={"X-API-Key": self.api_key, "Content-Type": "application/json", "User-Agent": self.conf["user_agent"]}, params=params, json=payload, timeout=self.conf["request_timeout"], verify=False)
        if resp.status_code not in expected:
            raise RuntimeError(f"Yêu cầu MoEmail thất bại: {method} {path}, HTTP {resp.status_code}, body={resp.text[:300]}")
        data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"MoEmail {method} {path} kết quả trả về không phải là đối tượng")
        return data

    def create_mailbox(self, username: str | None = None) -> dict[str, Any]:
        data = self._request("POST", "/api/emails/generate", payload={"name": username or _random_mailbox_name(), "expiryTime": self.expiry_time, "domain": _next_domain(self.domain)}, expected=(200, 201))
        address = str(data.get("email") or "").strip()
        email_id = str(data.get("id") or data.get("email_id") or "").strip()
        if not address or not email_id:
            raise RuntimeError("MoEmail thiếu email hoặc id")
        return {"provider": self.name, "provider_ref": self.provider_ref, "address": address, "email_id": email_id}

    def fetch_latest_message(self, mailbox: dict[str, Any]) -> dict[str, Any] | None:
        email_id = str(mailbox.get("email_id") or "").strip()
        if not email_id:
            raise RuntimeError("MoEmail thiếu email_id")
        data = self._request("GET", f"/api/emails/{email_id}")
        items = data.get("messages") or []
        messages = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
        if not messages:
            return None
        _, item = max(enumerate(messages), key=lambda pair: (((_parse_received_at(pair[1].get("createdAt") or pair[1].get("created_at") or pair[1].get("receivedAt") or pair[1].get("date") or pair[1].get("timestamp")) or datetime.fromtimestamp(0, tz=timezone.utc)).timestamp()), pair[0]))
        message_id = str(item.get("id") or item.get("message_id") or item.get("_id") or "").strip()
        detail = self._request("GET", f"/api/emails/{email_id}/{message_id}") if message_id else {"message": item}
        message = detail.get("message") if isinstance(detail.get("message"), dict) else detail
        text_content, html_content = _extract_content(message)
        sender = message.get("from") or message.get("sender") or ""
        if isinstance(sender, dict):
            sender = sender.get("address") or sender.get("email") or sender.get("name") or ""
        return {"provider": self.name, "mailbox": mailbox["address"], "message_id": message_id, "subject": str(message.get("subject") or item.get("subject") or ""), "sender": str(sender), "text_content": text_content, "html_content": html_content, "received_at": _parse_received_at(message.get("createdAt") or message.get("created_at") or message.get("receivedAt") or message.get("date") or message.get("timestamp") or item.get("createdAt") or item.get("created_at") or item.get("receivedAt") or item.get("date") or item.get("timestamp")), "raw": detail}

    def close(self) -> None:
        self.session.close()


class InbucketMailProvider(BaseMailProvider):
    name = "inbucket"

    def __init__(self, entry: dict, conf: dict):
        super().__init__(conf, str(entry.get("provider_ref") or ""))
        self.api_base = str(entry["api_base"]).rstrip("/")
        raw_domains = entry.get("domain") or []
        if isinstance(raw_domains, list):
            self.domain = [str(item).strip() for item in raw_domains if str(item).strip()]
        else:
            self.domain = [str(raw_domains).strip()] if str(raw_domains).strip() else []
        self.random_subdomain = bool(entry.get("random_subdomain", True))
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": conf["user_agent"],
            "Accept": "application/json",
        })

    def _request(self, method: str, path: str, expected: tuple[int, ...] = (200,)):
        resp = self.session.request(
            method.upper(),
            f"{self.api_base}{path}",
            timeout=self.conf["request_timeout"],
            verify=False,
        )
        if resp.status_code not in expected:
            raise RuntimeError(f"Yêu cầu Inbucket thất bại: {method} {path}, HTTP {resp.status_code}, body={resp.text[:300]}")
        if resp.status_code == 204:
            return {}
        content_type = str(resp.headers.get("content-type") or "").lower()
        if "application/json" in content_type:
            return resp.json()
        return resp.text

    def _resolve_domain(self) -> str:
        if self.domain:
            return _next_domain(self.domain)
        raise RuntimeError("Inbucket cần cấu hình ít nhất một domain")

    def _mailbox_name(self, address: str) -> str:
        local_part, _, _ = str(address or "").partition("@")
        return local_part.strip()

    def create_mailbox(self, username: str | None = None) -> dict[str, Any]:
        local_part = username or _random_mailbox_name()
        base_domain = self._resolve_domain()
        domain = f"{_random_subdomain_label()}.{base_domain}" if self.random_subdomain else base_domain
        address = f"{local_part}@{domain}"
        mailbox_name = self._mailbox_name(address)
        return {
            "provider": self.name,
            "provider_ref": self.provider_ref,
            "address": address,
            "base_domain": base_domain,
            "mailbox_name": mailbox_name,
        }

    def fetch_latest_message(self, mailbox: dict[str, Any]) -> dict[str, Any] | None:
        mailbox_name = str(mailbox.get("mailbox_name") or self._mailbox_name(str(mailbox.get("address") or ""))).strip()
        if not mailbox_name:
            raise RuntimeError("Inbucket thiếu mailbox_name")
        data = self._request("GET", f"/api/v1/mailbox/{mailbox_name}")
        items = [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
        if not items:
            return None
        items.sort(
            key=lambda value: (
                (_parse_received_at(value.get("date")) or datetime.fromtimestamp(0, tz=timezone.utc)).timestamp(),
                str(value.get("id") or ""),
            ),
            reverse=True,
        )
        address = str(mailbox.get("address") or "").strip()
        for item in items:
            message_id = str(item.get("id") or "").strip()
            if not message_id:
                continue
            detail = self._request("GET", f"/api/v1/mailbox/{mailbox_name}/{message_id}")
            if not isinstance(detail, dict):
                continue
            header = detail.get("header") if isinstance(detail.get("header"), dict) else {}
            body = detail.get("body") if isinstance(detail.get("body"), dict) else {}
            normalized = {
                "provider": self.name,
                "mailbox": mailbox_name,
                "message_id": message_id,
                "subject": str(detail.get("subject") or item.get("subject") or ""),
                "sender": str(detail.get("from") or item.get("from") or ""),
                "text_content": str(body.get("text") or ""),
                "html_content": str(body.get("html") or ""),
                "received_at": _parse_received_at(detail.get("date") or item.get("date")),
                "to": header.get("To") if isinstance(header, dict) else None,
                "raw": detail,
            }
            if _message_matches_email(normalized, address):
                return normalized
        return None

    def close(self) -> None:
        self.session.close()


class YydsMailProvider(BaseMailProvider):
    name = "yyds_mail"

    def __init__(self, entry: dict, conf: dict):
        super().__init__(conf, str(entry.get("provider_ref") or ""))
        self.api_base = str(entry.get("api_base") or "https://maliapi.215.im/v1").rstrip("/")
        self.api_key = str(entry["api_key"]).strip()
        self.domain = [str(item).strip() for item in (entry.get("domain") or []) if str(item).strip()]
        self.subdomain = str(entry.get("subdomain") or "").strip()
        self.wildcard = bool(entry.get("wildcard"))
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({"User-Agent": conf["user_agent"], "Accept": "application/json", "Content-Type": "application/json"})

    def _request(self, method: str, path: str, token: str = "", params: dict | None = None, payload: dict | None = None, expected: tuple[int, ...] = (200, 201, 204)):
        headers = {"Authorization": f"Bearer {token}"} if token else {"X-API-Key": self.api_key}
        resp = self.session.request(method.upper(), f"{self.api_base}{path}", headers=headers, params=params, json=payload, timeout=self.conf["request_timeout"], verify=False)
        if resp.status_code not in expected:
            raise RuntimeError(f"Yêu cầu YYDSMail thất bại: {method} {path}, HTTP {resp.status_code}, body={resp.text[:300]}")
        if resp.status_code == 204:
            return {}
        data = resp.json()
        if isinstance(data, dict) and data.get("success") is False:
            raise RuntimeError(f"Yêu cầu YYDSMail thất bại: {data.get('errorCode') or data.get('error')}")
        return data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), (dict, list)) else data

    @staticmethod
    def _items(data):
        return data if isinstance(data, list) else data.get("items") or data.get("messages") or data.get("data") or []

    def create_mailbox(self, username: str | None = None) -> dict[str, Any]:
        payload = {"localPart": username or _random_mailbox_name()}
        if self.domain:
            payload["domain"] = _next_domain(self.domain)
        if self.subdomain:
            payload["subdomain"] = self.subdomain
        data = self._request("POST", "/accounts/wildcard" if self.wildcard else "/accounts", payload=payload)
        address = str(data.get("address") or data.get("email") or "").strip()
        token = str(data.get("token") or data.get("temp_token") or data.get("tempToken") or data.get("access_token") or "").strip()
        if not address or not token:
            raise RuntimeError("YYDSMail thiếu address hoặc token")
        return {"provider": self.name, "provider_ref": self.provider_ref, "address": address, "token": token, "account_id": str(data.get("id") or "")}

    def fetch_latest_message(self, mailbox: dict[str, Any]) -> dict[str, Any] | None:
        data = self._request("GET", "/messages", token=str(mailbox.get("token") or ""), params={"address": mailbox["address"]})
        messages = [item for item in self._items(data) if isinstance(item, dict)]
        if not messages:
            return None
        item = max(messages, key=lambda value: ((_parse_received_at(value.get("createdAt") or value.get("created_at") or value.get("receivedAt") or value.get("date") or value.get("timestamp")) or datetime.fromtimestamp(0, tz=timezone.utc)).timestamp(), str(value.get("id") or "")))
        message_id = str(item.get("id") or item.get("message_id") or "").strip()
        if message_id:
            item = self._request("GET", f"/messages/{message_id}", token=str(mailbox.get("token") or ""), params={"address": mailbox["address"]})
        text_content, html_content = _extract_content(item)
        sender = item.get("from") or item.get("sender") or ""
        if isinstance(sender, dict):
            sender = sender.get("address") or sender.get("email") or sender.get("name") or ""
        return {"provider": self.name, "mailbox": mailbox["address"], "message_id": message_id, "subject": str(item.get("subject") or ""), "sender": str(sender), "text_content": text_content, "html_content": html_content, "received_at": _parse_received_at(item.get("createdAt") or item.get("created_at") or item.get("receivedAt") or item.get("date") or item.get("timestamp")), "raw": item}

    def close(self) -> None:
        self.session.close()


class EtempMailProvider(BaseMailProvider):
    """Mail provider dùng Playwright headless browser để vượt Cloudflare Turnstile
    Invisible trên etempmail.com và lấy địa chỉ email tạm.

    Browser chỉ được khởi động một lần khi ``create_mailbox()``; sau đó tất cả
    các lần poll inbox đều dùng ``requests`` HTTP thông thường với session cookies
    đã capture — không tốn thêm overhead browser.
    """

    name = "etempmail"

    # ── endpoints ──────────────────────────────────────────────────────────────
    _BASE_URL  = "https://etempmail.com"
    _EMAIL_URL = "https://etempmail.com/getEmailAddress"
    _INBOX_URL = "https://etempmail.com/getInbox"
    _DETAIL_URL = "https://etempmail.com/email"
    _MORE_URL  = "https://etempmail.com/moreMinutes"
    _DELETE_URL = "https://etempmail.com/deleteEmailAddress"

    # Địa chỉ troll mà backend etempmail trả về khi không có cf_token hợp lệ
    _TROLL_MARKER = "ip_logged"
    _TROLL_DOMAIN = "get-a-real-job.com"

    _DEFAULT_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def __init__(self, entry: dict, conf: dict) -> None:
        super().__init__(conf, str(entry.get("provider_ref") or ""))
        self.headless: bool = bool(entry.get("headless", True))
        # proxy cho Playwright browser (tách biệt proxy của OpenAI)
        # dạng "socks5://user:pass@host:port" hoặc "http://host:port"
        self.browser_proxy: str = str(entry.get("browser_proxy") or entry.get("proxy") or "").strip()
        # proxy cho requests (polling inbox)
        self.req_proxy: str = str(entry.get("req_proxy") or entry.get("proxy") or "").strip()
        # số lần thử lại khi nhận địa chỉ troll
        self.max_browser_retries: int = int(entry.get("max_browser_retries") or 3)
        # thời gian tối đa (giây) chờ Turnstile giải và nhận địa chỉ email
        self.browser_timeout: float = float(entry.get("browser_timeout") or 45)
        # mailbox dict cuối cùng tạo được, dùng cho close() để dọn dẹp
        self._last_mailbox: dict | None = None

    # ── public API ──────────────────────────────────────────────────────────────

    def create_mailbox(self, username: str | None = None) -> dict[str, Any]:
        """Mở Chrome headless, để Turnstile Invisible tự giải, intercept
        phản hồi /getEmailAddress và trả về mailbox dict.
        """
        last_error = ""
        for attempt in range(1, self.max_browser_retries + 1):
            try:
                mailbox = self._browser_get_mailbox()
                self._last_mailbox = mailbox
                return mailbox
            except RuntimeError as exc:
                last_error = str(exc)
                if attempt < self.max_browser_retries:
                    time.sleep(2)
        raise RuntimeError(f"EtempMail: Không thể tạo hộp thư sau {self.max_browser_retries} lần thử. Lỗi cuối: {last_error}")

    def fetch_latest_message(self, mailbox: dict[str, Any]) -> dict[str, Any] | None:
        """Poll inbox bằng requests HTTP (không cần browser), trả về thư
        mới nhất từ OpenAI hoặc None nếu chưa có thư.
        """
        session = self._make_req_session(mailbox)
        try:
            resp = session.post(
                self._INBOX_URL,
                headers=self._req_headers(referer=self._BASE_URL + "/"),
                timeout=self.conf["request_timeout"],
            )
            if resp.status_code != 200:
                return None
            try:
                items = resp.json()
            except Exception:
                return None
            if not isinstance(items, list) or not items:
                return None
            # Lấy thư mới nhất (etempmail trả về danh sách từ mới đến cũ)
            item = items[0]
            if not isinstance(item, dict):
                return None
            message_id = str(item.get("id") or "").strip()
            # Đọc nội dung chi tiết thư qua trang HTML /email?id=N
            text_content, html_content = self._fetch_message_body(session, message_id)
            sender_raw = str(item.get("from") or "")
            # etempmail trả về dạng "Name <addr@domain>" hoặc chỉ địa chỉ
            sender_match = re.search(r"<([^>]+)>", sender_raw)
            sender = sender_match.group(1) if sender_match else sender_raw
            return {
                "provider": self.name,
                "mailbox": str(mailbox.get("address") or ""),
                "message_id": message_id,
                "subject": str(item.get("subject") or ""),
                "sender": sender,
                "text_content": text_content,
                "html_content": html_content,
                "received_at": _parse_received_at(item.get("date")),
                "raw": item,
            }
        finally:
            session.close()

    def extend_mailbox(self, mailbox: dict[str, Any]) -> None:
        """Gia hạn hộp thư khi cần thêm thời gian (gọi thủ công nếu muốn)."""
        session = self._make_req_session(mailbox)
        try:
            session.post(
                self._MORE_URL,
                headers=self._req_headers(referer=self._BASE_URL + "/"),
                timeout=self.conf["request_timeout"],
            )
        finally:
            session.close()

    def close(self) -> None:
        """Dọn dẹp: xoá hộp thư trên etempmail sau khi dùng xong."""
        if self._last_mailbox:
            self._delete_mailbox(self._last_mailbox)
            self._last_mailbox = None

    # ── internal: Playwright browser ────────────────────────────────────────────

    def _browser_get_mailbox(self) -> dict[str, Any]:
        """Dùng Playwright lấy địa chỉ email từ etempmail.com.

        Chiến lược:
        1. Nếu không có X Display và ``xvfb-run`` khả dụng → chạy Chrome
           **headed** qua virtual framebuffer (Turnstile pass tốt nhất).
        2. Fallback: headless Firefox (ít bị detect hơn Chromium headless).
        3. Fallback cuối: headless Chromium với stealth patches.

        Sau khi Turnstile giải xong, đọc email trực tiếp từ DOM element
        ``#tempEmailAddress`` — không cần intercept network.
        """
        import os
        import shutil

        try:
            from playwright.sync_api import sync_playwright, Browser, BrowserContext
        except ImportError as exc:
            raise RuntimeError(
                "EtempMail yêu cầu playwright: chạy 'uv add playwright' và "
                "'uv run playwright install chromium firefox --with-deps'"
            ) from exc

        # Quyết định có dùng virtual display không
        has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        has_xvfb = bool(shutil.which("xvfb-run"))
        # Dùng headed + xvfb khi: không có màn hình thật, xvfb có, và không bị tắt headless
        use_xvfb_headed = not has_display and has_xvfb and self.headless

        if use_xvfb_headed:
            # Khởi động Xvfb virtual display rồi set DISPLAY
            import subprocess
            xvfb_display = ":99"
            xvfb_proc = subprocess.Popen(
                ["Xvfb", xvfb_display, "-screen", "0", "1280x800x24"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            time.sleep(1)  # Chờ Xvfb khởi động
            os.environ["DISPLAY"] = xvfb_display
        else:
            xvfb_proc = None

        try:
            return self._run_browser_engines(use_xvfb_headed)
        finally:
            # Dọn dẹp Xvfb
            if xvfb_proc is not None:
                try:
                    xvfb_proc.terminate()
                    xvfb_proc.wait(timeout=3)
                except Exception:
                    pass
                try:
                    del os.environ["DISPLAY"]
                except KeyError:
                    pass

    def _run_browser_engines(self, use_headed: bool) -> dict[str, Any]:
        """Thử từng browser engine cho đến khi lấy được email hợp lệ."""
        from playwright.sync_api import sync_playwright, Browser, BrowserContext

        with sync_playwright() as p:
            browser_engines = [
                ("firefox", p.firefox),
                ("chromium", p.chromium),
            ]
            last_err = ""
            for engine_name, engine in browser_engines:
                browser: Browser | None = None
                try:
                    # Chromium headed (qua Xvfb) bypass Turnstile tốt nhất
                    # Firefox headless: ít bị detect hơn Chromium headless
                    # Chromium headless: fallback cuối
                    run_headless = not use_headed
                    launch_kwargs: dict[str, Any] = {"headless": run_headless}

                    if engine_name == "chromium":
                        launch_kwargs["args"] = [
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-blink-features=AutomationControlled",
                            "--disable-web-security",
                            "--lang=en-US",
                        ]
                        if run_headless:
                            # Headless chromium: thêm SwiftShader để tránh GL errors
                            launch_kwargs["args"].append("--enable-unsafe-swiftshader")

                    if self.browser_proxy:
                        from urllib.parse import urlparse
                        _u = urlparse(self.browser_proxy)
                        if _u.hostname:
                            _server = f"{_u.scheme or 'http'}://{_u.hostname}"
                            if _u.port:
                                _server += f":{_u.port}"
                            _proxy_dict: dict[str, str] = {"server": _server}
                            if _u.username:
                                _proxy_dict["username"] = _u.username
                            if _u.password:
                                _proxy_dict["password"] = _u.password
                            launch_kwargs["proxy"] = _proxy_dict
                        else:
                            launch_kwargs["proxy"] = {"server": self.browser_proxy}

                    browser = engine.launch(**launch_kwargs)
                    ctx_kwargs: dict[str, Any] = {
                        "locale": "en-US",
                        "timezone_id": "America/New_York",
                        "user_agent": self._DEFAULT_UA,
                        "viewport": {"width": 1280, "height": 800},
                        "java_script_enabled": True,
                    }
                    context: BrowserContext = browser.new_context(**ctx_kwargs)

                    # Stealth script — ẩn dấu hiệu automation
                    context.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', { get: () => false });
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => { const p = []; p.length = 3; return p; }
                        });
                        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                        window.chrome = { runtime: {} };
                    """)

                    page = context.new_page()

                    # "domcontentloaded" không bị block bởi Cloudflare background polling
                    page.goto(
                        self._BASE_URL,
                        wait_until="domcontentloaded",
                        timeout=int(self.browser_timeout * 1000),
                    )

                    # Chờ Turnstile giải xong → JS điền email thật vào #tempEmailAddress
                    # Nhận biết email thật bằng ký tự "@" (phân biệt với "Please wait...")
                    page.wait_for_function(
                        """() => {
                            const el = document.getElementById('tempEmailAddress');
                            return el && el.value && el.value.includes('@');
                        }""",
                        timeout=int(self.browser_timeout * 1000),
                    )

                    # Đọc giá trị từ DOM
                    address = (page.input_value("#tempEmailAddress") or "").strip()
                    recover_key = (page.text_content("#recoverKey") or "").strip()

                    # Phát hiện địa chỉ troll (Turnstile fail nhưng server vẫn trả về giá trị)
                    if not address or self._TROLL_MARKER in address or self._TROLL_DOMAIN in address:
                        raise RuntimeError(
                            f"EtempMail [{engine_name}]: Địa chỉ không hợp lệ: '{address}'"
                        )

                    # Capture cookies
                    raw_cookies = context.cookies()
                    cookies: dict[str, str] = {
                        c["name"]: c["value"]
                        for c in raw_cookies
                        if "etempmail" in str(c.get("domain") or "")
                    }

                    browser.close()
                    browser = None
                    return {
                        "provider": self.name,
                        "provider_ref": self.provider_ref,
                        "address": address,
                        "recover_key": recover_key,
                        "creation_time": "",
                        "cookies": cookies,
                        "_engine": engine_name,
                        "_headed": use_headed,
                    }

                except Exception as exc:
                    if browser:
                        try:
                            browser.close()
                        except Exception:
                            pass
                        browser = None
                    last_err = str(exc)
                    _skip_keywords = (
                        "timeout", "timeouter", "không hợp lệ",
                        "executable", "browser", "crashed", "disconnected",
                    )
                    if any(kw in last_err.lower() for kw in _skip_keywords):
                        continue
                    raise

            raise RuntimeError(
                f"EtempMail: Không thể vượt Cloudflare Turnstile bằng cả Firefox lẫn Chromium. "
                f"Lỗi cuối: {last_err}. "
                f"Giải pháp: dùng residential proxy hoặc captcha solver service."
            )

    # ── internal: requests HTTP helpers ─────────────────────────────────────────

    def _make_req_session(self, mailbox: dict[str, Any]) -> requests.Session:
        """Tạo requests.Session với cookies và proxy đã cấu hình."""
        session = requests.Session()
        session.trust_env = False
        cookies: dict = mailbox.get("cookies") or {}
        for name, value in cookies.items():
            session.cookies.set(name, value, domain="etempmail.com")
        if self.req_proxy:
            session.proxies.update({"http": self.req_proxy, "https": self.req_proxy})
        session.verify = False
        return session

    def _req_headers(self, referer: str = "") -> dict[str, str]:
        headers: dict[str, str] = {
            "User-Agent": self.conf.get("user_agent") or self._DEFAULT_UA,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": self._BASE_URL,
        }
        if referer:
            headers["Referer"] = referer
        return headers

    def _fetch_message_body(self, session: requests.Session, message_id: str) -> tuple[str, str]:
        """Lấy nội dung HTML của thư qua trang /email?id=N, trích xuất text/html."""
        if not message_id:
            return "", ""
        try:
            resp = session.get(
                self._DETAIL_URL,
                params={"id": message_id},
                headers={
                    "User-Agent": self.conf.get("user_agent") or self._DEFAULT_UA,
                    "Accept": "text/html,application/xhtml+xml",
                    "Referer": self._BASE_URL + "/",
                },
                timeout=self.conf["request_timeout"],
            )
            if resp.status_code != 200:
                return "", ""
            html = resp.text or ""
            # Cố gắng trích xuất phần body thư từ trang HTML của etempmail
            # etempmail bọc nội dung thư trong <div class="card-body">
            body_match = re.search(
                r'<div[^>]+class=["\'][^"\']*card-body[^"\']*["\'][^>]*>([\s\S]*?)</div>',
                html,
                re.I,
            )
            html_content = body_match.group(1).strip() if body_match else html
            text_content = re.sub(r"<[^>]+>", " ", html_content)
            text_content = re.sub(r"\s+", " ", text_content).strip()
            return text_content, html_content
        except Exception:
            return "", ""

    def _delete_mailbox(self, mailbox: dict[str, Any]) -> None:
        """Xoá hộp thư trên etempmail sau khi không còn cần dùng nữa."""
        session = self._make_req_session(mailbox)
        try:
            session.post(
                self._DELETE_URL,
                headers=self._req_headers(referer=self._BASE_URL + "/"),
                timeout=max(5.0, self.conf["request_timeout"]),
            )
        except Exception:
            pass
        finally:
            session.close()


class BrowserRelayMailProvider(BaseMailProvider):
    name = "browser_relay"

    def __init__(self, entry: dict, conf: dict):
        super().__init__(conf, str(entry.get("provider_ref") or ""))
        self._last_mailbox: dict[str, Any] | None = None

    def create_mailbox(self, username: str | None = None) -> dict[str, Any]:
        timeout = float(self.conf.get("wait_timeout") or 60)
        mailbox = browser_relay.server_wait_for_mailbox(timeout=timeout)
        mailbox["provider_ref"] = self.provider_ref
        self._last_mailbox = mailbox
        return mailbox

    def fetch_latest_message(self, mailbox: dict[str, Any]) -> dict[str, Any] | None:
        return None

    def wait_for_code(self, mailbox: dict[str, Any]) -> str | None:
        timeout = float(self.conf.get("wait_timeout") or 60)
        return browser_relay.server_wait_for_otp(mailbox, timeout=timeout)

    def close(self) -> None:
        browser_relay.server_mailbox_done(self._last_mailbox, success=True)


def _entries(mail_config: dict) -> list[dict]:
    return [{**item, "provider_ref": f"{item['type']}#{index + 1}"} for index, item in enumerate(mail_config["providers"])]


def _enabled_entries(mail_config: dict) -> list[dict]:
    items = [item for item in _entries(mail_config) if item.get("enable")]
    if not items:
        raise RuntimeError("mail.providers không có nhà cung cấp nào được kích hoạt")
    return items


def _next_entry(mail_config: dict) -> dict:
    global provider_index
    items = _enabled_entries(mail_config)
    if len(items) == 1:
        return dict(items[0])
    with provider_lock:
        value = dict(items[provider_index % len(items)])
        provider_index = (provider_index + 1) % len(items)
        return value


def _create_provider(mail_config: dict, provider: str = "", provider_ref: str = "") -> BaseMailProvider:
    entry = next((dict(item) for item in _entries(mail_config) if provider_ref and item["provider_ref"] == provider_ref), None)
    entry = entry or next((dict(item) for item in _enabled_entries(mail_config) if provider and item["type"] == provider), None) or _next_entry(mail_config)
    conf = _config(mail_config)
    if entry["type"] == "cloudflare_temp_email":
        return CloudflareTempMailProvider(entry, conf)
    if entry["type"] == "tempmail_lol":
        return TempMailLolProvider(entry, conf)
    if entry["type"] == "duckmail":
        return DuckMailProvider(entry, conf)
    if entry["type"] == "gptmail":
        return GptMailProvider(entry, conf)
    if entry["type"] == "moemail":
        return MoEmailProvider(entry, conf)
    if entry["type"] == "inbucket":
        return InbucketMailProvider(entry, conf)
    if entry["type"] == "yyds_mail":
        return YydsMailProvider(entry, conf)
    if entry["type"] == "etempmail":
        return EtempMailProvider(entry, conf)
    if entry["type"] == "browser_relay":
        return BrowserRelayMailProvider(entry, conf)
    raise RuntimeError(f"Không hỗ trợ mail.provider: {entry['type']}")


def create_mailbox(mail_config: dict, username: str | None = None) -> dict:
    provider = _create_provider(mail_config)
    # EtempMailProvider và BrowserRelayMailProvider: KHÔNG gọi close() ngay sau khi tạo hộp thư
    # vì close() sẽ kích hoạt đổi/xóa mail — hộp thư cần tồn tại để nhận OTP.
    if isinstance(provider, (EtempMailProvider, BrowserRelayMailProvider)):
        mailbox = provider.create_mailbox(username)
        mailbox["_provider_instance"] = provider
        return mailbox
    try:
        return provider.create_mailbox(username)
    finally:
        provider.close()


def wait_for_code(mail_config: dict, mailbox: dict) -> str | None:
    bound_provider: BaseMailProvider | None = mailbox.pop("_provider_instance", None)
    provider = bound_provider or _create_provider(mail_config, str(mailbox.get("provider") or ""), str(mailbox.get("provider_ref") or ""))
    try:
        return provider.wait_for_code(mailbox)
    finally:
        provider.close()
