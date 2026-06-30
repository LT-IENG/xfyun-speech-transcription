"""
音频处理工具模块
提供音频文件时长获取、自定义时间段裁剪、随机片段生成等功能。
基于 pydub（封装 ffmpeg）实现，支持 mp3/wav/m4a/flac/ogg/aac 等主流格式。

注意：需要系统安装 ffmpeg 或将其放在 PATH 中。
    pydub 会自动查找 ffmpeg，也可通过如下方式指定：
    from pydub import AudioSegment
    AudioSegment.converter = "/path/to/ffmpeg.exe"
"""

import os
import random
import tempfile
from typing import Optional

from pydub import AudioSegment


# ============================================================================
# 支持的音频格式
# ============================================================================

SUPPORTED_FORMATS = {
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac",
    ".opus", ".wma", ".amr", ".ape", ".aiff", ".au",
    ".raw", ".pcm", ".mp2", ".ac3",
}


def is_supported(file_path: str) -> bool:
    """
    检查文件格式是否受支持。

    Args:
        file_path: 音频文件路径

    Returns:
        True 如果格式受支持
    """
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUPPORTED_FORMATS


# ============================================================================
# 音频信息获取
# ============================================================================

def get_audio_duration(file_path: str) -> float:
    """
    获取音频文件总时长（秒）。

    Args:
        file_path: 音频文件路径

    Returns:
        时长（秒），浮点数
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"音频文件不存在: {file_path}")

    audio = AudioSegment.from_file(file_path)
    return len(audio) / 1000.0  # 毫秒 → 秒


def get_audio_info(file_path: str) -> dict:
    """
    获取音频文件的详细信息。

    Args:
        file_path: 音频文件路径

    Returns:
        包含以下字段的字典:
            - duration_sec:   总时长（秒）
            - duration_str:   总时长（HH:MM:SS）
            - sample_rate:    采样率（Hz）
            - channels:       声道数
            - sample_width:   位深度（字节）
            - format:         文件格式
            - size_mb:        文件大小（MB）
            - file_name:      文件名
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"音频文件不存在: {file_path}")

    audio = AudioSegment.from_file(file_path)
    duration_sec = len(audio) / 1000.0
    file_size = os.path.getsize(file_path)

    return {
        "duration_sec": round(duration_sec, 1),
        "duration_str": _sec_to_hms(duration_sec),
        "sample_rate": audio.frame_rate,
        "channels": audio.channels,
        "sample_width": audio.sample_width,
        "format": os.path.splitext(file_path)[1].upper().lstrip("."),
        "size_mb": round(file_size / (1024 * 1024), 2),
        "file_name": os.path.basename(file_path),
    }


# ============================================================================
# 音频片段提取
# ============================================================================

def extract_segment(
    file_path: str,
    start_sec: float,
    end_sec: float,
    output_path: Optional[str] = None,
) -> str:
    """
    从音频文件中裁剪指定时间段。

    Args:
        file_path:   源音频文件路径
        start_sec:   起始时间（秒）
        end_sec:     结束时间（秒）
        output_path: 输出文件路径（如果为 None，自动生成临时文件）

    Returns:
        裁剪后的音频文件路径
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"音频文件不存在: {file_path}")

    if start_sec < 0:
        raise ValueError(f"起始时间不能为负数: {start_sec}")
    if end_sec <= start_sec:
        raise ValueError(f"结束时间 {end_sec}s 必须大于起始时间 {start_sec}s")

    # 加载音频
    audio = AudioSegment.from_file(file_path)
    total_ms = len(audio)

    # 转换为毫秒
    start_ms = int(start_sec * 1000)
    end_ms = int(end_sec * 1000)

    # 边界检查
    start_ms = max(0, min(start_ms, total_ms))
    end_ms = max(0, min(end_ms, total_ms))

    # 裁剪
    segment = audio[start_ms:end_ms]

    # 确定输出格式（保持原格式）
    ext = os.path.splitext(file_path)[1].lower()
    if not ext:
        ext = ".wav"

    # 生成输出路径
    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        output_path = tmp.name
        tmp.close()

    # 导出
    segment.export(output_path, format=ext.lstrip("."))
    return output_path


def generate_random_segment(
    file_path: str,
    duration_sec: float,
    output_path: Optional[str] = None,
) -> tuple:
    """
    从音频文件中随机截取指定时长的片段。

    Args:
        file_path:     源音频文件路径
        duration_sec:  目标片段时长（秒）
        output_path:   输出文件路径

    Returns:
        (output_path, start_sec, end_sec) 元组
    """
    total_duration = get_audio_duration(file_path)

    if duration_sec >= total_duration:
        # 如果请求时长 >= 总时长，直接返回全部
        path = extract_segment(file_path, 0, total_duration, output_path)
        return (path, 0.0, total_duration)

    # 随机起始位置
    max_start = total_duration - duration_sec
    start_sec = random.uniform(0, max_start)
    end_sec = start_sec + duration_sec

    path = extract_segment(file_path, start_sec, end_sec, output_path)
    return (path, start_sec, end_sec)


# ============================================================================
# 工具函数
# ============================================================================

def _sec_to_hms(seconds: float) -> str:
    """
    秒数转 HH:MM:SS 格式。

    Args:
        seconds: 秒数

    Returns:
        HH:MM:SS 格式字符串
    """
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def hms_to_sec(hms: str) -> float:
    """
    HH:MM:SS 格式转秒数。

    Args:
        hms: 时间字符串，如 "01:30:45"

    Returns:
        秒数
    """
    parts = hms.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    else:
        return float(parts[0])


def cleanup_temp_file(file_path: str):
    """
    安全删除临时文件。

    Args:
        file_path: 要删除的文件路径
    """
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except OSError:
        pass  # 忽略删除失败
