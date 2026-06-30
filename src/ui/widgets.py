"""
自定义控件模块 — 磨砂玻璃卡片、渐变按钮、侧边栏按钮等。
封装通用动画函数 start_flash_animation()，统一驱动左侧按钮+右侧卡片闪烁。
"""

from PyQt6.QtWidgets import (
    QFrame, QPushButton, QLabel, QLineEdit, QComboBox,
    QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect,
    QSizePolicy, QWidget,
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, pyqtProperty,
)
from PyQt6.QtGui import (
    QPainter, QBrush, QColor, QPen, QFont,
)

from .styles import ThemeColors, to_qcolor, get_font


# ============================================================================
# 通用动画函数
# ============================================================================

def start_flash_animation(widget, property_name: bytes, duration_ms: int,
                          color_css: str, peak_opacity: float = 0.85):
    """
    通用控件闪烁动画 — 对 widget 的注册属性做透明度渐变。

    Args:
        widget:         目标 QWidget（需预先注册对应 pyqtProperty）
        property_name:  属性名（bytes，如 b"flashBg"）
        duration_ms:    动画时长（毫秒）
        color_css:      动画色的 CSS 字符串（rgba 格式）
        peak_opacity:   峰值透明度 0.0-1.0
    """
    anim = QPropertyAnimation(widget, property_name)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setKeyValueAt(0.25, peak_opacity)
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    # 保持引用防止被 GC
    if not hasattr(widget, '_active_anims'):
        widget._active_anims = []
    widget._active_anims.append(anim)


# ============================================================================
# 磨砂玻璃卡片（注册 cardFlash 属性 + trigger_highlight）
# ============================================================================

class GlassCard(QFrame):
    """毛玻璃卡片 — 自绘圆角背景+细边框+阴影，支持闪烁动画"""

    def __init__(self, parent=None, radius: int = 14, blur_radius: int = 25):
        super().__init__(parent)
        self._radius = radius
        self._cardFlash = 0.0
        self.setObjectName("GlassCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(blur_radius)
        self._shadow.setOffset(0, 4)
        self._update_shadow_color()
        self.setGraphicsEffect(self._shadow)

    def _update_shadow_color(self):
        self._shadow.setColor(to_qcolor(ThemeColors.SHADOW_CARD))

    def refresh_theme(self):
        self._update_shadow_color()
        self.update()

    # -- cardFlash 属性（动画驱动）--

    def _get_cardFlash(self):
        return self._cardFlash

    def _set_cardFlash(self, val):
        self._cardFlash = float(val)
        self.update()

    cardFlash = pyqtProperty(float, _get_cardFlash, _set_cardFlash)

    def trigger_highlight(self):
        """启动 250ms 淡紫背景闪烁"""
        start_flash_animation(
            self, b"cardFlash", 2000,
            ThemeColors.ANIM_FLASH_CARD, 0.85
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        # 1. 卡片背景
        bg = to_qcolor(ThemeColors.BG_CARD)
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(r, self._radius, self._radius)

        # 2. 闪烁叠加层
        if self._cardFlash > 0.005:
            overlay = to_qcolor(ThemeColors.ANIM_FLASH_CARD)
            overlay.setAlphaF(min(self._cardFlash, 1.0))
            painter.setBrush(QBrush(overlay))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(r, self._radius, self._radius)

        # 3. 细边框
        border = to_qcolor(ThemeColors.BORDER)
        pen = QPen(border)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(r.adjusted(0, 0, -1, -1),
                                self._radius, self._radius)
        painter.end()


# ============================================================================
# 渐变按钮
# ============================================================================

class GradientButton(QPushButton):
    def __init__(self, text: str = "", parent=None, icon: str = ""):
        display = f"{icon}  {text}" if icon else text
        super().__init__(display, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(get_font(12, bold=True))


# ============================================================================
# 侧边栏按钮（注册 flashBg 属性 + trigger_flash，无 checked 高亮）
# ============================================================================

class SidebarButton(QPushButton):
    """侧边栏导航按钮 — 点击瞬时 200ms 淡紫闪烁，无常驻选中"""

    def __init__(self, text: str = "", icon: str = "", parent=None):
        super().__init__(f"  {icon}   {text}", parent)
        self.setFont(get_font(12))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(False)
        self.setFlat(True)
        self.setMinimumHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setProperty("sidebarButton", True)
        self._flashBg = 0.0

    # -- flashBg 属性（动画驱动）--

    def _get_flashBg(self):
        return self._flashBg

    def _set_flashBg(self, val):
        self._flashBg = float(val)
        self.update()

    flashBg = pyqtProperty(float, _get_flashBg, _set_flashBg)

    def trigger_flash(self):
        """启动 200ms 淡紫背景闪烁 + 左侧指示条"""
        start_flash_animation(
            self, b"flashBg", 200,
            ThemeColors.ANIM_FLASH_BTN, 0.75
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        # 闪烁背景层
        if self._flashBg > 0.005:
            hl = to_qcolor(ThemeColors.ANIM_FLASH_BTN)
            hl.setAlphaF(min(self._flashBg, 1.0))
            painter.setBrush(QBrush(hl))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(r, 10, 10)

            # 左侧指示条
            bar = to_qcolor(ThemeColors.PRIMARY)
            bar.setAlphaF(self._flashBg * 0.7)
            painter.fillRect(2, 8, 3, r.height() - 16, bar)

        painter.end()
        super().paintEvent(event)


# ============================================================================
# 统一样式的输入组件
# ============================================================================

class StyledLineEdit(QLineEdit):
    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setFont(get_font(12))
        self.setMinimumHeight(38)


class StyledComboBox(QComboBox):
    def __init__(self, items: list = None, parent=None):
        super().__init__(parent)
        if items:
            self.addItems(items)
        self.setFont(get_font(12))
        self.setMinimumHeight(38)


# ============================================================================
# 标签
# ============================================================================

class SectionTitle(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setProperty("cssClass", "card-title")
        self.setFont(get_font(14, bold=True))


class HintLabel(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setProperty("cssClass", "hint")
        self.setFont(get_font(11))
        self.setWordWrap(True)


# ============================================================================
# 磨砂玻璃侧边栏
# ============================================================================

class GlassSidebar(QFrame):
    def __init__(self, parent=None, radius: int = 0):
        super().__init__(parent)
        self._radius = radius
        self.setObjectName("GlassSidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(40)
        self._shadow.setOffset(2, 0)
        self._update_shadow()
        self.setGraphicsEffect(self._shadow)

    def _update_shadow(self):
        self._shadow.setColor(to_qcolor(ThemeColors.SHADOW_SIDEBAR))

    def refresh_theme(self):
        self._update_shadow()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg = to_qcolor(ThemeColors.BG_SIDEBAR)
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), self._radius, self._radius)

        # 右侧自然色差分割线（靠底色差异，不加硬黑线）
        div = QPen(to_qcolor(ThemeColors.DIVIDER))
        div.setWidthF(1.0)
        painter.setPen(div)
        rx = self.rect().right()
        painter.drawLine(rx, 20, rx, self.rect().bottom() - 20)

        painter.end()


# ============================================================================
# 主题切换按钮
# ============================================================================

class ThemeToggleButton(QPushButton):
    def __init__(self, text: str = "", theme_key: str = "dark", parent=None):
        super().__init__(text, parent)
        self._theme_key = theme_key
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(get_font(10))
        self.setProperty("themeButton", True)
        self.setMinimumHeight(28)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_active(self, active: bool):
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


# ============================================================================
# 卡片构建辅助
# ============================================================================

def create_card(title: str, content_widget: QWidget, parent=None) -> GlassCard:
    card = GlassCard(parent)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 16, 20, 20)
    layout.setSpacing(12)
    if title:
        layout.addWidget(SectionTitle(title))
    layout.addWidget(content_widget)
    return card
