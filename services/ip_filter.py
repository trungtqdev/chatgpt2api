from __future__ import annotations

import ipaddress
from fastapi import HTTPException, Request

from services.config import config


def get_client_ip(request: Request) -> str:
    """Trích xuất địa chỉ IP thực của client từ các header proxy (Cloudflare, Nginx, v.v.)."""
    # 1. Cloudflare header
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip and cf_ip.strip():
        return cf_ip.strip()

    # 2. X-Forwarded-For header (IP đầu tiên là client gốc)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and forwarded.strip():
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[0]

    # 3. X-Real-IP header từ reverse proxy (Nginx)
    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()

    # 4. Fallback socket IP từ kết nối trực tiếp
    if request.client and request.client.host:
        return request.client.host.strip()

    return ""


def is_ip_in_whitelist(ip_str: str, allowed_patterns: list[str]) -> bool:
    """Kiểm tra IP có khớp với danh sách cho phép (hỗ trợ cả IP đơn và CIDR subnet)."""
    if not ip_str:
        return False

    # Luôn cho phép localhost/loopback
    if ip_str in {"127.0.0.1", "::1", "localhost"}:
        return True

    try:
        client_addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    for pattern in allowed_patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        try:
            if "/" in pattern:
                net = ipaddress.ip_network(pattern, strict=False)
                if client_addr in net:
                    return True
            else:
                if client_addr == ipaddress.ip_address(pattern):
                    return True
        except ValueError:
            continue

    return False


def check_api_ip_allowed(request: Request, identity: dict[str, object] | None = None) -> None:
    """Kiểm tra quyền truy cập IP đối với các API endpoint.

    Nếu chế độ không phải 'whitelist' hoặc danh sách IP rỗng -> cho phép.
    Nếu cấu hình cho phép admin bypass và identity là admin -> cho phép.
    Nếu IP không thuộc danh sách cho phép -> ném HTTPException 403.
    """
    if config.ip_access_mode != "whitelist":
        return

    # Bỏ qua giới hạn IP nếu người gọi là quản trị viên và cấu hình bypass đang bật
    if config.ip_whitelist_bypass_admin and identity and identity.get("role") == "admin":
        return

    allowed_ips = config.allowed_ips
    if not allowed_ips:
        # Nếu bật whitelist nhưng chưa nhập IP nào, không chặn để tránh lockout
        return

    client_ip = get_client_ip(request)
    if not is_ip_in_whitelist(client_ip, allowed_ips):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "message": f"Địa chỉ IP {client_ip or 'không xác định'} không được phép truy cập API (IP not allowed).",
                    "type": "ip_forbidden",
                    "code": 403,
                }
            },
        )
