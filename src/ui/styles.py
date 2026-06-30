"""
全局样式表模块 — 深色/浅色双主题支持
定义配色常量、QSS 生成、主题切换逻辑。
统一字体为 Microsoft YaHei。

两套独立 QSS 文件：dark_style.qss / light_style.qss
由 apply_theme() 一次性加载完整 QSS 覆盖所有控件。
"""

import re
import os
from PyQt6.QtGui import QColor, QFont


# ============================================================================
# 深色主题色板（三层背景：主窗口 > 侧边栏 > 卡片）
# ============================================================================

DARK_PALETTE = {
    # --- 三层背景 ---
    "BG_WINDOW":        "#1e1e2f",    # 最底层 QMainWindow
    "BG_SIDEBAR":       "#27273a",    # 左侧侧边栏
    "BG_CARD":          "#2c2c40",    # 右侧卡片
    "BG_CARD_ALPHA":    "rgba(44, 44, 64, 0.90)",  # 卡片磨砂
    "BG_INPUT":         "rgba(50, 50, 72, 0.7)",
    "BG_INPUT_SOLID":   "#323248",
    "BG_HOVER":         "rgba(147, 112, 219, 0.12)",
    "BG_SELECTED":      "rgba(147, 112, 219, 0.18)",

    # --- 主色调 ---
    "PRIMARY":          "#6C63FF",
    "PRIMARY_HOVER":    "#7F78FF",
    "PRIMARY_DARK":     "#5A52D5",
    "ACCENT":           "#9D4EDD",
    "ACCENT_HOVER":     "#B066F0",

    # --- 渐变按钮 ---
    "BTN_GRADIENT_START":   "#6C63FF",
    "BTN_GRADIENT_END":     "#9D4EDD",
    "BTN_HOVER_START":      "#7F78FF",
    "BTN_HOVER_END":        "#B066F0",
    "BTN_PRESS_START":      "#5A52D5",
    "BTN_PRESS_END":        "#8A3EC0",

    # --- 文字 ---
    "TEXT_PRIMARY":     "#E8E8F0",
    "TEXT_SECONDARY":   "#A0A0B8",
    "TEXT_HINT":        "#6A6A80",
    "TEXT_DISABLED":    "rgba(232, 232, 240, 0.35)",

    # --- 边框 ---
    "BORDER":           "rgba(108, 99, 255, 0.20)",
    "BORDER_FOCUS":     "rgba(108, 99, 255, 0.55)",
    "BORDER_HOVER":     "#c0c0cc",
    "DIVIDER":          "rgba(255, 255, 255, 0.06)",

    # --- 功能色 ---
    "SUCCESS":          "#4ECB71",
    "WARNING":          "#F0A040",
    "ERROR":            "#F04864",
    "INFO":             "#4EA5F0",

    # --- 进度条 ---
    "PROGRESS_BG":      "rgba(255, 255, 255, 0.08)",
    "PROGRESS_CHUNK":   "#6C63FF",

    # --- 滚动条 ---
    "SCROLL_BG":        "rgba(255, 255, 255, 0.03)",
    "SCROLL_HANDLE":    "rgba(108, 99, 255, 0.3)",
    "SCROLL_HOVER":     "rgba(108, 99, 255, 0.5)",

    # --- 阴影 ---
    "SHADOW_CARD":      "rgba(0, 0, 0, 0.40)",
    "SHADOW_SIDEBAR":   "rgba(0, 0, 0, 0.50)",

    # --- 组件专用 ---
    "CHECKBOX_BG":          "rgba(50, 50, 72, 0.6)",
    "COMBO_DROPDOWN_BG":    "#2c2c40",
    "COMBO_ITEM_HOVER":     "rgba(147, 112, 219, 0.20)",
    "COMBO_ITEM_SELECTED":  "rgba(147, 112, 219, 0.30)",
    "TOOLTIP_BG":           "#2c2c40",
    "MENU_BG":              "#2c2c40",
    "TABLE_BG":             "rgba(44, 44, 64, 0.6)",
    "HEADER_BG":            "rgba(50, 50, 72, 0.7)",
    "SIDEBAR_BTN_TEXT":     "#A0A0B8",
    "SIDEBAR_BTN_HOVER":    "#D0D0E0",

    # --- 动画 ---
    "ANIM_FLASH_BTN":   "rgba(147, 112, 219, 0.35)",
    "ANIM_FLASH_CARD":  "rgba(147, 112, 219, 0.18)",
}

# ============================================================================
# 浅色主题色板（与深色三层一一对应）
# ============================================================================

LIGHT_PALETTE = {
    # --- 三层背景 ---
    "BG_WINDOW":        "#f5f5f9",    # 最底层 QMainWindow（消除黑色竖缝）
    "BG_SIDEBAR":       "#ebebf2",    # 左侧侧边栏（比主窗口深一阶）
    "BG_CARD":          "#ffffff",    # 右侧卡片纯白
    "BG_CARD_ALPHA":    "rgba(255, 255, 255, 0.92)",
    "BG_INPUT":         "rgba(248, 248, 252, 0.85)",
    "BG_INPUT_SOLID":   "#f8f8fc",
    "BG_HOVER":         "rgba(147, 112, 219, 0.08)",
    "BG_SELECTED":      "rgba(147, 112, 219, 0.14)",

    # --- 主色调（#9370db 浅紫，和深色紫色系同源）---
    "PRIMARY":          "#9370db",
    "PRIMARY_HOVER":    "#a78ae8",
    "PRIMARY_DARK":     "#7d5ac0",
    "ACCENT":           "#b088e8",
    "ACCENT_HOVER":     "#c4a4f2",

    # --- 渐变按钮 ---
    "BTN_GRADIENT_START":   "#9370db",
    "BTN_GRADIENT_END":     "#b088e8",
    "BTN_HOVER_START":      "#a78ae8",
    "BTN_HOVER_END":        "#c4a4f2",
    "BTN_PRESS_START":      "#7d5ac0",
    "BTN_PRESS_END":        "#9e70d8",

    # --- 文字 ---
    "TEXT_PRIMARY":     "#222226",
    "TEXT_SECONDARY":   "#44444c",
    "TEXT_HINT":        "#888892",
    "TEXT_DISABLED":    "rgba(68, 68, 76, 0.35)",

    # --- 边框 ---
    "BORDER":           "#dcdce6",
    "BORDER_FOCUS":     "rgba(147, 112, 219, 0.55)",
    "BORDER_HOVER":     "#c0c0cc",
    "DIVIDER":          "rgba(0, 0, 0, 0.06)",

    # --- 功能色 ---
    "SUCCESS":          "#3CB878",
    "WARNING":          "#E8963C",
    "ERROR":            "#E05555",
    "INFO":             "#4A90D9",

    # --- 进度条 ---
    "PROGRESS_BG":      "rgba(0, 0, 0, 0.05)",
    "PROGRESS_CHUNK":   "#9370db",

    # --- 滚动条 ---
    "SCROLL_BG":        "rgba(0, 0, 0, 0.04)",
    "SCROLL_HANDLE":    "rgba(147, 112, 219, 0.22)",
    "SCROLL_HOVER":     "rgba(147, 112, 219, 0.40)",

    # --- 阴影 ---
    "SHADOW_CARD":      "rgba(0, 0, 0, 0.06)",
    "SHADOW_SIDEBAR":   "rgba(0, 0, 0, 0.04)",

    # --- 组件专用 ---
    "CHECKBOX_BG":          "rgba(248, 248, 252, 0.7)",
    "COMBO_DROPDOWN_BG":    "#ffffff",
    "COMBO_ITEM_HOVER":     "rgba(147, 112, 219, 0.10)",
    "COMBO_ITEM_SELECTED":  "rgba(147, 112, 219, 0.18)",
    "TOOLTIP_BG":           "#ffffff",
    "MENU_BG":              "#ffffff",
    "TABLE_BG":             "rgba(255, 255, 255, 0.6)",
    "HEADER_BG":            "rgba(245, 245, 249, 0.8)",
    "SIDEBAR_BTN_TEXT":     "#44444c",
    "SIDEBAR_BTN_HOVER":    "#222226",

    # --- 动画（浅色降低透明度避免刺眼）---
    "ANIM_FLASH_BTN":   "rgba(147, 112, 219, 0.22)",
    "ANIM_FLASH_CARD":  "rgba(147, 112, 219, 0.12)",
}


# ============================================================================
# 动态主题色
# ============================================================================

class ThemeColors:
    """主题色命名空间"""
    pass


_current_theme = "dark"


def _apply_palette(palette: dict):
    for key, val in palette.items():
        setattr(ThemeColors, key, val)


_apply_palette(DARK_PALETTE)


def get_current_theme() -> str:
    return _current_theme


# ============================================================================
# 工具
# ============================================================================

def to_qcolor(css_color: str) -> QColor:
    if "rgba" in css_color:
        nums = re.findall(r'\d+\.?\d*', css_color)
        if len(nums) == 4:
            return QColor(int(nums[0]), int(nums[1]), int(nums[2]),
                          int(float(nums[3]) * 255))
        elif len(nums) == 3:
            return QColor(int(nums[0]), int(nums[1]), int(nums[2]))
    return QColor(css_color)


def get_font(size: int = 9, bold: bool = False) -> QFont:
    font = QFont("Microsoft YaHei", size)
    font.setBold(bold)
    return font


# ============================================================================
# QSS 生成（统一模板，p=palette，覆盖所有控件+三层背景）
# ============================================================================

def _generate_qss(p: dict) -> str:
    return f"""
/* ============================================================
   三层背景体系（消除中间竖缝 — 全部显式赋值）
   ============================================================ */

/* 第1层: QMainWindow 底层 */
QMainWindow {{
    background-color: {p["BG_WINDOW"]};
    color: {p["TEXT_PRIMARY"]};
    font-family: "Microsoft YaHei";
    font-size: 13px;
}}

/* 中央容器透明 — 由左右子控件各自着色 */
QMainWindow > QWidget#centralWidget {{
    background-color: {p["BG_WINDOW"]};
}}

/* QScrollArea 背景透出主窗口色 */
QScrollArea {{
    background-color: {p["BG_WINDOW"]};
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: {p["BG_WINDOW"]};
}}

QScrollArea > QWidget#qt_scrollarea_viewport {{
    background-color: {p["BG_WINDOW"]};
}}

/* 全局 Widget 默认透明 */
QWidget {{
    font-family: "Microsoft YaHei";
    color: {p["TEXT_PRIMARY"]};
    background-color: transparent;
    outline: none;
}}

/* 第2层: 玻璃侧边栏 — 由 paintEvent 自绘，此处只做兜底 */
QFrame#GlassSidebar {{
    background-color: {p["BG_SIDEBAR"]};
}}

/* 第3层: 卡片 — 由 GlassCard paintEvent 自绘，此处兜底 */
QFrame#GlassCard {{
    background-color: {p["BG_CARD"]};
}}

/* --- 输入框 --- */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {p["BG_INPUT"]};
    border: 1.5px solid {p["BORDER"]};
    border-radius: 8px;
    padding: 8px 12px;
    color: {p["TEXT_PRIMARY"]};
    font-size: 13px;
    selection-background-color: {p["PRIMARY"]};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {p["BORDER_FOCUS"]}; }}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{ border-color: {p["BORDER_HOVER"]}; }}

/* --- 下拉框 --- */
QComboBox {{
    background-color: {p["BG_INPUT"]};
    border: 1.5px solid {p["BORDER"]};
    border-radius: 8px;
    padding: 8px 12px;
    padding-right: 30px;
    color: {p["TEXT_PRIMARY"]};
    font-size: 13px;
    min-height: 20px;
}}
QComboBox:hover {{ border-color: {p["BORDER_HOVER"]}; }}
QComboBox:focus, QComboBox:on {{ border-color: {p["BORDER_FOCUS"]}; }}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid {p["BORDER"]};
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {p["COMBO_DROPDOWN_BG"]};
    border: 1px solid {p["BORDER"]};
    border-radius: 6px;
    padding: 4px;
    color: {p["TEXT_PRIMARY"]};
    selection-background-color: {p["COMBO_ITEM_SELECTED"]};
    selection-color: {p["TEXT_PRIMARY"]};
    outline: none;
}}
QComboBox QAbstractItemView::item {{ padding: 6px 12px; border-radius: 4px; min-height: 24px; }}
QComboBox QAbstractItemView::item:hover {{ background-color: {p["COMBO_ITEM_HOVER"]}; }}

/* --- 主按钮 --- */
QPushButton {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p["BTN_GRADIENT_START"]}, stop:1 {p["BTN_GRADIENT_END"]});
    color: #FFFFFF;
    border: none;
    border-radius: 12px;
    padding: 10px 24px;
    font-size: 13px;
    font-weight: bold;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p["BTN_HOVER_START"]}, stop:1 {p["BTN_HOVER_END"]});
}}
QPushButton:pressed {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p["BTN_PRESS_START"]}, stop:1 {p["BTN_PRESS_END"]});
    padding-top: 11px;
    padding-bottom: 9px;
}}
QPushButton:disabled {{
    background-color: {p["BG_HOVER"]};
    color: {p["TEXT_DISABLED"]};
}}

/* --- 次要按钮 --- */
QPushButton[cssClass="secondary"] {{
    background-color: transparent;
    border: 1.5px solid {p["BORDER_HOVER"]};
    color: {p["TEXT_SECONDARY"]};
    font-weight: normal;
}}
QPushButton[cssClass="secondary"]:hover {{
    background-color: {p["BG_HOVER"]};
    border-color: {p["BORDER_FOCUS"]};
    color: {p["TEXT_PRIMARY"]};
}}

/* --- 危险按钮 --- */
QPushButton[cssClass="danger"] {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F04864, stop:1 #D03050);
}}
QPushButton[cssClass="danger"]:hover {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F06080, stop:1 #E04060);
}}

/* --- 侧边栏按钮（禁止 checked 高亮）--- */
QPushButton[sidebarButton="true"] {{
    background-color: transparent;
    color: {p["SIDEBAR_BTN_TEXT"]};
    border: none;
    border-radius: 10px;
    text-align: left;
    padding: 10px 16px;
    font-weight: normal;
    font-size: 13px;
}}
QPushButton[sidebarButton="true"]:hover {{
    background-color: {p["BG_HOVER"]};
    color: {p["SIDEBAR_BTN_HOVER"]};
}}
QPushButton[sidebarButton="true"]:checked {{
    background-color: transparent;
    color: {p["SIDEBAR_BTN_TEXT"]};
    border: none;
}}

/* --- 主题切换按钮 --- */
QPushButton[themeButton="true"] {{
    background-color: {p["BG_HOVER"]};
    color: {p["TEXT_SECONDARY"]};
    border: 1px solid {p["BORDER"]};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: normal;
}}
QPushButton[themeButton="true"]:hover {{
    background-color: {p["BG_SELECTED"]};
    color: {p["TEXT_PRIMARY"]};
    border-color: {p["PRIMARY"]};
}}
QPushButton[themeButton="true"][active="true"] {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p["BTN_GRADIENT_START"]}, stop:1 {p["BTN_GRADIENT_END"]});
    color: #FFFFFF;
    border-color: transparent;
}}

/* --- 复选框 & 单选框 --- */
QCheckBox, QRadioButton {{
    color: {p["TEXT_PRIMARY"]};
    font-size: 13px;
    spacing: 8px;
    padding: 4px 0;
}}
QCheckBox::indicator {{
    width: 18px; height: 18px; border-radius: 4px;
    border: 1.5px solid {p["BORDER_HOVER"]};
    background-color: {p["CHECKBOX_BG"]};
}}
QCheckBox::indicator:hover {{ border-color: {p["BORDER_FOCUS"]}; }}
QCheckBox::indicator:checked {{ background-color: {p["PRIMARY"]}; border-color: {p["PRIMARY"]}; }}
QRadioButton::indicator {{
    width: 18px; height: 18px; border-radius: 10px;
    border: 1.5px solid {p["BORDER_HOVER"]};
    background-color: {p["CHECKBOX_BG"]};
}}
QRadioButton::indicator:hover {{ border-color: {p["BORDER_FOCUS"]}; }}
QRadioButton::indicator:checked {{ background-color: {p["PRIMARY"]}; border-color: {p["PRIMARY"]}; }}

/* --- 进度条 --- */
QProgressBar {{
    background-color: {p["PROGRESS_BG"]};
    border: none; border-radius: 6px; height: 12px;
    text-align: center; color: {p["TEXT_PRIMARY"]}; font-size: 11px;
}}
QProgressBar::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {p["PRIMARY"]}, stop:1 {p["ACCENT"]});
    border-radius: 6px;
}}

/* --- 滚动条 --- */
QScrollBar:vertical {{
    background-color: {p["SCROLL_BG"]};
    width: 8px; border-radius: 4px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background-color: {p["SCROLL_HANDLE"]};
    border-radius: 4px; min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background-color: {p["SCROLL_HOVER"]}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0; background: none; border: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{
    background-color: {p["SCROLL_BG"]};
    height: 8px; border-radius: 4px; margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background-color: {p["SCROLL_HANDLE"]};
    border-radius: 4px; min-width: 40px;
}}
QScrollBar::handle:horizontal:hover {{ background-color: {p["SCROLL_HOVER"]}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0; background: none; border: none;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

/* --- 标签 --- */
QLabel {{
    color: {p["TEXT_PRIMARY"]};
    background-color: transparent;
    font-size: 13px;
}}
QLabel[cssClass="title"]      {{ font-size: 20px; font-weight: bold; color: {p["TEXT_PRIMARY"]}; }}
QLabel[cssClass="subtitle"]   {{ font-size: 14px; font-weight: bold; color: {p["TEXT_SECONDARY"]}; }}
QLabel[cssClass="hint"]       {{ font-size: 12px; color: {p["TEXT_HINT"]}; }}
QLabel[cssClass="card-title"] {{ font-size: 15px; font-weight: bold; color: {p["TEXT_PRIMARY"]}; }}

/* --- 分组框 --- */
QGroupBox {{
    border: 1px solid {p["BORDER"]};
    border-radius: 10px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
    color: {p["TEXT_SECONDARY"]};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 10px;
    color: {p["TEXT_SECONDARY"]};
}}

/* --- 滑块 --- */
QSlider::groove:horizontal {{
    background-color: {p["PROGRESS_BG"]};
    height: 4px; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background-color: {p["PRIMARY"]};
    border: 2px solid {p["ACCENT"]};
    width: 16px; height: 16px; margin: -6px 0; border-radius: 9px;
}}
QSlider::handle:horizontal:hover {{
    background-color: {p["PRIMARY_HOVER"]};
    border-color: {p["ACCENT_HOVER"]};
}}

/* --- 分割线 --- */
QSplitter::handle {{ background-color: {p["BORDER"]}; margin: 0 2px; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical   {{ height: 2px; }}

/* --- 工具提示 --- */
QToolTip {{
    background-color: {p["TOOLTIP_BG"]};
    color: {p["TEXT_PRIMARY"]};
    border: 1px solid {p["BORDER"]};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* --- 菜单 --- */
QMenu {{
    background-color: {p["MENU_BG"]};
    border: 1px solid {p["BORDER"]};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{ padding: 8px 24px; border-radius: 4px; }}
QMenu::item:selected {{ background-color: {p["COMBO_ITEM_SELECTED"]}; }}
QMenu::separator {{ height: 1px; background-color: {p["DIVIDER"]}; margin: 4px 8px; }}

/* --- 表格 --- */
QTableWidget, QTableView {{
    background-color: {p["TABLE_BG"]};
    border: 1px solid {p["BORDER"]};
    border-radius: 8px;
    gridline-color: {p["DIVIDER"]};
    selection-background-color: {p["COMBO_ITEM_SELECTED"]};
    selection-color: {p["TEXT_PRIMARY"]};
}}
QHeaderView::section {{
    background-color: {p["HEADER_BG"]};
    padding: 8px; border: none;
    border-bottom: 1px solid {p["BORDER"]};
    font-weight: bold; color: {p["TEXT_SECONDARY"]};
}}

/* --- SpinBox / TimeEdit --- */
QSpinBox, QDoubleSpinBox, QTimeEdit {{
    background-color: {p["BG_INPUT"]};
    border: 1.5px solid {p["BORDER"]};
    border-radius: 8px;
    padding: 6px 10px;
    color: {p["TEXT_PRIMARY"]};
    font-size: 13px;
}}
QSpinBox:hover, QDoubleSpinBox:hover, QTimeEdit:hover {{ border-color: {p["BORDER_HOVER"]}; }}
QSpinBox:focus, QDoubleSpinBox:focus, QTimeEdit:focus {{ border-color: {p["BORDER_FOCUS"]}; }}

/* --- 对话框 --- */
QDialog {{
    background-color: {p["BG_WINDOW"]};
    border: 1px solid {p["BORDER"]};
    border-radius: 12px;
}}
QMessageBox {{ background-color: {p["BG_WINDOW"]}; }}
QFileDialog  {{ background-color: {p["BG_WINDOW"]}; }}
"""


# ============================================================================
# 生成 QSS 并写入独立文件
# ============================================================================

_QSS_DIR = os.path.dirname(os.path.abspath(__file__))

DARK_QSS = _generate_qss(DARK_PALETTE)
LIGHT_QSS = _generate_qss(LIGHT_PALETTE)

# 写入 QSS 文件供调试（PyInstaller 环境下跳过 — 只读文件系统）
_QSS_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(_QSS_DIR, "dark_style.qss"), "w", encoding="utf-8") as _f:
        _f.write(DARK_QSS)
    with open(os.path.join(_QSS_DIR, "light_style.qss"), "w", encoding="utf-8") as _f:
        _f.write(LIGHT_QSS)
except OSError:
    pass  # PyInstaller 只读环境，跳过文件写入

GLOBAL_STYLESHEET = DARK_QSS


# ============================================================================
# 主题切换
# ============================================================================

def apply_theme(app, theme_name: str):
    """
    一次性给 QMainWindow 加载完整 QSS，覆盖三层背景+所有控件。
    """
    global _current_theme, GLOBAL_STYLESHEET

    theme_name = theme_name.lower()
    if theme_name not in ("dark", "light"):
        theme_name = "dark"

    if theme_name == "dark":
        _apply_palette(DARK_PALETTE)
        GLOBAL_STYLESHEET = DARK_QSS
    else:
        _apply_palette(LIGHT_PALETTE)
        GLOBAL_STYLESHEET = LIGHT_QSS

    _current_theme = theme_name
    app.setStyleSheet(GLOBAL_STYLESHEET)


def setup_theme(app):
    apply_theme(app, "dark")
