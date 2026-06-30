"""
讯飞录音文件转写大模型 (Ifasr_llm) API 客户端
完全匹配官方 Python 示例：手动 urlencode 构建完整 URL，不使用 requests 的 params= 参数。
"""

import base64
import hashlib
import hmac
import json
import os
import random
import string
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable

import requests


# ============================================================================
# 工具
# ============================================================================

def _now() -> str:
    """东八区 ISO8601"""
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S+0800")


def _rand16() -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=16))


# ============================================================================
# 签名 — 完全匹配 urlencode 默认行为 (quote_plus, safe='/')
# ============================================================================

def _enc(v: str) -> str:
    return urllib.parse.quote_plus(str(v), safe='/')


def _sign(secret: str, params: dict) -> str:
    """HMAC-SHA1 签名。排除 signature 键 + 空值 → 排序 → _enc(k)=_enc(v) → & 拼接 → HMAC → Base64"""
    items = [(k, v) for k, v in params.items()
             if k != "signature" and str(v) != ""]
    items.sort(key=lambda x: x[0])
    base = "&".join(f"{_enc(k)}={_enc(str(v))}" for k, v in items)
    raw = hmac.new(secret.encode(), base.encode(), hashlib.sha1).digest()
    return base64.b64encode(raw).decode()


def _build_url_no_sig(base_url: str, params: dict) -> str:
    """构建不含签名的 URL（签名单独放 Header）"""
    qs = urllib.parse.urlencode(params)
    return f"{base_url}?{qs}"


# ============================================================================
# 领域
# ============================================================================

DOMAIN_MAP = {
    "通用": "",    "法院": "court",   "金融": "finance",
    "医疗": "medical", "科技": "tech",  "体育": "sport",
    "教育": "edu",   "运营商": "isp",    "政府": "gov",
    "游戏": "game",  "电商": "ecom",   "军事": "mil",
    "企业": "com",   "生活": "life",   "娱乐": "ent",
    "文化": "culture", "汽车": "car",
}


# ============================================================================
# 客户端
# ============================================================================

class XfyunASRClient:

    def __init__(self, app_id: str, access_key_id: str, access_key_secret: str,
                 upload_url: str = "https://office-api-ist-dx.iflyaisol.com/v2/upload",
                 result_url: str = "https://office-api-ist-dx.iflyaisol.com/v2/getResult"):
        self.app_id = app_id
        self.key_id = access_key_id
        self.key_secret = access_key_secret
        self.up_url = upload_url
        self.res_url = result_url

    # ----------------------------------------------------------------
    # 上传
    # ----------------------------------------------------------------

    def upload_file(self,
                    file_path: str,
                    language: str = "autodialect",
                    role_type: int = 1,
                    role_num: int = 0,
                    pd: str = "",
                    duration_ms: str = "60000",
                    eng_smoothproc: bool = True,
                    eng_colloqproc: bool = False,
                    duration_check_disable: bool = False,
                    progress_callback: Optional[Callable[[str], None]] = None,
                    ) -> Optional[str]:

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        flen = os.path.getsize(file_path)
        fname = os.path.basename(file_path)

        # 构建业务参数
        p = {
            "appId":           self.app_id,
            "accessKeyId":     self.key_id,
            "dateTime":        _now(),
            "signatureRandom": _rand16(),
            "fileSize":        str(flen),
            "fileName":        fname,
            "language":        language,
        }
        if duration_check_disable:
            p["durationCheckDisable"] = "true"
        else:
            p["duration"] = duration_ms

        if role_type:
            p["roleType"] = str(role_type)
        if role_num > 0:
            p["roleNum"] = str(role_num)
        if pd:
            p["pd"] = pd
        if not eng_smoothproc:
            p["eng_smoothproc"] = "false"
        if eng_colloqproc:
            p["eng_colloqproc"] = "true"

        # 计算签名（放入 Header）
        sig = _sign(self.key_secret, p)

        # URL 仅包含业务参数（不含 signature）
        full_url = _build_url_no_sig(self.up_url, p)

        if progress_callback:
            progress_callback(f"正在上传 ({flen / 1024 / 1024:.1f} MB)...")

        try:
            with open(file_path, "rb") as f:
                body = f.read()

            # signature 在 Header 中，不在 URL 中
            resp = requests.post(
                url=full_url,
                headers={
                    "Content-Type": "application/octet-stream",
                    "signature": sig,
                },
                data=body,
                timeout=120,
            )
            result = resp.json()

            if progress_callback:
                progress_callback(
                    f"上传响应: {result.get('descInfo', result.get('message', ''))}"
                )

            code = result.get("code")
            if code == "000000":
                inner = result.get("data") or result.get("content") or {}
                oid = inner.get("orderId", "")
                if progress_callback:
                    progress_callback(f"上传成功！OrderId: {oid}")
                return oid
            else:
                err = result.get("descInfo") or result.get("message") or f"code={code}"
                raise RuntimeError(f"上传失败: {err}")

        except requests.RequestException as e:
            raise RuntimeError(f"网络请求失败: {str(e)}")

    # ----------------------------------------------------------------
    # 结果查询
    # ----------------------------------------------------------------

    def get_result(self,
                   order_id: str,
                   poll_interval: int = 5,
                   max_wait: int = 3600,
                   progress_callback: Optional[Callable[[str], None]] = None,
                   ) -> dict:

        t0 = time.time()
        while True:
            if time.time() - t0 > max_wait:
                raise TimeoutError(f"超时 ({max_wait}s)")

            p = {
                "appId":           self.app_id,
                "accessKeyId":     self.key_id,
                "dateTime":        _now(),
                "signatureRandom": _rand16(),
                "orderId":         order_id,
            }
            sig = _sign(self.key_secret, p)
            full_url = _build_url_no_sig(self.res_url, p)

            try:
                resp = requests.get(
                    url=full_url,
                    headers={"signature": sig},
                    timeout=30,
                )
                result = resp.json()

                inner = result.get("data") or result.get("content") or {}
                oi = inner.get("orderInfo", {})
                st = int(oi.get("status", inner.get("status", -1)))

                lb = {0: "已创建", 3: "处理中...", 4: "完成", -1: "失败"}
                if progress_callback:
                    progress_callback(f"{lb.get(st, f'状态:{st}')} | {int(time.time()-t0)}s")

                if st == 4:
                    raw = inner.get("orderResult", "{}")
                    return json.loads(raw)
                if st == -1:
                    raise RuntimeError(f"转写失败: {oi.get('failReason', '未知')}")

                time.sleep(poll_interval)
            except requests.RequestException as e:
                if progress_callback:
                    progress_callback(f"网络异常: {e}")
                time.sleep(poll_interval)

    # ----------------------------------------------------------------
    # 解析
    # ----------------------------------------------------------------

    def parse_result(self, order_result: dict) -> list:
        paragraphs = []
        lattice = order_result.get("lattice", [])
        if not lattice:
            return paragraphs

        spk, parts, st_ms, ed_ms = None, [], None, None

        def _flush():
            """保存当前积累的说话人段落"""
            nonlocal spk, parts, st_ms, ed_ms
            if spk and parts:
                # 清理首尾空白和尾部标点
                text = "".join(parts).strip()
                # 移除末尾连续标点（逗号、句号、顿号等）
                while text and text[-1] in "，,。.、！!？?；;：:…—-":
                    text = text[:-1]
                text = text.strip()
                if text:
                    paragraphs.append({
                        "speaker": spk,
                        "start_time": _hms(st_ms or 0),
                        "end_time": _hms(ed_ms or 0),
                        "text": text,
                    })
            spk, parts, st_ms, ed_ms = None, [], None, None

        for item in lattice:
            js = item.get("json_1best", "{}")
            try:
                parsed = json.loads(js)
                st = parsed.get("st", {})
                rl = int(st.get("rl", 0))
                rt = st.get("rt", [])
                bg = int(st.get("bg", item.get("bg", 0)))
                ed = int(st.get("ed", item.get("ed", 0)))
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
            if not rt:
                continue

            words = []
            for ri in rt:
                for ws in ri.get("ws", []):
                    for cw in ws.get("cw", []):
                        words.append(cw.get("w", ""))
            txt = "".join(words)
            if not txt:
                continue

            cur_label = f"说话人{rl}" if rl > 0 else None

            if cur_label:
                # 有明确的角色切换标记
                if spk == cur_label:
                    # 同一说话人延续 → 合并
                    parts.append(txt)
                    ed_ms = ed
                else:
                    # 不同说话人 → 保存上一段，开始新段
                    _flush()
                    spk = cur_label
                    parts = [txt]
                    st_ms, ed_ms = bg, ed
            else:
                # rl == 0：延续当前说话人
                if spk is None:
                    spk = "说话人1"
                    st_ms = bg
                parts.append(txt)
                ed_ms = ed

        _flush()
        return paragraphs

    # ----------------------------------------------------------------
    # 一键
    # ----------------------------------------------------------------

    def transcribe(self, file_path: str,
                   language: str = "autodialect",
                   role_type: int = 1, role_num: int = 0,
                   pd: str = "", duration_ms: str = "60000",
                   eng_smoothproc: bool = True, eng_colloqproc: bool = False,
                   duration_check_disable: bool = False,
                   poll_interval: int = 5, max_wait: int = 3600,
                   progress_callback: Optional[Callable[[str], None]] = None,
                   ) -> list:
        oid = self.upload_file(
            file_path=file_path, language=language,
            role_type=role_type, role_num=role_num, pd=pd,
            duration_ms=duration_ms,
            eng_smoothproc=eng_smoothproc, eng_colloqproc=eng_colloqproc,
            duration_check_disable=duration_check_disable,
            progress_callback=progress_callback,
        )
        if not oid:
            raise RuntimeError("上传失败")
        raw = self.get_result(order_id=oid, poll_interval=poll_interval,
                              max_wait=max_wait, progress_callback=progress_callback)
        return self.parse_result(raw)

    @staticmethod
    def format_txt(paragraphs: list) -> str:
        lines = []
        for p in paragraphs:
            lines.append(f"{p['start_time']} - {p['end_time']} {p['speaker']}")
            lines.append(p["text"])
            lines.append("")
        return "\n".join(lines)


def _hms(ms: int) -> str:
    t = max(0, ms // 1000)
    return f"{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}"
