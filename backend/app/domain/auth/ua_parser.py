"""
User-Agent 解析工具 — 从 UA 字符串提取设备/浏览器/OS信息

不依赖外部库，纯字符串匹配。
"""
from __future__ import annotations


def parse_user_agent(ua: str) -> dict:
    """解析 User-Agent 字符串，返回设备类型、浏览器、OS"""
    if not ua:
        return {"device_type": "unknown", "browser": "unknown", "os": "unknown"}

    ua_lower = ua.lower()

    # ── 设备类型 ──
    device_type = "desktop"
    if any(k in ua_lower for k in ["mobile", "android", "iphone", "ipod"]):
        device_type = "mobile"
    elif "ipad" in ua_lower or ("tablet" in ua_lower):
        device_type = "tablet"

    # ── 浏览器 ──
    browser = "unknown"
    if "edg/" in ua_lower or "edge" in ua_lower:
        browser = "Edge"
    elif "opr/" in ua_lower or "opera" in ua_lower:
        browser = "Opera"
    elif "vivaldi" in ua_lower:
        browser = "Vivaldi"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif "chrome" in ua_lower and "edg/" not in ua_lower:
        browser = "Chrome"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    elif "msie" in ua_lower or "trident" in ua_lower:
        browser = "IE"

    # ── 操作系统 ──
    os_name = "unknown"
    if "windows" in ua_lower:
        os_name = "Windows"
    elif "mac os" in ua_lower or "macos" in ua_lower:
        os_name = "macOS"
    elif "linux" in ua_lower and "android" not in ua_lower:
        os_name = "Linux"
    elif "android" in ua_lower:
        os_name = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower or "ipod" in ua_lower:
        os_name = "iOS"
    elif "crOS" in ua:
        os_name = "ChromeOS"

    return {"device_type": device_type, "browser": browser, "os": os_name}


def parse_ip_region(ip: str) -> dict:
    """
    根据 IP 推断区域（简化版，无外部依赖）
    生产环境应使用 GeoIP 数据库或 API
    """
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return {"country": "本地", "region": "本地", "city": "本地网络"}

    # 内网 IP
    if ip.startswith(("192.168.", "10.", "172.16.", "172.17.", "172.18.",
                       "172.19.", "172.2", "172.3")):
        return {"country": "内网", "region": "内网", "city": "局域网"}

    return {"country": "", "region": "", "city": ""}
