"""
配置管理模块
- api_config.json：API 凭证、接口地址、超时参数（JSON 格式，方便调试）
- QSettings：UI 偏好（主题、自动识别人数、输出目录等）
"""

import json
import os
import sys
from PyQt6.QtCore import QSettings

# ============================================================================
# 路径（兼容 PyInstaller 打包后的 _MEIPASS）
# ============================================================================

def _get_writable_dir() -> str:
    """获取可写目录：开发环境=项目根目录，PyInstaller=EXE所在目录"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _get_bundled_config_path() -> str:
    """获取只读的默认配置路径（PyInstaller 内置配置）"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, "api_config.json")
    return os.path.join(_get_writable_dir(), "api_config.json")

# 可写的配置文件路径（用户修改后保存在此）
_API_CONFIG_PATH = os.path.join(_get_writable_dir(), "api_config.json")
# 内置默认配置（首次运行或重置时使用）
_DEFAULT_CONFIG_PATH = os.path.join(_get_writable_dir(), "api_config.json")

# ============================================================================
# QSettings 默认值（不含 API 凭证）
# ============================================================================

ORGANIZATION_NAME = "XfyunASR"
APPLICATION_NAME = "讯飞语音转写"

DEFAULT_CONFIG = {
    "auto_speaker": True,
    "theme": "dark",
    "output_dir": "",
}


# ============================================================================
# ConfigManager
# ============================================================================

class ConfigManager:
    """
    配置管理器：
      - API 配置 → 读写 api_config.json
      - UI 偏好  → QSettings
    """

    def __init__(self):
        self._settings = QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
        self._api_config = {}
        self._load_api_config()

    # ------------------------------------------------------------------
    # api_config.json 读写
    # ------------------------------------------------------------------

    def _load_api_config(self):
        """加载 API 配置：优先可写位置 → 回退内置默认（PyInstaller）"""
        try:
            # 1. 优先加载用户保存的配置
            if os.path.exists(_API_CONFIG_PATH):
                with open(_API_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            # 2. PyInstaller：首次运行从内置配置复制
            elif hasattr(sys, '_MEIPASS'):
                bundled = os.path.join(sys._MEIPASS, "api_config.json")
                if os.path.exists(bundled):
                    with open(bundled, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # 复制到可写位置
                    self._api_config = data.get("api", {})
                    self._save_api_config()
                    return
                else:
                    data = {}
            else:
                data = {}
            self._api_config = data.get("api", {})
        except (json.JSONDecodeError, IOError) as e:
            print(f"[ConfigManager] 加载 api_config.json 失败: {e}")
            self._api_config = {}

    def _save_api_config(self):
        """保存 API 配置到可写位置"""
        try:
            data = {}
            if os.path.exists(_API_CONFIG_PATH):
                try:
                    with open(_API_CONFIG_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    data = {}

            data["api"] = self._api_config

            os.makedirs(os.path.dirname(_API_CONFIG_PATH), exist_ok=True)
            with open(_API_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"[ConfigManager] 保存 api_config.json 失败: {e}")

    # ------------------------------------------------------------------
    # API 配置 get/set
    # ------------------------------------------------------------------

    def get_api(self, key: str, default=None):
        """读取 API 配置项"""
        return self._api_config.get(key, default)

    def set_api(self, key: str, value):
        """写入 API 配置项并即时保存"""
        self._api_config[key] = value
        self._save_api_config()

    def get_api_credentials(self) -> dict:
        """获取完整的 API 凭证和端点信息"""
        return {
            "app_id":            self._api_config.get("app_id", ""),
            "access_key_id":     self._api_config.get("access_key_id", ""),
            "access_key_secret": self._api_config.get("access_key_secret", ""),
            "upload_url":        self._api_config.get("upload_url", ""),
            "result_url":        self._api_config.get("result_url", ""),
        }

    def set_api_credentials(self, app_id: str, access_key_id: str,
                            access_key_secret: str,
                            upload_url: str = "", result_url: str = ""):
        """保存 API 凭证"""
        self._api_config["app_id"] = app_id
        self._api_config["access_key_id"] = access_key_id
        self._api_config["access_key_secret"] = access_key_secret
        if upload_url:
            self._api_config["upload_url"] = upload_url
        if result_url:
            self._api_config["result_url"] = result_url
        self._save_api_config()

    def has_valid_credentials(self) -> bool:
        """检查 API 凭证是否完整"""
        creds = self.get_api_credentials()
        return bool(
            creds["app_id"]
            and creds["access_key_id"]
            and creds["access_key_secret"]
        )

    def get_api_params(self) -> dict:
        """获取转写相关的 API 参数（language, role_type, role_num 等）"""
        return {
            "language":       self._api_config.get("language", "autodialect"),
            "role_type":      self._api_config.get("role_type", 1),
            "role_num":       self._api_config.get("role_num", 0),
            "pd":             self._api_config.get("pd", ""),
            "eng_smoothproc": self._api_config.get("eng_smoothproc", True),
            "eng_colloqproc": self._api_config.get("eng_colloqproc", False),
            "duration_check_disable": self._api_config.get("duration_check_disable", False),
            "poll_interval":  self._api_config.get("poll_interval", 5),
            "max_poll_time":  self._api_config.get("max_poll_time", 3600),
            "upload_timeout": self._api_config.get("upload_timeout", 120),
            "result_timeout": self._api_config.get("result_timeout", 30),
        }

    # ------------------------------------------------------------------
    # QSettings（UI 偏好）
    # ------------------------------------------------------------------

    def get(self, key: str, default=None):
        """读取 UI 配置项（QSettings）"""
        if default is None:
            default = DEFAULT_CONFIG.get(key)
        value = self._settings.value(key, default)

        if isinstance(default, bool):
            return str(value).lower() in ("true", "1", "yes")
        elif isinstance(default, int):
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        return str(value) if value else ""

    def set(self, key: str, value):
        """写入 UI 配置项"""
        self._settings.setValue(key, value)
        self._settings.sync()
