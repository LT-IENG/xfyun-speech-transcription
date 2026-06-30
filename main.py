"""
讯飞语音转写桌面应用 — 入口模块
基于 PyQt6 + 讯飞 录音文件转写大模型 API 的播客音频转文字工具。
"""

import sys
import os

# PyInstaller 打包后资源路径解析
def resource_path(relative_path: str) -> str:
    """获取资源绝对路径，兼容开发环境和 PyInstaller 打包后的 _MEIPASS"""
    if hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


# 确保项目根目录在 Python 路径中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from src.ui.styles import setup_theme, get_font


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("讯飞语音转写")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("XfyunASR")

    # 应用图标
    icon_path = resource_path(os.path.join("assets", "p1.ico"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    app.setFont(get_font(9))
    setup_theme(app)

    def exception_hook(exc_type, exc_value, exc_tb):
        import traceback
        traceback.print_exception(exc_type, exc_value, exc_tb)
        QMessageBox.critical(
            None, "程序异常",
            f"发生未预期的错误:\n{exc_value}\n\n请查看控制台输出。"
        )
        sys.exit(1)

    sys.excepthook = exception_hook

    from src.ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
