from __future__ import annotations

import re
import threading
import time
from typing import Any


class BrowserRelayManager:
    """Quản lý kết nối giữa tab trình duyệt thật (mở etempmail.com) và backend server.

    Quy trình:
    1. Trình duyệt thật mở https://etempmail.com (Cloudflare Turnstile pass 100%).
    2. Script trên F12 Console gửi heartbeat kèm địa chỉ email hiện có lên server.
    3. Khi đăng ký tài khoản ChatGPT, server lấy email này.
    4. OpenAI gửi mã OTP về etempmail.com -> script trên trình duyệt bắt mã và gửi lên server.
    5. Server hoàn tất đăng ký -> gửi tín hiệu yêu cầu trình duyệt đổi/xóa mail để lấy email mới.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()

        # Trạng thái email
        self.current_email: str = ""
        self.last_dispatched_email: str = ""
        self.need_new_email: bool = False

        # Trạng thái OTP
        self.waiting_for_otp: bool = False
        self.target_email_for_otp: str = ""
        self.current_otp: str = ""

        # Đồng bộ luồng (thread synchronization)
        self.email_event = threading.Event()
        self.otp_event = threading.Event()

        # Thống kê & kết nối
        self.last_heartbeat: float = 0.0
        self.total_registered: int = 0
        self.last_status_message: str = "Đang chờ trình duyệt kết nối..."

    @property
    def is_connected(self) -> bool:
        """Trình duyệt được coi là online nếu có heartbeat trong 10 giây qua."""
        return (time.time() - self.last_heartbeat) < 10.0

    def get_status(self) -> dict[str, Any]:
        with self.lock:
            return {
                "connected": self.is_connected,
                "current_email": self.current_email,
                "last_dispatched_email": self.last_dispatched_email,
                "need_new_email": self.need_new_email,
                "waiting_for_otp": self.waiting_for_otp,
                "target_email": self.target_email_for_otp,
                "has_otp": bool(self.current_otp),
                "total_registered": self.total_registered,
                "last_heartbeat_ago": round(time.time() - self.last_heartbeat, 1) if self.last_heartbeat else None,
                "status_message": self.last_status_message,
            }

    # ──────────────────────── Phía Trình duyệt gọi (Client API) ────────────────────────

    def browser_heartbeat(self, email: str = "", inbox_text: str = "", otp: str = "") -> dict[str, Any]:
        """Được gọi định kỳ (mỗi 1-2s) từ console script trên etempmail.com."""
        clean_email = str(email or "").strip()
        clean_otp = str(otp or "").strip()

        with self.lock:
            self.last_heartbeat = time.time()

            # Nếu trình duyệt báo email hợp lệ
            if clean_email and "@" in clean_email and "get-a-real-job" not in clean_email:
                if clean_email != self.last_dispatched_email:
                    self.current_email = clean_email
                    self.need_new_email = False
                    self.email_event.set()
                    self.last_status_message = f"Email sẵn sàng: {clean_email}"
                else:
                    self.current_email = clean_email

            # Xử lý OTP nếu được gửi kèm trực tiếp hoặc trích xuất từ inbox
            if clean_otp and len(clean_otp) == 6 and clean_otp.isdigit():
                self.current_otp = clean_otp
                self.otp_event.set()
                self.last_status_message = f"Đã nhận mã OTP: {clean_otp}"
            elif self.waiting_for_otp and inbox_text and not self.current_otp:
                code = self._extract_code(inbox_text)
                if code:
                    self.current_otp = code
                    self.otp_event.set()
                    self.last_status_message = f"Đã nhận mã OTP: {code}"

            return {
                "status": "ok",
                "need_new_email": self.need_new_email,
                "waiting_for_otp": self.waiting_for_otp,
                "target_email": self.target_email_for_otp,
                "total_registered": self.total_registered,
                "message": self.last_status_message,
            }

    def browser_submit_otp(self, email: str, code: str) -> dict[str, Any]:
        """Trình duyệt gửi mã OTP nhận được."""
        clean_code = str(code or "").strip()
        with self.lock:
            if clean_code and len(clean_code) == 6 and clean_code.isdigit():
                self.current_otp = clean_code
                self.otp_event.set()
                self.last_status_message = f"Nhận OTP từ browser: {clean_code}"
                return {"status": "ok", "message": f"OTP {clean_code} đã được ghi nhận"}
            return {"status": "error", "message": "Mã OTP không hợp lệ"}

    def browser_ack_new_email(self, new_email: str = "") -> dict[str, Any]:
        """Trình duyệt xác nhận đã bấm đổi/xóa mail và sinh email mới thành công."""
        clean_email = str(new_email or "").strip()
        with self.lock:
            self.last_heartbeat = time.time()
            if clean_email and "@" in clean_email:
                self.current_email = clean_email
                self.need_new_email = False
                self.email_event.set()
                self.last_status_message = f"Đã đổi sang email mới: {clean_email}"
                return {"status": "ok"}
            # Nếu browser chỉ bấm nút đổi mail và chưa kịp lấy email mới
            self.need_new_email = False
            return {"status": "ok", "message": "Đã ghi nhận thao tác đổi mail"}

    # ──────────────────────── Phía Server gọi (Mail Provider API) ────────────────────────

    def server_wait_for_mailbox(self, timeout: float = 60.0) -> dict[str, Any]:
        """Được gọi bởi BrowserRelayMailProvider.create_mailbox()."""
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            with self.lock:
                if not self.is_connected:
                    self.last_status_message = "Chờ kết nối từ trình duyệt..."
                else:
                    # Nếu có email hợp lệ và chưa từng dùng cho lần này
                    if self.current_email and self.current_email != self.last_dispatched_email:
                        self.last_dispatched_email = self.current_email
                        self.need_new_email = False
                        # Chuẩn bị cho lần nhận OTP kế tiếp
                        self.current_otp = ""
                        self.otp_event.clear()
                        self.last_status_message = f"Đang đăng ký OpenAI với: {self.current_email}"
                        return {
                            "provider": "browser_relay",
                            "address": self.current_email,
                        }
                    else:
                        # Cần yêu cầu browser sinh mail mới
                        self.need_new_email = True
                        self.email_event.clear()
                        self.last_status_message = "Yêu cầu trình duyệt tạo email mới..."

            # Chờ sự kiện có email mới từ browser
            wait_time = min(2.0, max(0.5, deadline - time.monotonic()))
            self.email_event.wait(wait_time)

        if not self.is_connected:
            raise RuntimeError(
                "Browser Relay: Chưa có trình duyệt nào kết nối! "
                "Hãy mở trang https://etempmail.com trên Chrome máy bạn và chạy script trên Console F12."
            )
        raise RuntimeError(f"Browser Relay: Đã chờ {timeout}s nhưng trình duyệt chưa sinh được email mới.")

    def server_wait_for_otp(self, mailbox: dict[str, Any], timeout: float = 60.0) -> str | None:
        """Được gọi bởi BrowserRelayMailProvider.wait_for_code()."""
        address = str(mailbox.get("address") or "").strip()

        with self.lock:
            if self.current_otp:
                code = self.current_otp
                self.current_otp = ""
                return code
            self.waiting_for_otp = True
            self.target_email_for_otp = address
            self.otp_event.clear()
            self.last_status_message = f"Đang chờ mã OTP gửi tới {address}..."

        # Chờ browser báo OTP
        self.otp_event.wait(timeout)

        with self.lock:
            self.waiting_for_otp = False
            code = self.current_otp
            self.current_otp = ""
            return code if code else None

    def server_mailbox_done(self, mailbox: dict[str, Any] | None = None, success: bool = True) -> None:
        """Được gọi sau khi hoàn thành đăng ký hoặc kết thúc phiên."""
        with self.lock:
            if success:
                self.total_registered += 1
            self.need_new_email = True
            self.waiting_for_otp = False
            self.last_status_message = f"Hoàn thành {self.total_registered} tài khoản. Yêu cầu email tiếp theo..."

    def reset(self) -> None:
        """Reset toàn bộ trạng thái."""
        with self.lock:
            self.current_email = ""
            self.last_dispatched_email = ""
            self.need_new_email = False
            self.waiting_for_otp = False
            self.target_email_for_otp = ""
            self.current_otp = ""
            self.email_event.set()
            self.otp_event.set()
            self.last_status_message = "Đã reset trạng thái relay."

    @staticmethod
    def _extract_code(content: str) -> str | None:
        match = re.search(r"background-color:\s*#F3F3F3[^>]*>[\s\S]*?(\d{6})[\s\S]*?</p>", content, re.I)
        if match:
            return match.group(1)
        match = re.search(r"(?:Verification code|code is|mã xác thực|mã xác nhận|代码为|验证码)[:\s]*(\d{6})", content, re.I)
        if match and match.group(1) != "177010":
            return match.group(1)
        for code in re.findall(r">\s*(\d{6})\s*<|(?<![#&])\b(\d{6})\b", content):
            val = code[0] or code[1]
            if val and val != "177010":
                return val
        return None


# Singleton instance
browser_relay = BrowserRelayManager()
