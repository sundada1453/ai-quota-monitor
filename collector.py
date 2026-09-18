#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Quota Collector for Grok & Antigravity (AGY)
"""

import os
import re
import ssl
import time
import json
import sqlite3
import datetime
import urllib.request
import subprocess

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# 内存级数据缓存 (5秒缓存，避免 UI 高频刷新重复打接口)
_CACHED_AGY_DATA = None
_CACHED_AGY_TIME = 0
_CACHED_GROK_DATA = None
_CACHED_GROK_TIME = 0
CACHE_TTL_SEC = 5

def load_config():
    default_config = {
        "grok": {"weekly_quota_requests": 150, "weekly_quota_usd": 15.0},
        "antigravity": {"quota_window_hours": 5},
        "ui": {"refresh_seconds": 10}
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_config

def get_grok_quota_from_xai():
    """读取 ~/.grok/auth.json，向 xAI 官方获取与 Orca 完全一致的真实周额度"""
    global _CACHED_GROK_DATA, _CACHED_GROK_TIME
    now = time.time()
    if _CACHED_GROK_DATA and (now - _CACHED_GROK_TIME < CACHE_TTL_SEC):
        return _CACHED_GROK_DATA

    auth_path = os.path.expanduser("~/.grok/auth.json")
    if not os.path.exists(auth_path):
        return None
    try:
        with open(auth_path, "r", encoding="utf-8") as f:
            auth_data = json.load(f)
        session = None
        for k, v in auth_data.items():
            if "https://auth.x.ai" in k and isinstance(v, dict):
                session = v
                break
        if not session or not session.get("key"):
            return None
        
        url = "https://cli-chat-proxy.grok.com/v1/billing?format=credits"
        headers = {
            "Authorization": f"Bearer {session.get('key')}",
            "X-XAI-Token-Auth": "xai-grok-cli",
            "Accept": "application/json",
            "User-Agent": "xai-grok-cli"
        }
        if session.get("user_id"):
            headers["x-userid"] = session.get("user_id")
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                cfg = data.get("config", {})
                used_pct = cfg.get("creditUsagePercent", 0.0)
                end_iso = cfg.get("currentPeriod", {}).get("end") or cfg.get("billingPeriodEnd", "")
                
                cd_str = format_countdown(end_iso)
                res = {
                    "has_data": True,
                    "used_pct": round(float(used_pct), 1),
                    "remaining_pct": round(max(0.0, 100.0 - float(used_pct)), 1),
                    "reset_time_str": cd_str,
                    "reset_iso": end_iso,
                    "products": cfg.get("productUsage", [])
                }
                _CACHED_GROK_DATA = res
                _CACHED_GROK_TIME = now
                return res
    except Exception:
        pass
    if _CACHED_GROK_DATA:
        return _CACHED_GROK_DATA
    return None

def get_grok_weekly_stats(db_path="/root/.cc-switch/cc-switch.db"):
    now_ts = int(time.time())
    week_ago = now_ts - 7 * 86400
    res = {
        "requests_count": 0,
        "total_cost_usd": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "last_model": "grok-4.6",
        "has_data": False,
        "used_pct": 0.0,
        "remaining_pct": 100.0,
        "reset_time_str": "--:--"
    }

    # 1. 优先获取与 Orca 完全一致的官方真实周额度 (源自 ~/.grok/auth.json)
    xai_quota = get_grok_quota_from_xai()
    if xai_quota and xai_quota.get("has_data"):
        res["has_data"] = True
        res["has_real_quota"] = True
        res["used_pct"] = xai_quota["used_pct"]
        res["remaining_pct"] = xai_quota["remaining_pct"]
        res["reset_time_str"] = xai_quota["reset_time_str"]
        res["reset_iso"] = xai_quota.get("reset_iso", "")
        res["products"] = xai_quota.get("products", [])

    # 2. 补充本地 cc-switch 的花费与 Token 统计
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            c = conn.cursor()
            rows = c.execute("""
                SELECT model, total_cost_usd, input_tokens, output_tokens 
                FROM proxy_request_logs 
                WHERE created_at >= ?
                ORDER BY created_at DESC
            """, (week_ago,)).fetchall()
            
            if rows:
                res["requests_count"] = len(rows)
                res["last_model"] = rows[0][0] or "grok-4.6"
                total_cost = 0.0
                in_tok = 0
                out_tok = 0
                for r in rows:
                    try:
                        total_cost += float(r[1])
                    except Exception:
                        pass
                    in_tok += (r[2] or 0)
                    out_tok += (r[3] or 0)
                res["total_cost_usd"] = round(total_cost, 4)
                res["input_tokens"] = in_tok
                res["output_tokens"] = out_tok
            conn.close()
        except Exception as e:
            res["error"] = str(e)
            
    if not res.get("has_data") and res["requests_count"] > 0:
        res["has_data"] = True

    return res

def format_countdown(reset_time_str):
    """格式化到期重置倒计时为易读字符串 (如 1h 35m, 4天20h)"""
    if not reset_time_str:
        return "--:--"
    try:
        dt = datetime.datetime.fromisoformat(reset_time_str.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        diff_sec = int((dt - now).total_seconds())
        if diff_sec <= 0:
            return "已重置"
        days = diff_sec // 86400
        hours = (diff_sec % 86400) // 3600
        mins = (diff_sec % 3600) // 60
        if days > 0:
            return f"{days}天{hours}h"
        elif hours > 0:
            return f"{hours}h {mins:02d}m"
        else:
            return f"{mins}m"
    except Exception:
        return reset_time_str

def get_agy_access_token():
    paths = [
        os.path.expanduser("~/.gemini/antigravity-cli/antigravity-oauth-token"),
        os.path.expanduser("~/.gemini/antigravity/antigravity-oauth-token")
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    tok = d.get("token", {}).get("access_token")
                    if tok:
                        return tok
            except Exception:
                pass
    return None

def fetch_agy_quota_from_ls():
    """直接从本机正在运行的 Antigravity 桌面端 LanguageServer ConnectRPC 获取配额 (与桌面端完全同源)"""
    try:
        out = subprocess.check_output(["ps", "-eo", "pid,args"], text=True, timeout=2)
        csrf = None
        pid = None
        for line in out.splitlines():
            if "language_server" in line and "--csrf_token" in line:
                m_csrf = re.search(r"--csrf_token\s+([a-f0-9\-]+)", line)
                if m_csrf:
                    csrf = m_csrf.group(1)
                    pid = line.strip().split()[0]
                    break
        if not pid or not csrf:
            return None

        ss_out = subprocess.check_output(["ss", "-tulpn"], text=True, timeout=2)
        ports = []
        for sline in ss_out.splitlines():
            if f"pid={pid}," in sline and "127.0.0.1:" in sline:
                m_port = re.search(r"127\.0\.0\.1:(\d+)", sline)
                if m_port:
                    ports.append(int(m_port.group(1)))

        ctx = ssl._create_unverified_context()
        for p in ports:
            try:
                url = f"https://127.0.0.1:{p}/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"
                req = urllib.request.Request(
                    url,
                    data=b'{"forceRefresh":true}',
                    headers={
                        "Content-Type": "application/json",
                        "x-codeium-csrf-token": csrf
                    }
                )
                with urllib.request.urlopen(req, timeout=3, context=ctx) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        if "response" in data:
                            return data["response"]
                        return data
            except Exception:
                continue
    except Exception:
        pass
    return None

def fetch_agy_quota_from_api(token):
    url = "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary"
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "antigravity-cli"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass
    return None

def fetch_agy_quota_from_cli():
    """备用方式：通过执行 agy -p '/usage' 获取并解析配额"""
    try:
        out = subprocess.run(
            ["agy", "-p", "/usage"],
            capture_output=True,
            text=True,
            timeout=12
        )
        if out.returncode == 0 and "Quota:" in out.stdout:
            lines = out.stdout.strip().splitlines()
            data = {"groups": []}
            gemini_group = {"displayName": "Gemini Models", "buckets": []}
            claude_group = {"displayName": "Claude and GPT models", "buckets": []}
            for line in lines:
                parts = [p.strip() for p in line.split() if p.strip()]
                if not parts or parts[0] == "Quota:":
                    continue
                if "Gemini" in line:
                    target_g = gemini_group
                elif "Claude" in line or "GPT" in line:
                    target_g = claude_group
                else:
                    continue
                
                pct_str = next((p for p in parts if p.endswith("%")), None)
                iso_time = next((p for p in parts if "T" in p and p.endswith("Z")), "")
                if pct_str:
                    try:
                        pct_val = float(pct_str.replace("%", "")) / 100.0
                        b_id = "weekly" if "Weekly" in line else "5h"
                        target_g["buckets"].append({
                            "bucketId": b_id,
                            "remainingFraction": pct_val,
                            "resetTime": iso_time
                        })
                    except Exception:
                        pass
            if gemini_group["buckets"]:
                data["groups"].append(gemini_group)
            if claude_group["buckets"]:
                data["groups"].append(claude_group)
            return data
    except Exception:
        pass
    return None

def get_agy_quota_stats():
    global _CACHED_AGY_DATA, _CACHED_AGY_TIME
    now = time.time()
    if _CACHED_AGY_DATA and (now - _CACHED_AGY_TIME < CACHE_TTL_SEC):
        return _CACHED_AGY_DATA

    raw_data = fetch_agy_quota_from_ls()
    if not raw_data:
        token = get_agy_access_token()
        if token:
            raw_data = fetch_agy_quota_from_api(token)

    if not raw_data:
        raw_data = fetch_agy_quota_from_cli()

    res = {
        "has_data": False,
        "active_account": "taylorveronica157@gmail.com",
        "five_hour": {
            "remaining_pct": 100.0,
            "used_pct": 0.0,
            "reset_time_str": "--:--",
            "reset_iso": "",
            "description": ""
        },
        "weekly": {
            "remaining_pct": 100.0,
            "used_pct": 0.0,
            "reset_time_str": "--:--",
            "reset_iso": "",
            "description": ""
        },
        "claude_gpt": {
            "five_hour": {"remaining_pct": 100.0, "reset_time_str": "--:--"},
            "weekly": {"remaining_pct": 100.0, "reset_time_str": "--:--"}
        }
    }

    # 尝试读取当前活跃账号
    acc_file = "/root/.gemini/google_accounts.json"
    if os.path.exists(acc_file):
        try:
            with open(acc_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                res["active_account"] = d.get("active", res["active_account"])
        except Exception:
            pass

    if raw_data and "groups" in raw_data:
        res["has_data"] = True
        for g in raw_data.get("groups", []):
            name = g.get("displayName", "")
            is_gemini = "Gemini" in name
            is_claude = "Claude" in name or "GPT" in name

            for b in g.get("buckets", []):
                window = b.get("window", "")
                bucket_id = b.get("bucketId", "")
                rem_frac = b.get("remainingFraction", 1.0)
                rem_pct = round(rem_frac * 100.0, 1)
                used_pct = round(max(0.0, 100.0 - rem_pct), 1)
                reset_iso = b.get("resetTime", "")
                reset_str = format_countdown(reset_iso)

                bucket_info = {
                    "remaining_pct": rem_pct,
                    "used_pct": used_pct,
                    "reset_time_str": reset_str,
                    "reset_iso": reset_iso,
                    "description": b.get("description", "")
                }

                if is_gemini:
                    if window == "5h" or "5h" in bucket_id or "Five" in b.get("displayName", ""):
                        res["five_hour"] = bucket_info
                    elif window == "weekly" or "weekly" in bucket_id or "Weekly" in b.get("displayName", ""):
                        res["weekly"] = bucket_info
                elif is_claude:
                    if window == "5h" or "5h" in bucket_id or "Five" in b.get("displayName", ""):
                        res["claude_gpt"]["five_hour"] = bucket_info
                    elif window == "weekly" or "weekly" in bucket_id or "Weekly" in b.get("displayName", ""):
                        res["claude_gpt"]["weekly"] = bucket_info

        # 更新缓存
        _CACHED_AGY_DATA = res
        _CACHED_AGY_TIME = now
        return res

    # 若抓取失败但有旧缓存，返回旧缓存
    if _CACHED_AGY_DATA:
        return _CACHED_AGY_DATA
    return res

def get_full_snapshot():
    cfg = load_config()
    grok_stats = get_grok_weekly_stats()
    agy_stats = get_agy_quota_stats()

    # 计算 Grok 百分比 (已消耗)
    grok_limit = cfg.get("grok", {}).get("weekly_quota_requests", 150)
    if grok_stats.get("has_real_quota"):
        grok_pct = grok_stats.get("used_pct", 0.0)
    else:
        grok_pct = min(100.0, (grok_stats["requests_count"] / max(1, grok_limit)) * 100)

    # 保持向后兼容字段
    agy_5h = agy_stats.get("five_hour", {})
    agy_w = agy_stats.get("weekly", {})

    return {
        "timestamp": time.time(),
        "grok": {
            **grok_stats,
            "quota_limit": grok_limit,
            "percentage": round(grok_pct, 1)
        },
        "antigravity": {
            **agy_stats,
            "percentage": agy_5h.get("used_pct", 0.0),
            "reset_time_str": agy_5h.get("reset_time_str", "--:--")
        }
    }

if __name__ == "__main__":
    import pprint
    pprint.pprint(get_full_snapshot())
