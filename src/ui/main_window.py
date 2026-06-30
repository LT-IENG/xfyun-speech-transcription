"""
主窗口模块
构建应用的整体布局：左侧磨砂玻璃侧边栏 + 右侧卡片式主内容区。
整合所有子组件（音频选择、转写设置含时间范围+说话人分离+领域优化、进度结果）。
支持深浅主题实时切换、侧边栏瞬时高亮导航、自动/手动说话人识别。
"""

import os
import random
import tempfile

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QScrollArea, QFrame, QFileDialog, QMessageBox,
    QRadioButton, QButtonGroup, QLabel, QTextEdit,
    QProgressBar, QSlider, QTimeEdit, QSpinBox,
    QSizePolicy, QSpacerItem, QDialog, QDialogButtonBox,
    QFormLayout, QLineEdit, QApplication, QCheckBox,
)
from PyQt6.QtCore import Qt, QTime, QTimer
from PyQt6.QtGui import QAction, QIcon

from ..config import ConfigManager
from ..api_client import XfyunASRClient, DOMAIN_MAP
from ..audio_utils import (
    get_audio_duration, get_audio_info,
    extract_segment, hms_to_sec, cleanup_temp_file,
)
from ..worker import TranscriptionWorker
from .styles import ThemeColors, get_font, apply_theme, get_current_theme
from .widgets import (
    GlassCard, GradientButton, SidebarButton,
    StyledLineEdit, StyledComboBox,
    SectionTitle, HintLabel, GlassSidebar, create_card,
    ThemeToggleButton,
)


class MainWindow(QMainWindow):
    """
    应用主窗口。

    布局结构:
        ┌─────────────────────────────────────────┐
        │ [GlassSidebar] │ [QScrollArea: 卡片列表] │
        │                │                         │
        │  📁 选择文件    │  ■ 音频信息             │
        │  ⚙️ API设置     │  ■ 转写设置             │
        │  🎯 转写设置    │    (时间范围+说话人     │
        │  📝 转写结果    │     +领域优化合并)      │
        │                │  ■ 进度与结果           │
        │  ▶️ 开始转写    │                         │
        │ [浅色][深色]    │                         │
        └─────────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__()

        # 配置管理器
        self.config = ConfigManager()

        # 状态变量
        self._audio_file_path: str = ""
        self._audio_duration: float = 0.0
        self._temp_segment_path: str = ""
        self._segment_start_sec: float = 0.0
        self._segment_end_sec: float = 0.0
        self._transcription_result: list = []
        self._worker: TranscriptionWorker = None

        # 窗口基本设置
        self.setWindowTitle("讯飞语音转写 — 播客音频转文字工具")
        self.setMinimumSize(1100, 720)
        self.resize(1200, 800)

        # 窗口图标（由 main.py 统一设置）

        # 构建 UI
        self._build_central_widget()
        self._build_sidebar()
        self._build_main_content()
        self._connect_signals()

        # 加载保存的配置（主题 + API 凭据）
        self._load_saved_settings()

    # ==================================================================
    # 中央布局
    # ==================================================================

    def _build_central_widget(self):
        """创建中央容器（设置 objectName 供 QSS 三层背景精准覆盖）"""
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        self._main_layout = QHBoxLayout(central)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

    # ==================================================================
    # 侧边栏
    # ==================================================================

    def _build_sidebar(self):
        """构建左侧毛玻璃侧边栏（含导航按钮 + 主题切换）"""
        sidebar = GlassSidebar(radius=0)
        sidebar.setFixedWidth(240)
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._sidebar = sidebar  # 保存引用供主题切换

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 20)
        layout.setSpacing(6)

        # Logo（保存引用供主题切换更新）
        self._logo_label = QLabel("🎙️ 讯飞语音转写")
        self._logo_label.setFont(get_font(16, bold=True))
        self._logo_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_PRIMARY}; padding: 8px 0 20px 8px;"
        )
        layout.addWidget(self._logo_label)

        # 导航按钮（不锁定选中态）
        self._sidebar_btns = {}
        nav_items = [
            ("select_file",           "📁", "选择文件"),
            ("api_settings",          "⚙️", "API 设置"),
            ("transcribe_settings",   "🎯", "转写设置"),
            ("results",               "📝", "转写结果"),
        ]
        for key, icon, text in nav_items:
            btn = SidebarButton(text=text, icon=icon)
            layout.addWidget(btn)
            self._sidebar_btns[key] = btn

        layout.addSpacing(16)

        # 开始转写
        self._start_btn = GradientButton("开始转写", icon="▶️")
        self._start_btn.setMinimumHeight(48)
        self._start_btn.setEnabled(False)
        layout.addWidget(self._start_btn)

        layout.addStretch()

        # --- 主题切换按钮组（侧边栏底部）---
        self._theme_label = QLabel("主题模式")
        self._theme_label.setFont(get_font(10))
        self._theme_label.setStyleSheet(f"color: {ThemeColors.TEXT_HINT}; padding-left: 4px;")
        layout.addWidget(self._theme_label)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(6)
        theme_row.setContentsMargins(0, 4, 0, 8)

        self._light_btn = ThemeToggleButton("☀️ 浅色", theme_key="light")
        self._dark_btn  = ThemeToggleButton("🌙 深色", theme_key="dark")

        theme_row.addWidget(self._light_btn)
        theme_row.addWidget(self._dark_btn)
        layout.addLayout(theme_row)

        # 版本信息
        version_label = HintLabel("v2.6.0 · 基于讯飞开放平台")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        self._main_layout.addWidget(sidebar)

    # ==================================================================
    # 主内容区
    # ==================================================================

    def _build_main_content(self):
        """构建右侧可滚动卡片区域"""
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setObjectName("mainContent")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(24, 20, 24, 24)
        self._content_layout.setSpacing(18)

        # 卡片1: 音频信息
        self._build_audio_info_card()

        # 卡片2: 转写设置（合并时间范围 + 说话人 + 领域）
        self._build_transcribe_settings_card()

        # 卡片3: 进度与结果
        self._build_progress_result_card()

        self._content_layout.addStretch()

        self._scroll_area.setWidget(content)
        self._main_layout.addWidget(self._scroll_area, 1)

    # ------------------------------------------------------------------
    # 卡片1: 音频信息
    # ------------------------------------------------------------------

    def _build_audio_info_card(self):
        """构建音频文件信息卡片"""
        card_content = QWidget()
        layout = QVBoxLayout(card_content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 文件选择行
        file_row = QHBoxLayout()
        file_row.setSpacing(10)

        self._file_path_edit = StyledLineEdit("请选择播客音频文件...")
        self._file_path_edit.setReadOnly(True)
        self._file_path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        file_row.addWidget(self._file_path_edit, 1)

        browse_btn = GradientButton("浏览文件", icon="📂")
        browse_btn.setFixedWidth(120)
        browse_btn.setProperty("cssClass", "secondary")
        file_row.addWidget(browse_btn)
        browse_btn.clicked.connect(self._on_browse_file)

        layout.addLayout(file_row)

        # 信息标签行
        info_row = QHBoxLayout()
        info_row.setSpacing(20)

        self._info_duration = HintLabel("时长: --")
        self._info_format   = HintLabel("格式: --")
        self._info_size     = HintLabel("大小: --")
        self._info_sample   = HintLabel("采样率: --")

        for lbl in [self._info_duration, self._info_format, self._info_size, self._info_sample]:
            info_row.addWidget(lbl)

        info_row.addStretch()
        layout.addLayout(info_row)

        self._audio_info_card = create_card("📁 音频文件", card_content)
        self._content_layout.addWidget(self._audio_info_card)

    # ------------------------------------------------------------------
    # 卡片2: 转写设置（时间范围 + 说话人分离 + 领域优化 统一面板）
    # ------------------------------------------------------------------

    def _build_transcribe_settings_card(self):
        """构建转写设置卡片 — 合并时间范围选择、说话人分离、领域优化"""
        card_content = QWidget()
        layout = QVBoxLayout(card_content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # ===== 分区 A: 时间范围 =====
        section_a = QWidget()
        sec_a_layout = QVBoxLayout(section_a)
        sec_a_layout.setContentsMargins(0, 0, 0, 0)
        sec_a_layout.setSpacing(8)

        sec_a_label = QLabel("⏱️ 时间范围")
        sec_a_label.setFont(get_font(12, bold=True))
        sec_a_layout.addWidget(sec_a_label)

        # 单选按钮行
        radio_row = QHBoxLayout()
        radio_row.setSpacing(20)

        self._radio_group = QButtonGroup(self)
        radio_options = [
            ("all",    "全部音频"),
            ("custom", "自定义时间段"),
        ]
        for key, label in radio_options:
            rb = QRadioButton(label)
            rb.setFont(get_font(12))
            self._radio_group.addButton(rb, radio_options.index((key, label)))
            radio_row.addWidget(rb)
            if key == "all":
                rb.setChecked(True)

        radio_row.addStretch()
        sec_a_layout.addLayout(radio_row)

        # 自定义时间行
        self._custom_range_widget = QWidget()
        custom_layout = QHBoxLayout(self._custom_range_widget)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(10)

        custom_layout.addWidget(QLabel("起始:"))
        self._time_start = QTimeEdit()
        self._time_start.setDisplayFormat("HH:mm:ss")
        self._time_start.setTime(QTime(0, 0, 0))
        self._time_start.setMinimumWidth(110)
        custom_layout.addWidget(self._time_start)

        custom_layout.addWidget(QLabel("结束:"))
        self._time_end = QTimeEdit()
        self._time_end.setDisplayFormat("HH:mm:ss")
        self._time_end.setTime(QTime(0, 1, 0))
        self._time_end.setMinimumWidth(110)
        custom_layout.addWidget(self._time_end)

        custom_layout.addStretch()
        self._custom_range_widget.setVisible(False)
        sec_a_layout.addWidget(self._custom_range_widget)

        layout.addWidget(section_a)

        # 分割线
        div_a = QFrame()
        div_a.setFrameShape(QFrame.Shape.HLine)
        div_a.setStyleSheet(f"QFrame {{ color: {ThemeColors.DIVIDER}; max-height: 1px; }}")
        layout.addWidget(div_a)

        # ===== 分区 B: 说话人分离 + 领域优化 =====
        section_b = QWidget()
        sec_b_layout = QVBoxLayout(section_b)
        sec_b_layout.setContentsMargins(0, 0, 0, 0)
        sec_b_layout.setSpacing(10)

        sec_b_label = QLabel("👥 语音识别参数")
        sec_b_label.setFont(get_font(12, bold=True))
        sec_b_layout.addWidget(sec_b_label)

        param_row = QHBoxLayout()
        param_row.setSpacing(20)

        # 自动识别说话人数开关
        self._auto_speaker_cb = QCheckBox("自动识别说话人数")
        self._auto_speaker_cb.setFont(get_font(12))
        self._auto_speaker_cb.setChecked(self.config.get("auto_speaker", True))
        self._auto_speaker_cb.setToolTip(
            "开启后由讯飞 ASR 模型自动分析音频中的说话人数量\n"
            "关闭后可手动指定人数（1-10）"
        )
        param_row.addWidget(self._auto_speaker_cb)

        # 手动人数输入（仅自动模式关闭时可见）
        self._manual_speaker_widget = QWidget()
        manual_layout = QHBoxLayout(self._manual_speaker_widget)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(6)

        manual_layout.addWidget(QLabel("人数:"))
        self._role_num_spin = QSpinBox()
        self._role_num_spin.setRange(1, 10)
        self._role_num_spin.setValue(max(1, self.config.get("role_num", 2)))
        self._role_num_spin.setMinimumWidth(65)
        self._role_num_spin.setToolTip("手动指定音频中的说话人总数")
        manual_layout.addWidget(self._role_num_spin)

        self._manual_speaker_widget.setVisible(not self._auto_speaker_cb.isChecked())
        param_row.addWidget(self._manual_speaker_widget)

        param_row.addSpacing(20)

        # 领域优化
        param_row.addWidget(QLabel("领域优化:"))
        self._domain_combo = StyledComboBox(list(DOMAIN_MAP.keys()))
        idx = list(DOMAIN_MAP.keys()).index(
            self._get_domain_key(self.config.get("pd", ""))
        )
        self._domain_combo.setCurrentIndex(idx)
        self._domain_combo.setMinimumWidth(120)
        self._domain_combo.setToolTip("选择音频所属领域可提升识别准确率")
        param_row.addWidget(self._domain_combo)

        param_row.addStretch()
        sec_b_layout.addLayout(param_row)

        layout.addWidget(section_b)

        self._transcribe_settings_card = create_card("🎯 转写设置", card_content)
        self._content_layout.addWidget(self._transcribe_settings_card)

        # 自动/手动切换信号
        self._auto_speaker_cb.toggled.connect(self._on_auto_speaker_toggled)
        # 时间范围信号
        self._radio_group.buttonClicked.connect(self._on_range_mode_changed)

    # ------------------------------------------------------------------
    # 卡片3: 进度与结果
    # ------------------------------------------------------------------

    def _build_progress_result_card(self):
        """构建进度与结果展示卡片"""
        card_content = QWidget()
        layout = QVBoxLayout(card_content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(10)
        layout.addWidget(self._progress_bar)

        # 状态日志
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(120)
        self._log_text.setPlaceholderText("转写进度日志将在此显示...")
        layout.addWidget(self._log_text)

        # 结果预览
        self._result_preview = QTextEdit()
        self._result_preview.setReadOnly(True)
        self._result_preview.setMinimumHeight(180)
        self._result_preview.setPlaceholderText("转写结果将在此预览显示...")
        layout.addWidget(self._result_preview)

        # 操作按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._export_btn = GradientButton("导出 TXT", icon="💾")
        self._export_btn.setEnabled(False)
        self._export_btn.setFixedWidth(140)
        btn_row.addWidget(self._export_btn)

        self._copy_btn = GradientButton("复制全部", icon="📋")
        self._copy_btn.setEnabled(False)
        self._copy_btn.setProperty("cssClass", "secondary")
        self._copy_btn.setFixedWidth(130)
        btn_row.addWidget(self._copy_btn)

        self._clear_btn = GradientButton("清除结果", icon="🗑️")
        self._clear_btn.setEnabled(False)
        self._clear_btn.setProperty("cssClass", "secondary")
        self._clear_btn.setFixedWidth(130)
        btn_row.addWidget(self._clear_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._progress_result_card = create_card("📊 转写进度与结果", card_content)
        self._content_layout.addWidget(self._progress_result_card)

    # ==================================================================
    # 信号连接
    # ==================================================================

    def _connect_signals(self):
        """连接所有信号和槽"""
        # 开始转写
        self._start_btn.clicked.connect(self._on_start_transcribe)

        # 导出 / 复制 / 清除
        self._export_btn.clicked.connect(self._on_export_txt)
        self._copy_btn.clicked.connect(self._on_copy_result)
        self._clear_btn.clicked.connect(self._on_clear_result)

        # 侧边栏导航：瞬时高亮 + 跳转 + 卡片闪烁
        self._sidebar_btns["select_file"].clicked.connect(
            lambda: self._navigate_to(self._audio_info_card, self._sidebar_btns["select_file"])
        )
        self._sidebar_btns["api_settings"].clicked.connect(
            lambda: self._navigate_to_api_settings(self._sidebar_btns["api_settings"])
        )
        self._sidebar_btns["transcribe_settings"].clicked.connect(
            lambda: self._navigate_to(self._transcribe_settings_card, self._sidebar_btns["transcribe_settings"])
        )
        self._sidebar_btns["results"].clicked.connect(
            lambda: self._navigate_to(self._progress_result_card, self._sidebar_btns["results"])
        )

        # 主题切换按钮
        self._light_btn.clicked.connect(lambda: self._switch_theme("light"))
        self._dark_btn.clicked.connect(lambda: self._switch_theme("dark"))

    # ==================================================================
    # 侧边栏导航逻辑（重制版：瞬时高亮 + 跳转 + 卡片闪烁）
    # ==================================================================

    def _navigate_to(self, card: GlassCard, sidebar_btn: SidebarButton):
        """
        导航:
        1. 按钮瞬时闪烁
        2. 滚动到目标卡片
        3. 延迟 10ms 启动卡片闪烁（确保页面已切换到位）
        """
        sidebar_btn.trigger_flash()
        self._scroll_to_card(card)
        # 延迟启动，避免动画作用在切换前的旧页面上
        QTimer.singleShot(10, card.trigger_highlight)

    def _navigate_to_api_settings(self, sidebar_btn: SidebarButton):
        """导航到 API 设置（弹窗）"""
        sidebar_btn.trigger_flash()
        self._on_open_api_settings()

    # ==================================================================
    # 主题切换
    # ==================================================================

    def _switch_theme(self, theme_name: str):
        """
        切换全局深浅主题。

        流程：
        1. 更新全局 QSS
        2. 更新 ThemeColors 类属性
        3. 刷新所有自绘控件（GlassCard、GlassSidebar）
        4. 更新主题切换按钮的 active 状态
        5. 持久化保存选择
        """
        app = QApplication.instance()

        # 应用新主题
        apply_theme(app, theme_name)

        # 刷新侧边栏
        if hasattr(self, '_sidebar'):
            self._sidebar.refresh_theme()

        # 刷新所有 GlassCard
        for card in self._collect_glass_cards():
            card.refresh_theme()

        # 更新主题按钮状态
        self._light_btn.set_active(theme_name == "light")
        self._dark_btn.set_active(theme_name == "dark")

        # 更新侧边栏中固定颜色的标签
        self._update_sidebar_labels()

        # 持久化
        self.config.set("theme", theme_name)

    def _collect_glass_cards(self) -> list:
        """收集内容区域中的所有 GlassCard 实例"""
        cards = []
        for i in range(self._content_layout.count()):
            item = self._content_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, GlassCard):
                    cards.append(w)
        return cards

    def _update_sidebar_labels(self):
        """主题切换后更新侧边栏中内联样式的标签颜色"""
        if hasattr(self, '_logo_label'):
            self._logo_label.setStyleSheet(
                f"color: {ThemeColors.TEXT_PRIMARY}; padding: 8px 0 20px 8px;"
            )
        if hasattr(self, '_theme_label'):
            self._theme_label.setStyleSheet(
                f"color: {ThemeColors.TEXT_HINT}; padding-left: 4px;"
            )

    # ==================================================================
    # 槽函数 — 文件选择
    # ==================================================================

    def _on_browse_file(self):
        """浏览并选择音频文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择播客音频文件",
            "",
            "音频文件 (*.mp3 *.wav *.m4a *.flac *.ogg *.aac *.opus *.wma *.amr);;所有文件 (*.*)"
        )
        if not file_path:
            return

        try:
            info = get_audio_info(file_path)
            self._audio_file_path = file_path
            self._audio_duration = info["duration_sec"]

            self._file_path_edit.setText(file_path)
            self._info_duration.setText(f"时长: {info['duration_str']}")
            self._info_format.setText(f"格式: {info['format']}")
            self._info_size.setText(f"大小: {info['size_mb']} MB")
            self._info_sample.setText(f"采样率: {info['sample_rate']} Hz · {info['channels']}ch")

            # 更新自定义时间范围最大值
            max_sec = int(self._audio_duration)
            max_time = QTime(max_sec // 3600, (max_sec % 3600) // 60, max_sec % 60)
            self._time_end.setMaximumTime(max_time)
            self._time_end.setTime(
                max_time if max_sec < 60
                else QTime(0, min(1, max_sec // 60), 0)
            )
            self._time_start.setMaximumTime(max_time)

            self._update_start_button_state()
            self._on_clear_result()
            self._log(f"✅ 已加载音频: {info['file_name']} ({info['duration_str']})")

        except FileNotFoundError:
            QMessageBox.warning(self, "文件错误", "找不到所选文件")
        except Exception as e:
            QMessageBox.warning(self, "加载失败",
                f"无法解析音频文件:\n{str(e)}\n\n请确认已安装 ffmpeg 并添加到系统 PATH")

    # ==================================================================
    # 槽函数 — 时间范围 / 自动说话人
    # ==================================================================

    def _on_range_mode_changed(self, button):
        """时间范围模式切换"""
        idx = self._radio_group.id(button)
        self._custom_range_widget.setVisible(idx == 1)  # 自定义模式

    def _on_auto_speaker_toggled(self, checked: bool):
        """自动/手动说话人模式切换"""
        self._manual_speaker_widget.setVisible(not checked)
        self.config.set("auto_speaker", checked)

    def _get_selected_range(self) -> tuple:
        """获取用户选择的时间范围。Returns (mode, start_sec, end_sec) or None"""
        idx = self._radio_group.checkedId()
        modes = ["all", "custom"]
        mode = modes[idx] if 0 <= idx < len(modes) else "all"

        if mode == "all":
            return ("all", 0.0, self._audio_duration)
        else:
            start = self._time_start.time()
            end = self._time_end.time()
            start_sec = start.hour() * 3600 + start.minute() * 60 + start.second()
            end_sec = end.hour() * 3600 + end.minute() * 60 + end.second()

            if end_sec <= start_sec:
                QMessageBox.warning(self, "时间范围错误", "结束时间必须大于起始时间")
                return None
            if start_sec >= self._audio_duration:
                QMessageBox.warning(self, "时间范围错误",
                    f"起始时间超出音频总时长 ({self._sec_to_hms(self._audio_duration)})")
                return None
            if end_sec > self._audio_duration:
                QMessageBox.warning(self, "时间范围提示",
                    f"结束时间超出音频总时长，已自动截断至 {self._sec_to_hms(self._audio_duration)}")
                end_sec = self._audio_duration

            return ("custom", start_sec, end_sec)

    # ==================================================================
    # 槽函数 — 开始转写
    # ==================================================================

    def _on_start_transcribe(self):
        """开始转写流程"""
        # 1. 验证 API 凭据
        creds = self.config.get_api_credentials()
        if not creds["app_id"] or not creds["access_key_id"] or not creds["access_key_secret"]:
            reply = QMessageBox.question(
                self, "未配置 API 凭据",
                "请先配置讯飞开放平台的 API 凭据（APPID、APIKey、APISecret）。\n\n是否现在去设置？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_open_api_settings()
            return

        # 2. 验证音频文件
        if not self._audio_file_path or not os.path.exists(self._audio_file_path):
            QMessageBox.warning(self, "无音频文件", "请先选择一个音频文件")
            return

        # 3. 获取时间范围
        range_info = self._get_selected_range()
        if range_info is None:
            return
        mode, start_sec, end_sec = range_info

        # 4. 准备音频片段（绝不动原始文件）
        try:
            # 仅清理上次产生的临时片段，跳过原始文件
            if self._temp_segment_path and self._temp_segment_path != self._audio_file_path:
                cleanup_temp_file(self._temp_segment_path)
                self._temp_segment_path = ""

            if mode == "all":
                # 全部音频：直接使用原始文件路径（不复制，不删除）
                self._temp_segment_path = self._audio_file_path
                self._segment_start_sec = 0.0
                self._segment_end_sec = self._audio_duration
                self._log(f"使用全部音频 ({self._audio_duration:.1f} 秒)")
            else:
                # 自定义截取：生成临时片段
                path = extract_segment(self._audio_file_path, start_sec, end_sec)
                self._temp_segment_path = path
                self._segment_start_sec = start_sec
                self._segment_end_sec = end_sec
                self._log(f"自定义截取: {self._sec_to_hms(start_sec)} - {self._sec_to_hms(end_sec)}（原始起点 {self._sec_to_hms(start_sec)}）")
        except Exception as e:
            QMessageBox.warning(self, "音频处理失败", f"无法裁剪音频片段:\n{str(e)}")
            return

        # 5. 获取转写参数
        auto_speaker = self._auto_speaker_cb.isChecked()
        if auto_speaker:
            role_num = 0
            self._log("👥 说话人模式: 自动识别（由模型自主匹配）")
        else:
            role_num = self._role_num_spin.value()
            self._log(f"👥 说话人模式: 手动指定 ({role_num} 人)")

        domain_key = self._domain_combo.currentText()
        pd = DOMAIN_MAP.get(domain_key, "")

        # 6. 保存配置
        self.config.set("auto_speaker", auto_speaker)
        self.config.set_api("pd", pd)

        # 7. 获取 API 默认参数
        api_params = self.config.get_api_params()

        # 8. 启动后台线程
        self._log("🚀 开始转写（大模型引擎）...")
        self._set_ui_busy(True)

        audio_duration_ms = str(int((self._segment_end_sec - self._segment_start_sec) * 1000))

        self._worker = TranscriptionWorker(
            app_id=creds["app_id"],
            access_key_id=creds["access_key_id"],
            access_key_secret=creds["access_key_secret"],
            file_path=self._temp_segment_path,
            upload_url=creds["upload_url"],
            result_url=creds["result_url"],
            language=api_params["language"],
            role_type=api_params["role_type"],
            role_num=role_num,
            pd=pd,
            duration_ms=audio_duration_ms,
            eng_smoothproc=api_params["eng_smoothproc"],
            eng_colloqproc=api_params["eng_colloqproc"],
            duration_check_disable=api_params["duration_check_disable"],
            poll_interval=api_params["poll_interval"],
            max_wait=api_params["max_poll_time"],
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_transcribe_finished)
        self._worker.error.connect(self._on_transcribe_error)
        self._worker.start()

    def _on_progress(self, message: str):
        self._log(message)

    def _on_transcribe_finished(self, success: bool, paragraphs: list):
        self._set_ui_busy(False)

        if success and paragraphs:
            # 时间戳偏移修正：API 返回的时序是基于截取片段的，
            # 需要加上截取起始偏移量回推到原始音频时间轴
            offset_sec = self._segment_start_sec
            if offset_sec > 0:
                self._log(f"[时间校准] 截取偏移 +{self._sec_to_hms(offset_sec)}，回推到原始音频时间轴")
                for p in paragraphs:
                    p["start_time"] = self._add_time_offset(p["start_time"], offset_sec)
                    p["end_time"]   = self._add_time_offset(p["end_time"],   offset_sec)

            self._transcription_result = paragraphs
            preview_text = XfyunASRClient.format_txt(paragraphs)
            if len(preview_text) > 2000:
                preview_text = preview_text[:2000] + "\n\n... (请导出 TXT 查看完整结果)"
            self._result_preview.setPlainText(preview_text)

            self._export_btn.setEnabled(True)
            self._copy_btn.setEnabled(True)
            self._clear_btn.setEnabled(True)

            num_speakers = len(set(p.get('speaker', '') for p in paragraphs))
            self._log(f"转写完成！共 {len(paragraphs)} 个段落，{num_speakers} 位说话人")
            self._navigate_to(self._progress_result_card, self._sidebar_btns["results"])
        else:
            self._log("转写完成但无结果")

    def _on_transcribe_error(self, message: str):
        self._set_ui_busy(False)
        self._log(f"❌ 错误: {message}")
        QMessageBox.critical(self, "转写失败", message)

    # ==================================================================
    # 槽函数 — 导出 / 复制 / 清除
    # ==================================================================

    def _on_export_txt(self):
        if not self._transcription_result:
            QMessageBox.warning(self, "无结果", "没有可导出的转写结果")
            return

        base_name = os.path.splitext(os.path.basename(self._audio_file_path))[0]
        time_suffix = (
            f"{self._sec_to_hms(self._segment_start_sec).replace(':', '')}"
            f"-{self._sec_to_hms(self._segment_end_sec).replace(':', '')}"
        )
        default_name = f"{base_name}_transcribe_{time_suffix}.txt"
        default_dir = self.config.get("output_dir", "")
        default_path = os.path.join(default_dir, default_name) if default_dir else default_name

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出转写文本", default_path,
            "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if not file_path:
            return

        try:
            content = XfyunASRClient.format_txt(self._transcription_result)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.config.set("output_dir", os.path.dirname(file_path))
            self._log(f"💾 已导出: {file_path}")
            QMessageBox.information(self, "导出成功", f"转写结果已保存到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"无法写入文件:\n{str(e)}")

    def _on_copy_result(self):
        if not self._transcription_result:
            return
        content = XfyunASRClient.format_txt(self._transcription_result)
        QApplication.clipboard().setText(content)
        self._log("📋 已复制全部结果到剪贴板")

    def _on_clear_result(self):
        """清除转写结果 — 仅清理内存和临时片段，绝不动原始音频文件"""
        self._transcription_result = []
        self._result_preview.clear()
        self._log_text.clear()
        self._export_btn.setEnabled(False)
        self._copy_btn.setEnabled(False)
        self._clear_btn.setEnabled(False)

        # 仅删除临时裁剪片段，跳过原始音频文件
        if self._temp_segment_path and os.path.exists(self._temp_segment_path):
            if self._temp_segment_path != self._audio_file_path:
                cleanup_temp_file(self._temp_segment_path)
        self._temp_segment_path = ""

        self._log("结果已清除（原始音频文件未受影响）")

    # ==================================================================
    # 槽函数 — API 设置弹窗
    # ==================================================================

    def _on_open_api_settings(self):
        dialog = APISettingsDialog(self, self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._update_start_button_state()
            self._log("✅ API 凭据已更新")

    # ==================================================================
    # 辅助方法
    # ==================================================================

    def _log(self, message: str):
        self._log_text.append(message)
        sb = self._log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_ui_busy(self, busy: bool):
        self._start_btn.setEnabled(not busy)
        self._progress_bar.setVisible(busy)
        for btn in self._radio_group.buttons():
            btn.setEnabled(not busy)

        if busy:
            self._progress_bar.setRange(0, 0)
            self._log_text.clear()

    def _update_start_button_state(self):
        has_file = bool(self._audio_file_path and os.path.exists(self._audio_file_path))
        has_creds = self.config.has_valid_credentials()
        self._start_btn.setEnabled(has_file and has_creds)

        if not has_creds and has_file:
            self._start_btn.setToolTip("请先配置 API 凭据")
        elif not has_file:
            self._start_btn.setToolTip("请先选择音频文件")
        else:
            self._start_btn.setToolTip("")

    def _load_saved_settings(self):
        """加载保存的配置：主题、API 凭据"""
        # 加载并应用主题
        saved_theme = self.config.get("theme", "dark")
        self._switch_theme(saved_theme)

        # 更新凭据状态
        self._update_start_button_state()
        if self.config.has_valid_credentials():
            self._log("ℹ️ 已加载保存的 API 凭据")

        # 自动说话人模式初始状态
        auto_speaker = self.config.get("auto_speaker", True)
        self._auto_speaker_cb.setChecked(auto_speaker)
        self._manual_speaker_widget.setVisible(not auto_speaker)

    def _scroll_to_card(self, card):
        """滚动主内容区使指定卡片可见"""
        self._scroll_area.ensureWidgetVisible(card, 50, 50)

    @staticmethod
    @staticmethod
    def _sec_to_hms(seconds: float) -> str:
        total = int(seconds)
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"

    @staticmethod
    def _add_time_offset(hms: str, offset_sec: float) -> str:
        """将 HH:MM:SS 格式的时间加上偏移秒数，返回 HH:MM:SS"""
        parts = hms.strip().split(":")
        total_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        total_sec += int(offset_sec)
        return f"{total_sec // 3600:02d}:{(total_sec % 3600) // 60:02d}:{total_sec % 60:02d}"

    @staticmethod
    def _get_domain_key(pd: str) -> str:
        for key, val in DOMAIN_MAP.items():
            if val == pd:
                return key
        return "通用"


# ============================================================================
# API 设置弹窗
# ============================================================================

class APISettingsDialog(QDialog):
    """
    API 凭据设置对话框（录音文件转写大模型）。
    对照讯飞控制台：APPID / APIKey / APISecret，保存到 api_config.json。
    """

    def __init__(self, parent, config: ConfigManager):
        super().__init__(parent)
        self.config = config

        self.setWindowTitle("⚙️ API 凭据设置（转写大模型）")
        self.setMinimumWidth(520)
        self.setModal(True)

        self._build_ui()

        creds = config.get_api_credentials()
        self._appid_input.setText(creds["app_id"])
        self._keyid_input.setText(creds["access_key_id"])
        self._secret_input.setText(creds["access_key_secret"])
        self._upload_url_input.setText(creds["upload_url"])
        self._result_url_input.setText(creds["result_url"])

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("讯飞录音文件转写大模型 API 凭据")
        title.setFont(get_font(16, bold=True))
        layout.addWidget(title)

        hint = HintLabel(
            "在讯飞开放平台 (console.xfyun.cn) 创建应用 → 开通「录音文件转写大模型」服务后获取。\n"
            "凭据自动保存到 api_config.json，可手动编辑该文件进行调试。"
        )
        layout.addWidget(hint)
        layout.addSpacing(4)

        form = QFormLayout()
        form.setSpacing(12)

        self._appid_input = StyledLineEdit("请输入 AppID")
        self._appid_input.setMinimumWidth(320)
        form.addRow("AppID:", self._appid_input)

        self._keyid_input = StyledLineEdit("请输入 APIKey")
        self._keyid_input.setMinimumWidth(320)
        form.addRow("APIKey:", self._keyid_input)

        self._secret_input = StyledLineEdit("请输入 APISecret")
        self._secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("APISecret:", self._secret_input)

        form.addRow(QLabel(""))  # 空行

        self._upload_url_input = StyledLineEdit("上传接口地址")
        form.addRow("Upload URL:", self._upload_url_input)

        self._result_url_input = StyledLineEdit("结果查询接口地址")
        form.addRow("Result URL:", self._result_url_input)

        layout.addLayout(form)
        layout.addSpacing(10)

        btn_box = QDialogButtonBox()
        save_btn = GradientButton("💾 保存凭据")
        cancel_btn = GradientButton("取消")
        cancel_btn.setProperty("cssClass", "secondary")

        btn_box.addButton(save_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)

        save_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self.reject)

        layout.addWidget(btn_box)

    def _on_save(self):
        app_id = self._appid_input.text().strip()
        key_id = self._keyid_input.text().strip()
        secret = self._secret_input.text().strip()

        if not app_id or not key_id or not secret:
            QMessageBox.warning(self, "输入不完整",
                "APPID、APIKey、APISecret 均为必填项")
            return

        self.config.set_api_credentials(
            app_id=app_id,
            access_key_id=key_id,
            access_key_secret=secret,
            upload_url=self._upload_url_input.text().strip(),
            result_url=self._result_url_input.text().strip(),
        )
        self.accept()
