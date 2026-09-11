"""Script smoke test cho EtempMailProvider.

Chạy:
    uv run python services/register/test_etempmail.py
"""
import sys, time, pprint
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.register.mail_provider import EtempMailProvider

conf = {
    "request_timeout": 30,
    "wait_timeout": 90,
    "wait_interval": 3,
    "user_agent": "",
}

entry = {
    "provider_ref": "etempmail#1",
    "headless": True,
    "browser_proxy": "",
    "req_proxy": "",
    "max_browser_retries": 2,
    "browser_timeout": 45,
}

print("=== EtempMailProvider Smoke Test ===")
print("1. Tạo hộp thư (Playwright browser sẽ khởi động)...")
t0 = time.time()
provider = EtempMailProvider(entry, conf)
try:
    mailbox = provider.create_mailbox()
    elapsed = time.time() - t0
    print(f"   OK: Hộp thư tạo thành công sau {elapsed:.1f}s")
    print(f"   Địa chỉ : {mailbox['address']}")
    print(f"   Cookies : {list(mailbox.get('cookies', {}).keys())}")
    print(f"   Recover : {mailbox.get('recover_key', '(trống)')}")

    print("\n2. Poll inbox (chưa có thư — None là đúng)...")
    msg = provider.fetch_latest_message(mailbox)
    print(f"   Inbox: {pprint.pformat(msg)}")

    print("\n3. Dọn dẹp hộp thư...")
    provider.close()
    print("   OK: Đã xoá hộp thư")
except Exception as exc:
    print(f"   LOI: {exc}")
    import traceback; traceback.print_exc()
    sys.exit(1)

print("\n=== PASS ===")
