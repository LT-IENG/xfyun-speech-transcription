"""
后台工作线程模块
使用 QThread 将耗时的 API 调用（上传 + 轮询）移至后台执行。
"""

from PyQt6.QtCore import QThread, pyqtSignal

from .api_client import XfyunASRClient


class TranscriptionWorker(QThread):
    """
    语音转写后台工作线程。

    信号:
        progress(str)          — 实时进度消息
        finished(bool, list)   — (success, paragraphs)
        error(str)             — 错误消息
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, list)
    error = pyqtSignal(str)

    def __init__(
        self,
        app_id: str,
        access_key_id: str,
        access_key_secret: str,
        file_path: str,
        upload_url: str = "",
        result_url: str = "",
        language: str = "autodialect",
        role_type: int = 1,
        role_num: int = 0,
        pd: str = "",
        duration_ms: str = "",
        eng_smoothproc: bool = True,
        eng_colloqproc: bool = False,
        duration_check_disable: bool = False,
        poll_interval: int = 5,
        max_wait: int = 3600,
    ):
        super().__init__()

        self.app_id = app_id
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.file_path = file_path
        self.upload_url = upload_url
        self.result_url = result_url
        self.language = language
        self.role_type = role_type
        self.role_num = role_num
        self.pd = pd
        self.duration_ms = duration_ms
        self.eng_smoothproc = eng_smoothproc
        self.eng_colloqproc = eng_colloqproc
        self.duration_check_disable = duration_check_disable
        self.poll_interval = poll_interval
        self.max_wait = max_wait

        self._is_cancelled = False

    def cancel(self):
        """请求取消当前任务"""
        self._is_cancelled = True
        self.progress.emit("⚠️ 用户取消了转写任务")

    def run(self):
        """线程主入口"""
        try:
            self.progress.emit("🚀 正在初始化讯飞转写大模型服务...")

            client = XfyunASRClient(
                app_id=self.app_id,
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret,
                upload_url=self.upload_url or "https://office-api-ist-dx.iflyaisol.com/v2/upload",
                result_url=self.result_url or "https://office-api-ist-dx.iflyaisol.com/v2/getResult",
            )

            if self._is_cancelled:
                return

            paragraphs = client.transcribe(
                file_path=self.file_path,
                language=self.language,
                role_type=self.role_type,
                role_num=self.role_num,
                pd=self.pd,
                duration_ms=self.duration_ms,
                eng_smoothproc=self.eng_smoothproc,
                eng_colloqproc=self.eng_colloqproc,
                duration_check_disable=self.duration_check_disable,
                poll_interval=self.poll_interval,
                max_wait=self.max_wait,
                progress_callback=self._emit_progress,
            )

            if self._is_cancelled:
                return

            if paragraphs:
                self.progress.emit(f"✅ 转写完成，共识别 {len(paragraphs)} 个段落")
                self.finished.emit(True, paragraphs)
            else:
                self.error.emit("转写结果为空，请检查音频内容是否包含语音")

        except FileNotFoundError as e:
            self.error.emit(f"文件错误: {str(e)}")
        except TimeoutError as e:
            self.error.emit(f"超时: {str(e)}")
        except RuntimeError as e:
            self.error.emit(f"运行错误: {str(e)}")
        except Exception as e:
            self.error.emit(f"未知错误: {str(e)}")

    def _emit_progress(self, message: str):
        """线程安全进度发射"""
        if not self._is_cancelled:
            self.progress.emit(message)
