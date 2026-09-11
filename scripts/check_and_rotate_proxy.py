#!/usr/bin/env python3
"""
Script tự động kiểm tra proxy với ChatGPT và etempmail.com.
Sử dụng 2 Key xoay IP luân phiên để giảm tối đa thời gian chờ cooldown.
"""

import sys
import time
import json
import re
from datetime import datetime
from urllib.parse import urlparse
import requests

# ==================== CẤU HÌNH ====================
PROXY_URL = "http://g3gFg0o6:VIdP062Y@hndc57.proxyxoay.net:14350"

ROTATE_KEYS = [
    "3cf7e16b-958d-4639-8734-919525583e71",
    "0f2b25c1-e400-4ead-83bc-454aa3d5b616",
]

ETEMPMAIL_TIMEOUT = 30  # Giây chờ Turnstile sinh email
# ==================================================


def log(msg: str):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def get_ip_info(proxy_url: str) -> dict:
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        # Dùng HTTPS để tránh bị captive portal chuyển hướng trên HTTP
        r = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=12)
        ip = r.json().get("ip")
        # Lấy thêm thông tin vị trí
        r_info = requests.get(f"http://ip-api.com/json/{ip}", timeout=8)
        data = r_info.json()
        return data
    except Exception as e:
        return {"error": str(e)}


def check_chatgpt(proxy_url: str) -> tuple[bool, str]:
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        from curl_cffi import requests as c_requests
        r = c_requests.get("https://chatgpt.com", proxies=proxies, impersonate="chrome124", timeout=12)
        if r.status_code == 200 or r.status_code == 302:
            return True, f"HTTP {r.status_code} (OK)"
        return False, f"HTTP {r.status_code} (Bị chặn bởi Cloudflare)"
    except Exception as e:
        return False, f"Lỗi kết nối: {e}"


def check_etempmail_playwright(proxy_url: str) -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "Playwright chưa được cài đặt"

    u = urlparse(proxy_url)
    proxy_cfg = {"server": f"{u.scheme}://{u.hostname}:{u.port}"}
    if u.username:
        proxy_cfg["username"] = u.username
    if u.password:
        proxy_cfg["password"] = u.password

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                proxy=proxy_cfg,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = browser.new_context(
                locale="en-US",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            )
            page = context.new_page()
            page.goto("https://etempmail.com", wait_until="domcontentloaded", timeout=25000)

            page.wait_for_function(
                """() => {
                    const el = document.getElementById('tempEmailAddress');
                    return el && el.value && el.value.includes('@');
                }""",
                timeout=ETEMPMAIL_TIMEOUT * 1000,
            )
            email = page.input_value("#tempEmailAddress")
            browser.close()
            if email and "@" in email:
                return True, email
            return False, "Không lấy được email hợp lệ"
    except Exception as e:
        err_str = str(e)
        if "Timeout" in err_str:
            return False, f"Turnstile Timeout sau {ETEMPMAIL_TIMEOUT}s"
        return False, f"Lỗi: {err_str[:80]}"


def try_rotate_any_key(keys: list[str]) -> tuple[bool, str, int]:
    """
    Thử xoay IP bằng lần lượt các key.
    Nếu có key sẵn sàng -> đổi ngay lập tức và return (True, key, 0).
    Nếu tất cả đều đang cooldown -> return (False, key_min, số giây chờ nhỏ nhất).
    """
    min_wait = 9999
    best_key = keys[0]

    for key in keys:
        api_url = f"https://proxyxoay.net/api/rotating-proxy/change-key-ip/{key}"
        log(f"Thử gọi đổi IP với key: {key[:8]}...")
        try:
            r = requests.get(api_url, timeout=12)
            log(f"  -> Phản hồi: {r.status_code} - {r.text.strip()[:100]}")
            if r.status_code == 200:
                return True, key, 0

            try:
                data = r.json()
                msg = str(data.get("message", ""))
            except Exception:
                msg = r.text

            m = re.search(r"(\d+)", msg)
            wait_sec = int(m.group(1)) if m else 240
            if wait_sec < min_wait:
                min_wait = wait_sec
                best_key = key
        except Exception as e:
            log(f"  -> Lỗi kết nối API: {e}")

    return False, best_key, min_wait


def countdown(seconds: int):
    log(f"Bắt đầu đếm ngược {seconds}s ({seconds // 60}m {seconds % 60}s) đến lần đổi IP kế tiếp...")
    step = 15
    remaining = seconds
    while remaining > 0:
        mins, secs = divmod(remaining, 60)
        print(f"⏳ Còn lại {mins:02d}:{secs:02d}...", flush=True)
        sleep_chunk = min(step, remaining)
        time.sleep(sleep_chunk)
        remaining -= sleep_chunk
    print("⏳ Hết thời gian chờ!", flush=True)


def main():
    log("==================================================")
    log("BẮT ĐẦU CHƯƠNG TRÌNH TỰ ĐỘNG CHECK & XOAY PROXY")
    log(f"Proxy: {PROXY_URL}")
    log(f"Danh sách key xoay ({len(ROTATE_KEYS)} keys):")
    for k in ROTATE_KEYS:
        log(f" - {k}")
    log("==================================================")

    attempt = 1
    while True:
        log(f"\n[LẦN THỬ #{attempt}]")

        # 1. Kiểm tra IP hiện tại
        ip_data = get_ip_info(PROXY_URL)
        current_ip = ip_data.get("query") or ip_data.get("ip") or "Unknown"
        isp = ip_data.get("isp", "Unknown")
        country = ip_data.get("country", "Unknown")
        log(f"🌐 IP hiện tại: {current_ip} | Nhà mạng: {isp} ({country})")

        # 2. Test ChatGPT
        log("Kiểm tra kết nối ChatGPT (https://chatgpt.com)...")
        cg_ok, cg_msg = check_chatgpt(PROXY_URL)
        if cg_ok:
            log(f"✅ ChatGPT: PASS ({cg_msg})")
        else:
            log(f"❌ ChatGPT: FAIL ({cg_msg})")

        # 3. Test etempmail nếu ChatGPT pass
        etemp_ok = False
        if cg_ok:
            log("ChatGPT đã pass! Tiến hành kiểm tra etempmail.com qua Playwright...")
            etemp_ok, etemp_msg = check_etempmail_playwright(PROXY_URL)
            if etemp_ok:
                log(f"✅ etempmail: PASS (Email sinh ra: {etemp_msg})")
            else:
                log(f"❌ etempmail: FAIL ({etemp_msg})")
        else:
            log("⏭️ Bỏ qua bước etempmail vì ChatGPT đã bị chặn.")

        # 4. Thành công
        if cg_ok and etemp_ok:
            log("\n" + "=" * 50)
            log("🎉🎉🎉 TÌM THẤY PROXY SẠCH HOÀN TOÀN!")
            log(f"Proxy: {PROXY_URL}")
            log(f"Outbound IP: {current_ip}")
            log("=" * 50)

            with open("working_proxy.txt", "w") as f:
                f.write(f"Proxy: {PROXY_URL}\nIP: {current_ip}\nChecked_At: {datetime.now().isoformat()}\n")
            log("Đã lưu thông tin vào file 'working_proxy.txt'.")
            sys.exit(0)

        # 5. Xoay IP thông minh bằng 1 trong các keys
        attempt += 1
        rotated, used_key, wait_sec = try_rotate_any_key(ROTATE_KEYS)
        if not rotated:
            # Cả 2 keys đều đang cooldown -> chờ số giây nhỏ nhất của key gần nhất
            countdown(wait_sec)
            # Sau khi hết chờ, gọi đổi IP bằng key đó
            requests.get(f"https://proxyxoay.net/api/rotating-proxy/change-key-ip/{used_key}", timeout=12)

        log("Đợi 15s để proxy nạp IP mới...")
        time.sleep(15)


if __name__ == "__main__":
    main()
