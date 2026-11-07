"""System settings interface for the desktop demo with tabbed modular architecture."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import icon


class ToggleButton(QPushButton):
    """Custom iOS/macOS-style smooth toggle switch with midnight SOC palette."""

    def __init__(self, checked: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsToggle")
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(48, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(lambda _: self.update())

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        # Checked: Deep purple gradient/accent, Unchecked: Dark navy
        painter.setBrush(QColor("#6C5DD3" if self.isChecked() else "#25224D"))
        painter.drawRoundedRect(QRectF(0, 0, 48, 26), 13, 13)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(25 if self.isChecked() else 3, 3, 20, 20))


class PreviewWidget(QWidget):
    """High-fidelity miniature SOC Dashboard preview with midnight indigo palette."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # 1. Background Shell
        painter.fillRect(self.rect(), QColor("#131129"))
        painter.setPen(QPen(QColor("#282452"), 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)

        # 2. Mini Sidebar (Left 42px)
        painter.fillRect(QRectF(1, 1, 42, h - 2), QColor("#181533"))
        # Mini logo dot
        painter.fillRect(QRectF(14, 10, 14, 14), QColor("#6C5DD3"))
        # Navigation items
        for y in range(36, h - 16, 16):
            is_active = (y == 36)
            painter.fillRect(QRectF(8, y, 26, 6), QColor("#8B5CF6" if is_active else "#2B2757"))

        # 3. Mini Topbar
        painter.fillRect(QRectF(43, 1, w - 44, 26), QColor("#1B1938"))
        painter.setPen(QPen(QColor("#24204A"), 1))
        painter.drawLine(43, 27, w - 1, 27)
        # Search pill mockup
        painter.fillRect(QRectF(52, 6, 80, 14), QColor("#15132B"))
        # Status dot
        painter.fillRect(QRectF(w - 24, 9, 8, 8), QColor("#10B981"))

        # 4. Mini KPI Cards (4 cards)
        colors = ["#3B82F6", "#8B5CF6", "#FBBF24", "#FF5B79"]
        card_w = min(82, max(50, (w - 70) / 4))
        for index, color in enumerate(colors):
            x = 52 + index * (card_w + 6)
            if x + card_w < w - 8:
                painter.fillRect(QRectF(x, 34, card_w, 32), QColor("#1E1B40"))
                painter.fillRect(QRectF(x + 6, 42, 12, 12), QColor(color))
                painter.fillRect(QRectF(x + 22, 43, card_w - 28, 4), QColor("#CBD5E1"))
                painter.fillRect(QRectF(x + 22, 51, card_w - 38, 4), QColor("#64748B"))

        # 5. Mini Charts (Row below KPIs)
        chart_y = 74
        chart_h = h - chart_y - 10
        if chart_h > 30:
            # Main Wave Chart (Left ~60%)
            chart_w = (w - 60) * 0.62
            painter.fillRect(QRectF(52, chart_y, chart_w, chart_h), QColor("#1A173B"))
            # Grid lines
            painter.setPen(QPen(QColor("#24204A"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(56, chart_y + chart_h / 2, 52 + chart_w - 4, chart_y + chart_h / 2)
            # Wave line
            points = [
                (56, chart_y + chart_h - 10),
                (80, chart_y + chart_h - 28),
                (105, chart_y + chart_h - 16),
                (130, chart_y + chart_h - 36),
                (155, chart_y + chart_h - 22),
                (180, chart_y + chart_h - 44),
                (205, chart_y + chart_h - 26),
                (230, chart_y + chart_h - 40),
                (255, chart_y + chart_h - 32),
                (280, chart_y + chart_h - 38),
            ]
            painter.setPen(QPen(QColor("#6C5DD3"), 2))
            for p1, p2 in zip(points, points[1:]):
                if p2[0] < 52 + chart_w - 4:
                    painter.drawLine(p1[0], p1[1], p2[0], p2[1])

            # Secondary Donut / Distribution Mockup (Right ~38%)
            right_x = 52 + chart_w + 8
            right_w = w - right_x - 12
            if right_w > 40:
                painter.fillRect(QRectF(right_x, chart_y, right_w, chart_h), QColor("#1A173B"))
                # Mini Donut Ring
                donut_cx = right_x + 26
                donut_cy = chart_y + chart_h / 2
                painter.setPen(QPen(QColor("#3B82F6"), 4))
                painter.drawArc(QRectF(donut_cx - 14, donut_cy - 14, 28, 28), 0, 180 * 16)
                painter.setPen(QPen(QColor("#FF5B79"), 4))
                painter.drawArc(QRectF(donut_cx - 14, donut_cy - 14, 28, 28), 180 * 16, 100 * 16)
                painter.setPen(QPen(QColor("#10B981"), 4))
                painter.drawArc(QRectF(donut_cx - 14, donut_cy - 14, 28, 28), 280 * 16, 80 * 16)
                # Mini bars
                bar_x = donut_cx + 22
                bar_w = right_x + right_w - bar_x - 8
                if bar_w > 10:
                    for bi, bcol in enumerate(["#3B82F6", "#8B5CF6", "#F59E0B"]):
                        by = chart_y + 12 + bi * 14
                        painter.fillRect(QRectF(bar_x, by, bar_w * (0.8 - bi * 0.2), 5), QColor(bcol))


class SettingsCard(QFrame):
    """Modern SOC settings card with icon badge, title, subtitle, and input rows."""

    def __init__(
        self,
        title: str,
        icon_name: str,
        color: str = "#8B5CF6",
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(22, 20, 22, 22)
        self.box.setSpacing(14)

        # Header
        header = QHBoxLayout()
        header.setSpacing(12)

        badge = QLabel()
        badge.setObjectName("settingsCardIcon")
        badge.setPixmap(icon(icon_name, color, 20).pixmap(20, 20))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(40, 40)
        header.addWidget(badge)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("settingsCardTitle")
        titles.addWidget(title_label)
        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("settingsCardSubtitle")
            titles.addWidget(sub_label)
        header.addLayout(titles)
        header.addStretch()
        self.box.addLayout(header)

    def add_row(self, label_text: str, widget: QWidget, stretch: int = 1) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        label = QLabel(label_text)
        label.setObjectName("settingsLabel")
        label.setMinimumWidth(180)
        row.addWidget(label)

        if isinstance(widget, ToggleButton):
            row.addStretch()
            switch_group = QWidget()
            switch_layout = QHBoxLayout(switch_group)
            switch_layout.setContentsMargins(0, 0, 0, 0)
            switch_layout.setSpacing(10)
            switch_layout.addWidget(widget)
            state = QLabel("Bật" if widget.isChecked() else "Tắt")
            state.setObjectName("settingsToggleState")
            widget.toggled.connect(lambda checked, s=state: s.setText("Bật" if checked else "Tắt"))
            switch_layout.addWidget(state)
            row.addWidget(switch_group)
        else:
            row.addWidget(widget, stretch)
        self.box.addLayout(row)

    def add_slider(
        self,
        label_text: str,
        min_val: int,
        max_val: int,
        cur_val: int,
        factor: float = 0.01,
    ) -> QSlider:
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        header_row = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("settingsLabel")
        header_row.addWidget(label)
        header_row.addStretch()

        val_label = QLabel(f"{cur_val * factor:.2f}" if factor < 1 else f"{cur_val}")
        val_label.setObjectName("sliderValue")
        val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_row.addWidget(val_label)
        lay.addLayout(header_row)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setObjectName("settingsSlider")
        slider.setRange(min_val, max_val)
        slider.setValue(cur_val)
        slider.valueChanged.connect(
            lambda v, l=val_label, f=factor: l.setText(f"{v * f:.2f}" if f < 1 else f"{v}")
        )
        lay.addWidget(slider)

        self.box.addWidget(container)
        return slider


def combo(items: list[str], width: int = 180) -> QComboBox:
    widget = QComboBox()
    widget.setObjectName("settingsCombo")
    widget.addItems(items)
    widget.setMinimumWidth(width)
    return widget


def input_field(text: str = "", placeholder: str = "") -> QLineEdit:
    widget = QLineEdit(text)
    widget.setObjectName("settingsInput")
    widget.setPlaceholderText(placeholder)
    return widget


def make_page(card_left: QWidget, card_right: QWidget, ratio_left: int = 1, ratio_right: int = 1) -> QWidget:
    """Helper to assemble a tab page with perfectly grouped cards and natural vertical pacing."""
    page = QWidget()
    page_lay = QVBoxLayout(page)
    page_lay.setContentsMargins(0, 4, 0, 4)
    page_lay.setSpacing(16)

    cards_row = QHBoxLayout()
    cards_row.setSpacing(16)
    cards_row.addWidget(card_left, ratio_left)
    cards_row.addWidget(card_right, ratio_right)
    page_lay.addLayout(cards_row)
    page_lay.addStretch(1)  # Pushes empty space to the bottom, keeping all rows tight and natural!

    return page


class SettingsPage(QScrollArea):
    """System settings page with modular tab views driven by category buttons."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("settingsContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 14, 18, 18)
        root.setSpacing(14)

        # ---------------------------------------------------------------------
        # 1. HEADER (Title, Subtitle & SOC Status Badge)
        # ---------------------------------------------------------------------
        header = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(3)

        title = QLabel("Cài đặt hệ thống")
        title.setObjectName("settingsHeading")
        intro.addWidget(title)

        subtitle = QLabel("Quản lý cấu hình toàn diện, tham số mô hình AI, kết nối SDN Controller và chính sách an ninh mạng")
        subtitle.setObjectName("settingsSubtitle")
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        header.addLayout(intro, stretch=1)

        status_badge = QLabel("● SYSTEM ACTIVE  v1.2.0")
        status_badge.setStyleSheet(
            "background: rgba(16, 185, 129, 0.14); color: #34D399; "
            "border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 10px; "
            "padding: 8px 16px; font-weight: 700; font-size: 12px;"
        )
        header.addWidget(status_badge)
        root.addLayout(header)

        # ---------------------------------------------------------------------
        # 2. TAB BUTTONS (Có sẵn 7 nút chức năng chia theo từng thành phần)
        # ---------------------------------------------------------------------
        self.tabs_layout = QHBoxLayout()
        self.tabs_layout.setSpacing(8)
        self.tab_buttons: list[QPushButton] = []
        self.tab_data = [
            ("Tổng quan", "settings"),
            ("Giao diện", "palette"),
            ("Kết nối hệ thống", "nodes"),
            ("Giám sát mạng", "monitor"),
            ("Phát hiện bất thường", "shield"),
            ("Dự đoán lưu lượng", "trend"),
            ("Giảm thiểu rủi ro (IPS)", "lock"),
        ]

        for index, (text, icon_name) in enumerate(self.tab_data):
            btn = QPushButton("  " + text)
            btn.setObjectName("activeSettingsTab" if index == 0 else "settingsTab")
            btn.setIcon(icon(icon_name, "#FFFFFF" if index == 0 else "#9E9BB5", 15))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda checked=False, i=index: self.switch_tab(i))
            self.tab_buttons.append(btn)
            self.tabs_layout.addWidget(btn)

        root.addLayout(self.tabs_layout)

        # ---------------------------------------------------------------------
        # 3. STACKED WIDGET (Chia 7 thành phần cấu hình tương ứng 7 nút)
        # ---------------------------------------------------------------------
        self.stack = QStackedWidget()
        self.stack.setObjectName("settingsStack")
        self.stack.addWidget(self._page_overview())
        self.stack.addWidget(self._page_appearance())
        self.stack.addWidget(self._page_connection())
        self.stack.addWidget(self._page_monitoring())
        self.stack.addWidget(self._page_detection())
        self.stack.addWidget(self._page_prediction())
        self.stack.addWidget(self._page_ips())
        root.addWidget(self.stack, 1)

        # ---------------------------------------------------------------------
        # 4. PERSISTENT FOOTER (Khôi phục, Kiểm tra, Lưu & Áp dụng)
        # ---------------------------------------------------------------------
        footer = QHBoxLayout()
        footer.setSpacing(12)

        restore = QPushButton("  Khôi phục cài đặt gốc")
        restore.setObjectName("settingsSecondaryButton")
        restore.setIcon(icon("refresh", "#9E9BB5", 15))
        restore.setCursor(Qt.CursorShape.PointingHandCursor)
        restore.clicked.connect(self.restore_defaults)
        footer.addWidget(restore)

        footer.addStretch()

        self.status = QLabel("")
        self.status.setObjectName("settingsStatus")
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        footer.addWidget(self.status)

        validate = QPushButton("  Kiểm tra cấu hình")
        validate.setObjectName("settingsSecondaryButton")
        validate.setIcon(icon("check", "#9E9BB5", 15))
        validate.setCursor(Qt.CursorShape.PointingHandCursor)
        validate.clicked.connect(lambda: self.show_status("✓ Tất cả tham số cấu hình đều hợp lệ!", True))
        footer.addWidget(validate)

        save = QPushButton("  Lưu cấu hình")
        save.setObjectName("saveSettingsButton")
        save.setIcon(icon("save", "#FFFFFF", 15))
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(lambda: self.show_status("✓ Đã lưu cấu hình hệ thống thành công!", True))
        footer.addWidget(save)

        apply = QPushButton("  Áp dụng")
        apply.setObjectName("applySettingsButton")
        apply.setIcon(icon("check", "#FFFFFF", 15))
        apply.setCursor(Qt.CursorShape.PointingHandCursor)
        apply.clicked.connect(lambda: self.show_status("✓ Đã áp dụng cấu hình thời gian thực lên SDN & AI Engine!", True))
        footer.addWidget(apply)

        root.addLayout(footer)
        self.setWidget(content)

    # -------------------------------------------------------------------------
    # TAB SWITCHING LOGIC
    # -------------------------------------------------------------------------
    def switch_tab(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.tab_buttons):
            if i == index:
                btn.setObjectName("activeSettingsTab")
                btn.setIcon(icon(self.tab_data[i][1], "#FFFFFF", 15))
            else:
                btn.setObjectName("settingsTab")
                btn.setIcon(icon(self.tab_data[i][1], "#9E9BB5", 15))
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # -------------------------------------------------------------------------
    # TAB 0: TỔNG QUAN (OVERVIEW)
    # -------------------------------------------------------------------------
    def _page_overview(self) -> QWidget:
        # Card 1: Thông tin hệ thống
        card1 = SettingsCard(
            "Thông tin hệ thống & Môi trường",
            "info",
            "#60A5FA",
            "Phiên bản và kiến trúc vận hành của nền tảng SOC AI",
        )
        self.app_name_input = input_field("AI Network IDS/IPS Platform")
        card1.add_row("Tên ứng dụng", self.app_name_input)
        self.version_input = input_field("v1.2.0 (Cybera SOC Edition)")
        card1.add_row("Phiên bản", self.version_input)

        # Description tightly grouped with 6px spacing
        desc_container = QWidget()
        desc_lay = QVBoxLayout(desc_container)
        desc_lay.setContentsMargins(0, 0, 0, 0)
        desc_lay.setSpacing(6)
        lbl = QLabel("Mô tả hệ thống")
        lbl.setObjectName("settingsLabel")
        desc_lay.addWidget(lbl)
        self.desc_text = QTextEdit(
            "Hệ thống giám sát lưu lượng SDN thời gian thực, phát hiện bất thường bằng học máy "
            "(Random Forest / Isolation Forest), dự báo lưu lượng chuỗi thời gian (LSTM) "
            "và tự động thực thi chính sách giảm thiểu rủi ro IPS trên Ryu Controller."
        )
        self.desc_text.setObjectName("settingsText")
        self.desc_text.setFixedHeight(72)
        desc_lay.addWidget(self.desc_text)
        card1.box.addWidget(desc_container)

        self.lang_combo = combo(["Tiếng Việt (Mặc định)", "English (US)"])
        card1.add_row("Ngôn ngữ giao diện", self.lang_combo)
        self.autostart_toggle = ToggleButton(True)
        card1.add_row("Khởi động cùng hệ điều hành", self.autostart_toggle, 0)
        self.autoupdate_toggle = ToggleButton(True)
        card1.add_row("Tự động kiểm tra bản cập nhật", self.autoupdate_toggle, 0)
        card1.box.addStretch(1)

        # Card 2: Trạng thái mô-đun & Sức khỏe SOC
        card2 = SettingsCard(
            "Trạng thái mô-đun & Sức khỏe SOC",
            "activity",
            "#34D399",
            "Tình trạng sẵn sàng của các thành phần cốt lõi",
        )

        def make_status_row(name: str, status_txt: str, color: str) -> QWidget:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)
            nl = QLabel(name)
            nl.setObjectName("settingsLabel")
            rl.addWidget(nl)
            rl.addStretch()
            sl = QLabel(status_txt)
            sl.setStyleSheet(
                f"color: {color}; background: {color}1A; border: 1px solid {color}4D; "
                "border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 700;"
            )
            rl.addWidget(sl)
            return row

        card2.box.addWidget(make_status_row("Mô hình phát hiện AI (IDS)", "● Đang hoạt động (98.5% SLA)", "#10B981"))
        card2.box.addWidget(make_status_row("Mô hình dự đoán lưu lượng", "● LSTM Engine Active", "#8B5CF6"))
        card2.box.addWidget(make_status_row("Cơ chế giảm thiểu IPS", "● 82 Flow Rules Enforced", "#F59E0B"))
        card2.box.addWidget(make_status_row("Ryu SDN Controller", "● Kết nối trực tuyến (1.2ms)", "#3B82F6"))
        card2.box.addWidget(make_status_row("Cơ sở dữ liệu PostgreSQL", "● Đã đồng bộ 5,281 logs", "#10B981"))

        card2.box.addSpacing(6)
        # Resource Bars
        cpu_box = QVBoxLayout()
        cpu_box.setSpacing(5)
        cpu_hdr = QHBoxLayout()
        cpu_lbl = QLabel("Tải bộ xử lý AI Engine (CPU)")
        cpu_lbl.setObjectName("settingsLabel")
        cpu_hdr.addWidget(cpu_lbl)
        cpu_hdr.addStretch()
        cpu_val = QLabel("14.2%")
        cpu_val.setObjectName("settingsValue")
        cpu_hdr.addWidget(cpu_val)
        cpu_box.addLayout(cpu_hdr)

        cpu_bar = QProgressBar()
        cpu_bar.setRange(0, 100)
        cpu_bar.setValue(14)
        cpu_bar.setTextVisible(False)
        cpu_bar.setFixedHeight(8)
        cpu_bar.setStyleSheet("QProgressBar { background: #25224D; border-radius: 4px; border: none; } QProgressBar::chunk { background: #3B82F6; border-radius: 4px; }")
        cpu_box.addWidget(cpu_bar)
        card2.box.addLayout(cpu_box)

        ram_box = QVBoxLayout()
        ram_box.setSpacing(5)
        ram_hdr = QHBoxLayout()
        ram_lbl = QLabel("Bộ nhớ RAM sử dụng (AI Models)")
        ram_lbl.setObjectName("settingsLabel")
        ram_hdr.addWidget(ram_lbl)
        ram_hdr.addStretch()
        ram_val = QLabel("38.5% (1.54 GB)")
        ram_val.setObjectName("settingsValue")
        ram_hdr.addWidget(ram_val)
        ram_box.addLayout(ram_hdr)

        ram_bar = QProgressBar()
        ram_bar.setRange(0, 100)
        ram_bar.setValue(38)
        ram_bar.setTextVisible(False)
        ram_bar.setFixedHeight(8)
        ram_bar.setStyleSheet("QProgressBar { background: #25224D; border-radius: 4px; border: none; } QProgressBar::chunk { background: #8B5CF6; border-radius: 4px; }")
        ram_box.addWidget(ram_bar)
        card2.box.addLayout(ram_box)
        card2.box.addStretch(1)

        return make_page(card1, card2)

    # -------------------------------------------------------------------------
    # TAB 1: GIAO DIỆN (APPEARANCE)
    # -------------------------------------------------------------------------
    def _page_appearance(self) -> QWidget:
        card1 = SettingsCard(
            "Cài đặt hiển thị & Chủ đề",
            "palette",
            "#C084FC",
            "Tùy chỉnh giao diện màu sắc, tỷ lệ hiển thị và hiệu ứng",
        )
        self.theme_combo = combo(["Tối (Midnight Indigo SOC - Khuyên dùng)", "Sáng (Cyber Light Mode)"])
        card1.add_row("Chủ đề chính", self.theme_combo)

        # Accent color selection
        colors = QWidget()
        color_row = QHBoxLayout(colors)
        color_row.setContentsMargins(0, 0, 0, 0)
        color_row.setSpacing(10)
        for val in ("#6C5DD3", "#3B82F6", "#10B981", "#F59E0B", "#FF5B79"):
            dot = QPushButton()
            dot.setFixedSize(28, 28)
            dot.setCursor(Qt.CursorShape.PointingHandCursor)
            border = "#FFFFFF" if val == "#6C5DD3" else val
            dot.setStyleSheet(f"background: {val}; border-radius: 14px; border: 2px solid {border};")
            color_row.addWidget(dot)
        card1.add_row("Màu điểm nhấn (Accent)", colors)

        self.font_scale_combo = combo(["100% (Chuẩn Segoe UI)", "90% (Gọn gàng)", "110% (Lớn)"])
        card1.add_row("Tỷ lệ phông chữ", self.font_scale_combo)
        self.anim_toggle = ToggleButton(True)
        card1.add_row("Hiệu ứng chuyển động mượt", self.anim_toggle, 0)
        self.autoscale_toggle = ToggleButton(True)
        card1.add_row("Tự co giãn bảng theo độ phân giải", self.autoscale_toggle, 0)
        self.legend_toggle = ToggleButton(True)
        card1.add_row("Hiển thị nhãn chú giải biểu đồ", self.legend_toggle, 0)
        card1.box.addStretch(1)

        card2 = SettingsCard(
            "Xem trước giao diện (Live Preview)",
            "monitor",
            "#60A5FA",
            "Mô phỏng thu nhỏ bố cục trung tâm điều hành SOC",
        )
        card2.box.addWidget(PreviewWidget())

        note = QLabel(
            "✓  Độ phân giải tối ưu: 1366×768 đến 1920×1080 (Full HD)\n"
            "✓  Bố cục co giãn thích ứng khi đóng/mở Sidebar điều hướng (80px ↔ 280px)\n"
            "✓  Áp dụng bảng màu SOC Cybera Midnight Indigo chuẩn quốc tế\n"
            "✓  Hỗ trợ hiển thị mượt mà trên Windows Acrylic / Frameless Window"
        )
        note.setStyleSheet("color: #94A3B8; font-size: 12.5px; line-height: 1.6; padding: 10px 4px;")
        card2.box.addWidget(note)
        card2.box.addStretch(1)

        return make_page(card1, card2, 54, 46)

    # -------------------------------------------------------------------------
    # TAB 2: KẾT NỐI HỆ THỐNG (SYSTEM CONNECTIVITY)
    # -------------------------------------------------------------------------
    def _page_connection(self) -> QWidget:
        # Card 1: Ryu SDN Controller
        card1 = SettingsCard(
            "Kết nối SDN Controller (Ryu / OpenFlow)",
            "nodes",
            "#60A5FA",
            "Cấu hình giao tiếp điều khiển mạng OpenFlow 1.3",
        )
        self.ryu_ip = input_field("192.168.1.10")
        card1.add_row("Địa chỉ IP Controller", self.ryu_ip)
        self.ryu_port = input_field("8080")
        card1.add_row("Cổng REST API", self.ryu_port)
        self.openflow_port = input_field("6653")
        card1.add_row("Cổng OpenFlow Switch", self.openflow_port)
        self.ryu_proto = combo(["REST API / HTTP", "gRPC / Protobuf", "WebSocket Stream"])
        card1.add_row("Giao thức kết nối", self.ryu_proto)
        self.ryu_autosync = ToggleButton(True)
        card1.add_row("Tự động đồng bộ Switch topology", self.ryu_autosync, 0)

        test_btn = QPushButton("  Kiểm tra kết nối Ryu Controller")
        test_btn.setObjectName("connectionTestButton")
        test_btn.setIcon(icon("refresh", "#A78BFA", 14))
        test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_btn.clicked.connect(self._test_ryu_conn)
        card1.box.addWidget(test_btn, 0, Qt.AlignmentFlag.AlignRight)

        self.ryu_status_lbl = QLabel("● Đang kết nối trực tuyến (Ping: 1.2ms)")
        self.ryu_status_lbl.setObjectName("connectionStatus")
        card1.add_row("Trạng thái Ryu", self.ryu_status_lbl, 0)
        card1.box.addStretch(1)

        # Card 2: Database & Backend
        card2 = SettingsCard(
            "Cơ sở dữ liệu & Quản lý kết nối",
            "database",
            "#34D399",
            "Cấu hình PostgreSQL lưu trữ nhật ký và sự kiện",
        )
        self.db_host = input_field("localhost:5432")
        card2.add_row("Máy chủ CSDL (Host)", self.db_host)
        self.db_name = input_field("ai_network_ids")
        card2.add_row("Tên Database", self.db_name)
        self.db_auto_reconnect = ToggleButton(True)
        card2.add_row("Tự động kết nối lại khi rớt mạng", self.db_auto_reconnect, 0)
        self.db_retry_interval = combo(["5 giây", "10 giây (Khuyên dùng)", "30 giây", "1 phút"])
        card2.add_row("Khoảng thời gian thử lại", self.db_retry_interval)

        self.db_timeout = QSpinBox()
        self.db_timeout.setObjectName("settingsSpin")
        self.db_timeout.setRange(1000, 30000)
        self.db_timeout.setSingleStep(500)
        self.db_timeout.setValue(5000)
        self.db_timeout.setSuffix(" ms")
        card2.add_row("Thời gian chờ tối đa (Timeout)", self.db_timeout)

        test_db_btn = QPushButton("  Kiểm tra kết nối Database")
        test_db_btn.setObjectName("connectionTestButton")
        test_db_btn.setIcon(icon("database", "#A78BFA", 14))
        test_db_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_db_btn.clicked.connect(self._test_db_conn)
        card2.box.addWidget(test_db_btn, 0, Qt.AlignmentFlag.AlignRight)

        self.db_status_lbl = QLabel("● Đã kết nối thành công (PostgreSQL 16)")
        self.db_status_lbl.setObjectName("connectionStatus")
        card2.add_row("Trạng thái CSDL", self.db_status_lbl, 0)
        card2.box.addStretch(1)

        return make_page(card1, card2)

    # -------------------------------------------------------------------------
    # TAB 3: GIÁM SÁT MẠNG (NETWORK MONITORING)
    # -------------------------------------------------------------------------
    def _page_monitoring(self) -> QWidget:
        # Card 1: Packet Capture Engine
        card1 = SettingsCard(
            "Cấu hình thu thập gói tin (Packet Capture)",
            "activity",
            "#10B981",
            "Thiết lập cổng quan trắc và cơ chế bắt gói",
        )
        self.iface_combo = combo(["Tất cả giao diện (all)", "s1-eth1", "eth0", "lo"])
        card1.add_row("Giao diện mạng giám sát", self.iface_combo)
        self.sample_interval = combo(["1 giây (Thời gian thực)", "3 giây", "5 giây (Tiêu chuẩn)", "10 giây"])
        card1.add_row("Chu kỳ lấy mẫu lưu lượng", self.sample_interval)
        self.capture_mode = combo(["PCAP (Raw Packet Mirror)", "NetFlow v9", "sFlow", "IPFIX"])
        card1.add_row("Phương thức thu thập", self.capture_mode)

        bpf_container = QWidget()
        bpf_box = QVBoxLayout(bpf_container)
        bpf_box.setContentsMargins(0, 0, 0, 0)
        bpf_box.setSpacing(6)
        bpf_lbl = QLabel("Bộ lọc gói tin BPF (Berkeley Packet Filter)")
        bpf_lbl.setObjectName("settingsLabel")
        bpf_box.addWidget(bpf_lbl)
        self.bpf_input = input_field("tcp or udp or icmp", "Ví dụ: port 80 or host 192.168.1.10")
        bpf_box.addWidget(self.bpf_input)
        card1.box.addWidget(bpf_container)

        bpf_btn = QPushButton("  Kiểm tra cú pháp BPF")
        bpf_btn.setObjectName("connectionTestButton")
        bpf_btn.setIcon(icon("check", "#A78BFA", 14))
        bpf_btn.clicked.connect(lambda: self.show_status("✓ Cú pháp bộ lọc BPF hoàn toàn chính xác!", True))
        card1.box.addWidget(bpf_btn, 0, Qt.AlignmentFlag.AlignRight)
        card1.box.addStretch(1)

        # Card 2: Storage & PCAP Data
        card2 = SettingsCard(
            "Lưu trữ & Dữ liệu PCAP",
            "server",
            "#FBBF24",
            "Dung lượng bộ đệm và chính sách vòng đời gói tin",
        )
        self.save_raw_toggle = ToggleButton(True)
        card2.add_row("Lưu trữ dữ liệu gói tin thô", self.save_raw_toggle, 0)

        self.storage_limit = QSpinBox()
        self.storage_limit.setObjectName("settingsSpin")
        self.storage_limit.setRange(1, 500)
        self.storage_limit.setValue(10)
        self.storage_limit.setSuffix(" GB")
        card2.add_row("Giới hạn dung lượng lưu trữ", self.storage_limit)

        self.auto_clean_toggle = ToggleButton(True)
        card2.add_row("Tự động ghi đè log cũ khi đầy", self.auto_clean_toggle, 0)

        self.retention_days = QSpinBox()
        self.retention_days.setObjectName("settingsSpin")
        self.retention_days.setRange(1, 365)
        self.retention_days.setValue(30)
        self.retention_days.setSuffix(" ngày")
        card2.add_row("Thời gian lưu trữ log mạng", self.retention_days)

        self.storage_path = input_field("/var/log/ids_pcap")
        card2.add_row("Thư mục lưu trữ PCAP", self.storage_path)
        card2.box.addStretch(1)

        return make_page(card1, card2)

    # -------------------------------------------------------------------------
    # TAB 4: PHÁT HIỆN BẤT THƯỜNG (ANOMALY DETECTION)
    # -------------------------------------------------------------------------
    def _page_detection(self) -> QWidget:
        # Card 1: AI Model Configuration
        card1 = SettingsCard(
            "Cấu hình mô hình Học máy AI",
            "shield",
            "#A78BFA",
            "Lựa chọn thuật toán phân loại và ngưỡng kích hoạt",
        )
        self.detect_model_combo = combo([
            "Random Forest + Isolation Forest (Hybrid Ensemble)",
            "Autoencoder (Deep Anomaly Detection)",
            "XGBoost Classifier (Supervised)",
            "One-Class SVM (Statistical)",
        ], 240)
        card1.add_row("Thuật toán AI phát hiện", self.detect_model_combo)

        card1.box.addSpacing(4)
        self.threshold_slider = card1.add_slider(
            "Ngưỡng phát hiện bất thường (Detection Threshold):",
            10, 95, 70, 0.01
        )
        self.sensitivity_slider = card1.add_slider(
            "Độ nhạy phân loại tấn công (Sensitivity Factor):",
            10, 95, 80, 0.01
        )

        self.auto_retrain_toggle = ToggleButton(True)
        card1.add_row("Tự động cập nhật trọng số mô hình", self.auto_retrain_toggle, 0)
        self.label_attacks_toggle = ToggleButton(True)
        card1.add_row("Tự động gắn nhãn loại tấn công", self.label_attacks_toggle, 0)
        card1.box.addStretch(1)

        # Card 2: Alerts & Event Dispatching
        card2 = SettingsCard(
            "Cảnh báo & Xử lý sự kiện AI",
            "bell",
            "#FF5B79",
            "Phương thức thông báo và lưu vết dữ liệu tấn công",
        )
        self.sound_alert_toggle = ToggleButton(True)
        card2.add_row("Phát âm thanh cảnh báo (Critical)", self.sound_alert_toggle, 0)
        self.desktop_notify_toggle = ToggleButton(True)
        card2.add_row("Bắn thông báo Desktop Notification", self.desktop_notify_toggle, 0)
        self.save_vector_toggle = ToggleButton(True)
        card2.add_row("Lưu chi tiết vector đặc trưng (Feature Vector)", self.save_vector_toggle, 0)

        self.history_days = QSpinBox()
        self.history_days.setObjectName("settingsSpin")
        self.history_days.setRange(1, 365)
        self.history_days.setValue(60)
        self.history_days.setSuffix(" ngày")
        card2.add_row("Thời gian lưu lịch sử phát hiện", self.history_days)

        reset_btn = QPushButton("  Đặt lại tham số AI mặc định")
        reset_btn.setObjectName("cardResetButton")
        reset_btn.setIcon(icon("refresh", "#8E8BA7", 13))
        reset_btn.clicked.connect(self._reset_detection_defaults)
        card2.box.addWidget(reset_btn, 0, Qt.AlignmentFlag.AlignRight)
        card2.box.addStretch(1)

        return make_page(card1, card2)

    # -------------------------------------------------------------------------
    # TAB 5: DỰ ĐOÁN LƯU LƯỢNG (TRAFFIC PREDICTION)
    # -------------------------------------------------------------------------
    def _page_prediction(self) -> QWidget:
        # Card 1: Time Series Model Setup
        card1 = SettingsCard(
            "Mô hình Chuỗi thời gian (Time Series)",
            "trend",
            "#FBBF24",
            "Cấu hình mạng học sâu dự báo xu hướng lưu lượng",
        )
        self.pred_model_combo = combo([
            "LSTM (Long Short-Term Memory Deep Learning)",
            "GRU (Gated Recurrent Unit)",
            "ARIMA (Statistical Time Series)",
            "Transformer Temporal Network",
        ], 240)
        card1.add_row("Mô hình học sâu dự báo", self.pred_model_combo)
        self.pred_horizon_combo = combo(["30 phút tới (Tiêu chuẩn)", "10 phút tới", "1 giờ tới", "3 giờ tới"])
        card1.add_row("Khoảng thời gian dự báo tới", self.pred_horizon_combo)
        self.pred_interval_combo = combo(["5 phút (Khuyên dùng)", "1 phút", "10 phút", "15 phút"])
        card1.add_row("Chu kỳ cập nhật dự đoán", self.pred_interval_combo)
        self.pred_seq_combo = combo(["60 bước (10 phút)", "30 bước", "120 bước", "240 bước"])
        card1.add_row("Độ dài chuỗi quan trắc đầu vào", self.pred_seq_combo)
        card1.box.addStretch(1)

        # Card 2: Visualization & Spikes
        card2 = SettingsCard(
            "Hiển thị & Ngưỡng quá tải",
            "activity",
            "#60A5FA",
            "Cảnh báo sớm và trực quan hóa đường xu hướng AI",
        )
        self.show_confidence_toggle = ToggleButton(True)
        card2.add_row("Vẽ dải khoảng tin cậy 95% (Ribbon)", self.show_confidence_toggle, 0)
        self.show_trend_toggle = ToggleButton(True)
        card2.add_row("Hiển thị dự đoán thời gian thực trên đồ thị", self.show_trend_toggle, 0)
        self.spike_alert_toggle = ToggleButton(True)
        card2.add_row("Cảnh báo sớm nguy cơ quá tải (> 85%)", self.spike_alert_toggle, 0)
        self.cache_pred_toggle = ToggleButton(True)
        card2.add_row("Lưu kết quả dự báo phục vụ kiểm định", self.cache_pred_toggle, 0)

        self.pred_retention = QSpinBox()
        self.pred_retention.setObjectName("settingsSpin")
        self.pred_retention.setRange(1, 365)
        self.pred_retention.setValue(30)
        self.pred_retention.setSuffix(" ngày")
        card2.add_row("Thời gian lưu lịch sử dự báo", self.pred_retention)

        reset_btn = QPushButton("  Đặt lại tham số dự đoán mặc định")
        reset_btn.setObjectName("cardResetButton")
        reset_btn.setIcon(icon("refresh", "#8E8BA7", 13))
        reset_btn.clicked.connect(self._reset_prediction_defaults)
        card2.box.addWidget(reset_btn, 0, Qt.AlignmentFlag.AlignRight)
        card2.box.addStretch(1)

        return make_page(card1, card2)

    # -------------------------------------------------------------------------
    # TAB 6: GIẢM THIỂU RỦI RO (IPS)
    # -------------------------------------------------------------------------
    def _page_ips(self) -> QWidget:
        # Card 1: IPS Enforcement Policy
        card1 = SettingsCard(
            "Chính sách ngăn chặn (IPS Policy)",
            "shield",
            "#FF5B79",
            "Chế độ vận hành và phản ứng tự động khi có mối đe dọa",
        )
        self.ips_mode_combo = combo([
            "Tự động chặn (Active Prevention)",
            "Chỉ cảnh báo & Mô phỏng (Simulation Only)",
            "Xác nhận thủ công (Manual Approval)",
        ], 220)
        card1.add_row("Chế độ vận hành IPS", self.ips_mode_combo)
        self.ips_action_combo = combo([
            "Chặn lưu lượng (Drop IP)",
            "Giới hạn băng thông (Rate Limit)",
            "Chuyển tiếp cách ly (Quarantine)",
        ])
        card1.add_row("Hành động can thiệp mặc định", self.ips_action_combo)
        self.ips_block_time_combo = combo(["30 phút (Tiêu chuẩn)", "5 phút", "15 phút", "1 giờ", "Vĩnh viễn"])
        card1.add_row("Thời gian chặn IP mặc định", self.ips_block_time_combo)
        self.ips_rate_limit_combo = combo(["5 Mbps", "10 Mbps", "2 Mbps", "512 Kbps"])
        card1.add_row("Băng thông giới hạn tối đa", self.ips_rate_limit_combo)
        card1.box.addStretch(1)

        # Card 2: OpenFlow Sync & Audit
        card2 = SettingsCard(
            "Đồng bộ OpenFlow Rule & Nhật ký",
            "lock",
            "#A78BFA",
            "Tự động hóa nạp flow rule và kiểm toán can thiệp",
        )
        self.ips_autosync_toggle = ToggleButton(True)
        card2.add_row("Tự động đẩy Flow Rule xuống Ryu Switch", self.ips_autosync_toggle, 0)
        self.ips_priority_combo = combo(["P1 (Ưu tiên cao nhất - 65535)", "P2 (Ưu tiên trung bình)", "P3 (Thấp)"])
        card2.add_row("Mức ưu tiên rule mặc định", self.ips_priority_combo)
        self.ips_confirm_unlock_toggle = ToggleButton(True)
        card2.add_row("Yêu cầu xác nhận khi mở khóa IP thủ công", self.ips_confirm_unlock_toggle, 0)
        self.ips_audit_toggle = ToggleButton(True)
        card2.add_row("Ghi nhật ký kiểm toán hành động IPS", self.ips_audit_toggle, 0)

        clear_btn = QPushButton("  Xóa toàn bộ rule tạm thời trên Firewall")
        clear_btn.setObjectName("cardResetButton")
        clear_btn.setIcon(icon("trash", "#FF5B79", 13))
        clear_btn.clicked.connect(lambda: self.show_status("✓ Đã xóa 14 Flow Rule tạm thời thành công!", True))
        card2.box.addWidget(clear_btn, 0, Qt.AlignmentFlag.AlignRight)
        card2.box.addStretch(1)

        return make_page(card1, card2)

    # -------------------------------------------------------------------------
    # FEEDBACK & TEST ACTIONS
    # -------------------------------------------------------------------------
    def _test_ryu_conn(self) -> None:
        self.ryu_status_lbl.setText("⏳ Đang ping Ryu Controller...")
        self.ryu_status_lbl.setStyleSheet("color: #FBBF24; font-size: 12.5px; font-weight: 600;")
        QTimer.singleShot(600, self._ryu_success)

    def _ryu_success(self) -> None:
        self.ryu_status_lbl.setText("● Kết nối Ryu Controller thành công (1.2ms)")
        self.ryu_status_lbl.setStyleSheet("color: #34D399; font-size: 12.5px; font-weight: 600;")
        self.show_status("✓ Đã kết nối thành công tới Ryu SDN Controller!", True)

    def _test_db_conn(self) -> None:
        self.db_status_lbl.setText("⏳ Đang kiểm tra Database...")
        self.db_status_lbl.setStyleSheet("color: #FBBF24; font-size: 12.5px; font-weight: 600;")
        QTimer.singleShot(600, self._db_success)

    def _db_success(self) -> None:
        self.db_status_lbl.setText("● Kết nối CSDL thành công (ai_network_ids)")
        self.db_status_lbl.setStyleSheet("color: #34D399; font-size: 12.5px; font-weight: 600;")
        self.show_status("✓ Đã kết nối thành công tới cơ sở dữ liệu PostgreSQL!", True)

    def _reset_detection_defaults(self) -> None:
        self.threshold_slider.setValue(70)
        self.sensitivity_slider.setValue(80)
        self.detect_model_combo.setCurrentIndex(0)
        self.show_status("✓ Đã đặt lại tham số AI về mặc định (Threshold: 0.70, Sensitivity: 0.80)!", True)

    def _reset_prediction_defaults(self) -> None:
        self.pred_model_combo.setCurrentIndex(0)
        self.pred_horizon_combo.setCurrentIndex(0)
        self.pred_interval_combo.setCurrentIndex(0)
        self.show_status("✓ Đã đặt lại tham số dự đoán về mặc định (LSTM 30m)!", True)

    def restore_defaults(self) -> None:
        self.app_name_input.setText("AI Network IDS/IPS Platform")
        self.version_input.setText("v1.2.0 (Cybera SOC Edition)")
        self.lang_combo.setCurrentIndex(0)
        self.autostart_toggle.setChecked(True)
        self.autoupdate_toggle.setChecked(True)
        self.theme_combo.setCurrentIndex(0)
        self.font_scale_combo.setCurrentIndex(0)
        self._reset_detection_defaults()
        self._reset_prediction_defaults()
        self.show_status("✓ Đã khôi phục toàn bộ cấu hình gốc của hệ thống thành công!", True)

    def show_status(self, text: str, is_success: bool = True) -> None:
        self.status.setText(text)
        color = "#34D399" if is_success else "#FF5B79"
        self.status.setStyleSheet(f"color: {color}; font-size: 12.5px; font-weight: 700;")
        QTimer.singleShot(3500, lambda: self.status.setText(""))
