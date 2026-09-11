from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Header, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

import logging

from api.support import require_admin
from services.config import config as app_config
from services.register.browser_relay import browser_relay
from services.register_service import register_service

logger = logging.getLogger(__name__)


class RegisterConfigRequest(BaseModel):
    mail: dict | None = None
    proxy: str | None = None
    total: int | None = None
    threads: int | None = None
    mode: str | None = None
    target_quota: int | None = None
    target_available: int | None = None
    check_interval: int | None = None


class RelayHeartbeatRequest(BaseModel):
    email: str = ""
    inbox_text: str = ""
    otp: str = ""
    key: str = ""


class RelayOtpRequest(BaseModel):
    email: str = ""
    code: str
    key: str = ""


class RelayAckNewEmailRequest(BaseModel):
    email: str = ""
    key: str = ""


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/register")
    async def get_register_config(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"register": register_service.get()}

    @router.post("/api/register")
    async def update_register_config(body: RegisterConfigRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"register": register_service.update(body.model_dump(exclude_none=True))}

    @router.post("/api/register/start")
    async def start_register(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"register": register_service.start()}

    @router.post("/api/register/stop")
    async def stop_register(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"register": register_service.stop()}

    @router.post("/api/register/reset")
    async def reset_register(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"register": register_service.reset()}

    @router.get("/api/register/events")
    async def register_events(token: str = ""):
        require_admin(f"Bearer {token}")

        async def stream():
            last = ""
            while True:
                payload = json.dumps(register_service.get(), ensure_ascii=False)
                if payload != last:
                    last = payload
                    yield f"data: {payload}\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(stream(), media_type="text/event-stream")

    # ── Browser Relay endpoints ──────────────────────────────────────────────

    @router.get("/api/register/relay/status")
    async def get_relay_status():
        return {"relay": browser_relay.get_status()}

    @router.post("/api/register/relay/heartbeat")
    async def relay_heartbeat(body: RelayHeartbeatRequest):
        logger.info(f"[Relay] Heartbeat nhận từ browser: email='{body.email}', otp='{body.otp}', inbox_len={len(body.inbox_text)}")
        return browser_relay.browser_heartbeat(email=body.email, inbox_text=body.inbox_text, otp=body.otp)

    @router.post("/api/register/relay/otp")
    async def relay_otp(body: RelayOtpRequest):
        return browser_relay.browser_submit_otp(email=body.email, code=body.code)

    @router.post("/api/register/relay/ack_new_email")
    async def relay_ack_new_email(body: RelayAckNewEmailRequest | None = None):
        new_email = body.email if body else ""
        return browser_relay.browser_ack_new_email(new_email=new_email)

    @router.post("/api/register/relay/reset")
    async def relay_reset(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        browser_relay.reset()
        return {"status": "ok", "message": "Đã reset Browser Relay"}

    @router.get("/api/register/relay/script")
    async def get_relay_script(request: Request):
        server_url = str(app_config.base_url or "").rstrip("/")
        if not server_url:
            scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
            host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
            server_url = f"{scheme}://{host}".rstrip("/")

        js_code = f"""// ==UserScript==
// @name         ChatGPT2API EtempMail Relay Worker
// @namespace    https://github.com/chatgpt2api
// @version      1.1
// @description  Relay EtempMail to ChatGPT2API Server
// @match        https://etempmail.com/*
// @grant        none
// ==/UserScript==

(function() {{
    'use strict';
    const SERVER_URL = "{server_url}";
    let currentEmail = "";
    let isRequestingNewEmail = false;
    let lastFoundOtp = "";
    let isPollingOtp = false;

    if (document.getElementById("chatgpt-relay-badge")) return;

    // Trích xuất mã OTP 6 chữ số từ text / card-body / iframe src
    function extractOtpFromHtml(rawContent) {{
        if (!rawContent) return null;
        let textToScan = rawContent;
        try {{
            // 1. Nếu có iframe data:text/html trong HTML
            const parser = new DOMParser();
            const doc = parser.parseFromString(rawContent, "text/html");
            const iframe = doc.querySelector("iframe");
            if (iframe && iframe.getAttribute("src")) {{
                const src = iframe.getAttribute("src");
                try {{
                    textToScan = decodeURIComponent(src);
                }} catch(e) {{
                    textToScan = unescape(src);
                }}
            }} else {{
                // Thử giải mã URI component nếu toàn bộ chuỗi bị encode
                try {{
                    textToScan = decodeURIComponent(rawContent);
                }} catch(e) {{}}
            }}
        }} catch(e) {{
            textToScan = rawContent;
        }}

        // Tìm từ khóa thông dụng của OpenAI verification code
        let m = textToScan.match(/(?:verification\\s*code|code\\s*is|mã\\s*xác\\s*thực|mã\\s*xác\\s*nhận|security\\s*code|của\\s*bạn\\s*là|your\\s*code)[:\\s]*(\\d{{6}})/i);
        if (m && m[1] && m[1] !== "177010") return m[1];

        // Lấy tất cả số có 6 chữ số
        const all = textToScan.match(/\\b\\d{{6}}\\b/g);
        if (all) {{
            for (const num of all) {{
                if (num !== "177010") return num;
            }}
        }}
        return null;
    }}

    // Gửi OTP lên server
    async function submitOtpToServer(code) {{
        if (!code || code.length !== 6 || !/^\\d{{6}}$/.test(code)) return;
        lastFoundOtp = code;
        updateBadge("🔥 ChatGPT Relay", null, `ĐÃ BẮT ĐƯỢC OTP: ${{code}}! Đang gửi...`);
        console.log(`%c[Relay] 🔥 Gửi mã OTP ${{code}} lên Server!`, "color:#fbbf24;font-size:16px;font-weight:bold;");

        try {{
            await fetch(`${{SERVER_URL}}/api/register/relay/otp`, {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ email: currentEmail, code: code }})
            }});
            updateBadge("🎉 ChatGPT Relay", null, `✅ ĐÃ GỬI OTP: ${{code}}`);
        }} catch(e) {{
            console.error("[Relay] Lỗi gửi OTP:", e);
        }}
    }}

    // Tự động kiểm tra chi tiết các thư mới để trích xuất OTP
    async function checkInboxForOtp() {{
        if (isPollingOtp) return;
        isPollingOtp = true;
        try {{
            // 1. Kiểm tra trên trang hiện tại nếu đang mở /email?id=...
            if (location.pathname.includes("/email")) {{
                const card = document.querySelector(".card-body") || document.body;
                const pageHtml = card ? card.innerHTML : document.documentElement.innerHTML;
                const found = extractOtpFromHtml(pageHtml);
                if (found && found !== lastFoundOtp) {{
                    await submitOtpToServer(found);
                    isPollingOtp = false;
                    return;
                }}
            }}

            // 2. Fetch /email?id=1,2,3 để lấy nội dung mail
            for (let id = 1; id <= 3; id++) {{
                try {{
                    const resp = await fetch(`/email?id=${{id}}`);
                    if (resp.status === 200) {{
                        const html = await resp.text();
                        // Trích xuất OTP trực tiếp từ response HTML (bao gồm iframe)
                        const found = extractOtpFromHtml(html);
                        if (found && found !== lastFoundOtp) {{
                            console.log(`%c[Relay] 👉 Bắt được OTP từ email id=${{id}}: ${{found}}`, "color:#4ade80;font-weight:bold;");
                            await submitOtpToServer(found);
                            break;
                        }}
                    }}
                }} catch(e) {{
                    console.error("[Relay] Lỗi quét email id=" + id, e);
                }}
            }}
        }} finally {{
            isPollingOtp = false;
        }}
    }}

    // Tạo widget nổi góc phải
    const badge = document.createElement("div");
    badge.id = "chatgpt-relay-badge";
    badge.style.cssText = "position:fixed;bottom:20px;right:20px;background:#18181b;color:#f4f4f5;padding:14px 18px;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,0.5);z-index:999999;font-family:system-ui,-apple-system,sans-serif;font-size:13px;max-width:350px;line-height:1.5;border:1px solid #3f3f46;";
    badge.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
            <span style="font-weight:700;color:#4ade80;font-size:14px;" id="relay-title">🟢 ChatGPT Relay</span>
            <span style="font-size:11px;background:#27272a;padding:2px 6px;border-radius:6px;color:#a1a1aa;" id="relay-ping">Đang kết nối...</span>
        </div>
        <div id="relay-email" style="font-size:12px;color:#e4e4e7;margin-bottom:3px;word-break:break-all;">📧 Email: <span style="color:#fbbf24;">(Đang lấy...)</span></div>
        <div id="relay-status" style="font-size:12px;color:#a1a1aa;margin-bottom:6px;">⚡ Trạng thái: Khởi động</div>
        
        <!-- Khung nhập OTP thủ công phòng hờ -->
        <div style="display:flex;gap:6px;margin-bottom:8px;padding-top:6px;border-top:1px solid #27272a;">
            <input id="relay-manual-otp" type="text" maxlength="6" placeholder="Nhập OTP 6 số..." style="flex:1;background:#27272a;color:#fff;border:1px solid #52525b;border-radius:6px;padding:4px 8px;font-size:12px;outline:none;" />
            <button id="relay-send-otp-btn" style="background:#10b981;color:#fff;border:none;border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer;font-weight:600;">Gửi OTP</button>
        </div>

        <div style="display:flex;align-items:center;justify-content:space-between;font-size:11px;color:#818cf8;border-top:1px solid #27272a;padding-top:4px;">
            <span id="relay-counter">🎉 Đã tạo: 0 tài khoản</span>
            <button id="relay-manual-btn" style="background:#3f3f46;color:#fff;border:none;padding:2px 8px;border-radius:4px;cursor:pointer;font-size:11px;">Đổi mail mới</button>
        </div>
    `;
    document.body.appendChild(badge);

    function updateBadge(title, email, status, counter) {{
        if (title) document.getElementById("relay-title").innerHTML = title;
        if (email) document.getElementById("relay-email").innerHTML = '📧 Email: <span style="color:#38bdf8;font-weight:600;">' + email + '</span>';
        if (status) document.getElementById("relay-status").textContent = "⚡ " + status;
        if (counter !== undefined) document.getElementById("relay-counter").textContent = "🎉 Đã tạo: " + counter + " tài khoản";
    }}

    // Nút gửi OTP tay
    document.getElementById("relay-send-otp-btn").onclick = () => {{
        const inp = document.getElementById("relay-manual-otp");
        if (inp && inp.value.trim()) {{
            submitOtpToServer(inp.value.trim());
            inp.value = "";
        }}
    }};
    document.getElementById("relay-manual-otp").onkeydown = (e) => {{
        if (e.key === "Enter") {{
            document.getElementById("relay-send-otp-btn").click();
        }}
    }};

    // Lấy email từ DOM bằng nhiều selector dự phòng
    function getEmailFromDOM() {{
        const selectors = [
            "#tempEmailAddress",
            "input#tempEmailAddress",
            "#email",
            "input#email",
            ".email-address",
            "input[name='email']",
            "input[readonly]"
        ];
        for (const s of selectors) {{
            const el = document.querySelector(s);
            if (el) {{
                const val = (el.value || el.innerText || el.textContent || "").trim();
                if (val && val.includes("@") && !val.includes("get-a-real-job") && !val.includes("...") && !val.toLowerCase().includes("please wait")) {{
                    return val;
                }}
            }}
        }}
        // Tìm bất kỳ text nào có định dạng email trong các phần tử input hoặc span nổi bật
        const inputs = Array.from(document.querySelectorAll("input, span, div.font-monospace, .card-body"));
        for (const el of inputs) {{
            const txt = (el.value || el.innerText || "").trim();
            const m = txt.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}/);
            if (m && !m[0].includes("example") && !m[0].includes("openai") && !m[0].includes("etempmail")) {{
                return m[0];
            }}
        }}
        return "";
    }}

    // Nút đổi email
    async function triggerNewEmail() {{
        if (isRequestingNewEmail) return;
        isRequestingNewEmail = true;
        lastFoundOtp = "";
        currentEmail = "";
        updateBadge("🟡 ChatGPT Relay", "(Đang tạo mới...)", "Đang tạo email mới...", undefined);
        console.log("%c[Relay] 🔄 Kích hoạt đổi email...", "color:#38bdf8;font-weight:bold;");

        try {{
            const btn = document.getElementById("deleteEmailAddress") ||
                        document.querySelector("#delete") ||
                        document.querySelector(".delete-mail") ||
                        document.querySelector("button#del");
            if (btn) {{
                btn.click();
            }} else {{
                const deleteUrl = (typeof $ !== "undefined" && $("#strings").length) ? $("#strings").data("delete-url") : "/deleteEmailAddress";
                await fetch(deleteUrl, {{ method: "POST" }});
            }}
        }} catch (e) {{
            console.error("[Relay] Lỗi đổi mail:", e);
        }}

        // Thông báo cho backend biết đã click đổi mail
        try {{
            await fetch(`${{SERVER_URL}}/api/register/relay/ack_new_email`, {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ email: "" }})
            }});
        }} catch(e) {{}}

        setTimeout(() => {{ isRequestingNewEmail = false; }}, 3000);
    }}

    document.getElementById("relay-manual-btn").onclick = triggerNewEmail;

    // Vòng lặp chính gửi heartbeat & quét OTP (chạy mỗi 1.2s)
    setInterval(async () => {{
        const domEmail = getEmailFromDOM();
        if (domEmail && domEmail !== currentEmail) {{
            currentEmail = domEmail;
            lastFoundOtp = "";
            console.log(`%c[Relay] 📬 Đã nhận email: ${{currentEmail}}`, "color:#38bdf8;font-weight:bold;");
            updateBadge(null, currentEmail, "Đã sẵn sàng", undefined);
        }}

        // Quét chi tiết hộp thư để lấy OTP nếu đang có email
        if (currentEmail) {{
            await checkInboxForOtp();
        }}

        const inboxCard = document.querySelector("#inbox") || document.querySelector("#inboxTable") || document.querySelector(".table");
        const inboxText = inboxCard ? inboxCard.innerText : "";

        try {{
            const startPing = Date.now();
            const resp = await fetch(`${{SERVER_URL}}/api/register/relay/heartbeat`, {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{
                    email: currentEmail,
                    inbox_text: inboxText,
                    otp: lastFoundOtp
                }})
            }});
            const ping = Date.now() - startPing;
            document.getElementById("relay-ping").textContent = ping + "ms";
            document.getElementById("relay-ping").style.color = "#4ade80";

            const data = await resp.json();
            updateBadge(
                "🟢 ChatGPT Relay",
                currentEmail,
                data.message || (data.waiting_for_otp ? "⏳ Đang chờ mã OTP từ OpenAI..." : "Sẵn sàng nhận lệnh"),
                data.total_registered
            );

            // Server yêu cầu sinh mail mới sau khi tạo xong tài khoản
            if (data.need_new_email && !isRequestingNewEmail) {{
                console.log("%c[Relay] ⚡ Server yêu cầu email mới!", "color:#fbbf24;font-weight:bold;");
                triggerNewEmail();
            }}
        }} catch (err) {{
            document.getElementById("relay-ping").textContent = "Mất kết nối";
            document.getElementById("relay-ping").style.color = "#ef4444";
            updateBadge("🔴 ChatGPT Relay", null, "Lỗi kết nối Server: " + err.message, undefined);
        }}
    }}, 1200);

    console.log("%c[ChatGPT2API Relay v1.3] Worker sẵn sàng!", "color:#4ade80;font-size:15px;font-weight:bold;");
}})();
"""
        return PlainTextResponse(js_code, media_type="application/javascript")

    return router
