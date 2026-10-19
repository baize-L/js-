"""Mars desktop: PySide6/Qt cross-platform interface. Original networking in xxxx.py."""
from __future__ import annotations
import contextlib
import io
import json
import platform
import sys
from pathlib import Path

import requests
from PySide6.QtCore import Qt, QObject, QThread, Signal, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QFileDialog,
    QMessageBox, QStackedWidget, QScrollArea, QSizePolicy, QGraphicsDropShadowEffect,
    QButtonGroup, QCheckBox,
)
from xxxx import API, PlatformError, apiMain, bundled_bank_path

ACTIVITIES = {
    "查询项目和活动（不答题）": "list",
    "自动完成未做项目": "auto",
    "顺序练习": "sequential",
    "随机练习": "random",
    "模拟考试": "mock",
    "正式考试": "formal",
}
ACCENTS = ["#4385FF", "#8B6BF0", "#13A894", "#E98447", "#D95C9B"]

class SignalWriter(io.TextIOBase):
    def __init__(self, signal):
        self.signal = signal
        self.buffer = ""
    def write(self, s):
        self.buffer += s
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
                self.signal.emit(line)
        return len(s)
    def flush(self):
        if self.buffer.strip():
            self.signal.emit(self.buffer)
        self.buffer = ""

class TaskWorker(QObject):
    log = Signal(str)
    finished = Signal(object, str)
    authenticated = Signal(object)
    def __init__(self, args, client):
        super().__init__()
        self.args = args
        self.client = client
    def run(self):
        username, password, school, activity, score, duration, bank = self.args
        session = self.client.session if self.client else requests.Session()
        writer = SignalWriter(self.log)
        try:
            with contextlib.redirect_stdout(writer):
                result = apiMain(
                    "江苏省第十五届大学生安全知识竞赛", school,
                    username, password, None, "deimos", "", "", session,
                    activity=activity, execute=activity != "list",
                    target_score=score, duration_seconds=duration, bank_path=bank,
                    client=self.client, on_authenticated=self.authenticated.emit,
                )
            writer.flush()
            self.finished.emit(result, "执行完毕，登录状态已保留")
        except Exception as exc:
            writer.flush()
            if isinstance(exc, PlatformError) and exc.status == 401:
                try:
                    if self.client:
                        self.client.p = ""
                        self.client.session.close()
                except Exception:
                    pass
                self.finished.emit(None, f"登录失效：{exc}")
            else:
                self.finished.emit(self.client, f"执行失败：{type(exc).__name__}: {exc}")
        finally:
            if self.client is None:
                # apiMain owns its session when authenticated; don't invalidate it.
                pass

class GlassCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("glassCard")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(12, 24, 50, 18))
        self.setGraphicsEffect(shadow)

class MarsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mars 竞赛助手 · Qt Desktop")
        self.resize(1210, 800)
        self.setMinimumSize(920, 650)
        self.client = None
        self.running = False
        self.logs = []
        self.page = "overview"
        self.theme = "light"
        self.accent = ACCENTS[0]
        self.thread = None
        self.worker = None
        self._build_shell()
        self._show_page("overview")
        self._apply_theme()

    def _label(self, text, kind="body"):
        label = QLabel(text)
        label.setObjectName(kind)
        label.setWordWrap(True)
        return label

    def _button(self, text, slot=None, primary=False):
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setProperty("primary", primary)
        if slot:
            b.clicked.connect(slot)
        return b

    def _column(self, gap=12):
        lay = QVBoxLayout()
        lay.setSpacing(gap)
        return lay

    def _card(self, title, hint=None):
        card = GlassCard()
        lay = self._column(10)
        lay.setContentsMargins(22, 19, 22, 20)
        lay.addWidget(self._label(title, "sectionTitle"))
        if hint:
            lay.addWidget(self._label(hint, "muted"))
        card.setLayout(lay)
        return card, lay

    def _build_shell(self):
        shell = QWidget()
        shell.setObjectName("shell")
        self.setCentralWidget(shell)
        root = QHBoxLayout(shell)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(231)
        root.addWidget(sidebar)
        side = self._column(9)
        side.setContentsMargins(15, 25, 15, 18)
        sidebar.setLayout(side)
        brand = self._label("✦  Mars Desktop", "brand")
        side.addWidget(brand)
        side.addWidget(self._label("智能竞赛 · 专注工作台", "muted"))
        side.addSpacing(25)
        self.nav = {}
        for page, icon, title in [
            ("overview", "▦", "工作台概览"),
            ("query", "⌕", "活动查询"),
            ("exam", "▤", "练习与考试"),
            ("logs", "☷", "运行日志"),
            ("settings", "⚙", "偏好设置"),
        ]:
            b = self._button(f"{icon}    {title}", lambda _, p=page: self._show_page(p))
            b.setObjectName("navButton")
            b.setCheckable(True)
            b.setMinimumHeight(46)
            side.addWidget(b)
            self.nav[page] = b
        side.addStretch(1)
        info, il = self._card("●  桌面端运行", "Windows  /  macOS")
        info.setObjectName("sidebarFoot")
        side.addWidget(info)
        workspace = QWidget()
        workspace.setObjectName("workspace")
        root.addWidget(workspace, 1)
        wlay = self._column(14)
        wlay.setContentsMargins(2, 10, 2, 2)
        workspace.setLayout(wlay)
        header = QHBoxLayout()
        heading = self._column(4)
        self.heading = self._label("工作台概览", "pageTitle")
        self.subtitle = self._label("为你的竞赛任务提供统一入口", "muted")
        heading.addWidget(self.heading)
        heading.addWidget(self.subtitle)
        header.addLayout(heading, 1)
        self.theme_shortcut = self._button("☾  切换主题", self._toggle_theme)
        header.addWidget(self.theme_shortcut)
        wlay.addLayout(header)
        self.stack = QStackedWidget()
        wlay.addWidget(self.stack, 1)
        self.pages = {}
        for p in ("overview", "query", "exam", "logs", "settings"):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setObjectName("pageScroll")
            body = QWidget()
            body.setObjectName("pageBody")
            v = self._column(16)
            v.setContentsMargins(0, 4, 12, 12)
            body.setLayout(v)
            scroll.setWidget(body)
            self.stack.addWidget(scroll)
            self.pages[p] = (scroll, v)
        self._render_workspaces()
        self._render_logs()
        self._render_settings()

    def _render_workspaces(self):
        for page in ("overview", "query", "exam"):
            v = self.pages[page][1]
            if page == "overview":
                stats = QHBoxLayout()
                self.status_value = None
                for title, val, hint in [
                    ("运行状态", "● 准备就绪", "本地安全工作台"),
                    ("登录会话", "未登录", "同账号可复用会话"),
                    ("运行模式", "6 种模式", "查询 · 练习 · 考试"),
                ]:
                    card, content = self._card(title)
                    lab = self._label(val, "statValue")
                    content.addWidget(lab)
                    content.addWidget(self._label(hint, "muted"))
                    if title == "运行状态": self.status_value = lab
                    if title == "登录会话": self.session_value = lab
                    stats.addWidget(card, 1)
                v.addLayout(stats)
            if page == "query":
                text, lay = self._card("活动查询", "查询可用活动，不会自动提交答题内容。")
                v.addWidget(text)
            if page == "exam":
                text, lay = self._card("练习与考试", "请遵守平台规则；目标分数和用时选项仅用于支持的模式。")
                v.addWidget(text)
            # Reuse one main form, not duplicate live credentials across pages.
            if page == "overview":
                self.form_card, self.form_layout = self._card("账号与任务配置", "首次登录填写密码，已认证的相同账号可留空复用会话。")
                v.addWidget(self.form_card)
                grid = QGridLayout()
                grid.setHorizontalSpacing(18)
                grid.setVerticalSpacing(12)
                self.username = QLineEdit(); self.username.setPlaceholderText("竞赛平台账号")
                self.password = QLineEdit(); self.password.setPlaceholderText("仅本次登录使用")
                self.password.setEchoMode(QLineEdit.Password)
                self.school = QLineEdit(); self.school.setPlaceholderText("学校名称")
                self.score = QLineEdit(); self.score.setPlaceholderText("可选，填写整数")
                self.duration = QLineEdit(); self.duration.setPlaceholderText("可选，单位秒")
                self.bank = QLineEdit(); self.bank.setPlaceholderText("默认使用随程序附带的题库")
                inputs = [
                    ("账号", self.username), ("密码", self.password),
                    ("学校", self.school), ("目标分数（考试）", self.score),
                    ("最短用时（秒）", self.duration), ("自定义题库路径", self.bank),
                ]
                for i, (label, field) in enumerate(inputs):
                    cell = self._column(6)
                    cell.addWidget(self._label(label, "fieldLabel"))
                    cell.addWidget(field)
                    grid.addLayout(cell, i // 2, i % 2)
                browse = self._button("选择 Excel 题库", self._select_bank)
                grid.addWidget(browse, 3, 1)
                self.form_layout.addLayout(grid)
                self.activity = QComboBox()
                self.activity.addItems(ACTIVITIES)
                self.activity.currentTextChanged.connect(self._activity_changed)
                actions = QHBoxLayout()
                actions.addWidget(self.activity, 1)
                self.start_button = self._button("查询项目和活动", self._start, primary=True)
                actions.addWidget(self.start_button)
                self.form_layout.addLayout(actions)
                self._activity_changed()
                note, lay = self._card("实时活动日志", "日志只保存在当前应用会话中")
                self.inline_log = QTextEdit()
                self.inline_log.setReadOnly(True)
                self.inline_log.setMinimumHeight(175)
                lay.addWidget(self.inline_log)
                self.state_label = self._label("准备就绪 · 输入账号信息后查询", "muted")
                lay.addWidget(self.state_label)
                v.addWidget(note, 1)
                v.addStretch()
            else:
                info, layout = self._card("返回工作台进行配置", "为保证账号和会话一致，所有输入在工作台统一管理。")
                layout.addWidget(self._button("前往工作台  →", lambda: self._show_page("overview"), True))
                v.addWidget(info)
                v.addStretch()

    def _render_logs(self):
        v = self.pages["logs"][1]
        card, lay = self._card("本次运行日志", "可实时查看执行状态；关闭应用后日志自动清除。")
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self._button("清除日志", self._clear_logs))
        lay.addLayout(row)
        self.full_log = QTextEdit()
        self.full_log.setReadOnly(True)
        self.full_log.setMinimumHeight(460)
        lay.addWidget(self.full_log)
        v.addWidget(card)

    def _render_settings(self):
        v = self.pages["settings"][1]
        card, lay = self._card("外观与主题", "切换玻璃质感浅色、深色外观；不会重置账号和执行状态。")
        row = QHBoxLayout()
        self.light_btn = self._button("☀  浅色")
        self.dark_btn = self._button("☾  深色")
        self.system_btn = self._button("◈  跟随系统")
        for b, mode in ((self.light_btn, "light"), (self.dark_btn, "dark"), (self.system_btn, "system")):
            b.setCheckable(True)
            b.clicked.connect(lambda _, m=mode: self._set_theme(m))
            row.addWidget(b)
        lay.addLayout(row)
        lay.addWidget(self._label("强调色", "fieldLabel"))
        colors = QHBoxLayout()
        self.accent_buttons = []
        for color in ACCENTS:
            b = self._button("●")
            b.setFixedSize(49, 42)
            b.setStyleSheet(f"color: {color}; font-size: 23px;")
            b.clicked.connect(lambda _, c=color: self._set_accent(c))
            colors.addWidget(b)
            self.accent_buttons.append(b)
        colors.addStretch()
        lay.addLayout(colors)
        v.addWidget(card)
        pref, pl = self._card("一般设置", "本地应用界面偏好")
        self.notifications = QCheckBox("启用应用内通知（执行结果提示）")
        self.notifications.setChecked(True)
        pl.addWidget(self.notifications)
        pl.addWidget(self._label("语言：简体中文    |    系统：Windows / macOS", "muted"))
        v.addWidget(pref)
        about, al = self._card("关于 Mars Desktop", "PySide6 + Qt Widgets 桌面架构")
        al.addWidget(self._label("业务模块：原 xxxx.py · 本地题库 · 当前启动期间会话复用", "muted"))
        al.addWidget(self._label("视觉效果通过 Qt 的半透明背景、渐变和阴影实现；系统级实时背景模糊需要单独的原生集成。", "muted"))
        v.addWidget(about)
        v.addStretch()

    def _show_page(self, page):
        if page == "settings" and self.running:
            # Qt settings are safe to display while running; no form reconstruction.
            pass
        self.page = page
        titles = {"overview": "工作台概览", "query": "活动查询", "exam": "练习与考试", "logs": "运行日志", "settings": "偏好设置"}
        self.heading.setText(titles[page])
        self.subtitle.setText("Mars 竞赛助手   /   清晰、专注、跨平台")
        self.stack.setCurrentWidget(self.pages[page][0])
        for p, b in self.nav.items():
            b.setChecked(p == page)

    def _set_theme(self, theme):
        self.theme = theme
        self._apply_theme()

    def _toggle_theme(self):
        self._set_theme("light" if self._dark() else "dark")

    def _set_accent(self, color):
        self.accent = color
        self._apply_theme()

    def _dark(self):
        if self.theme == "system":
            return QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        return self.theme == "dark"

    def _apply_theme(self):
        dark = self._dark()
        accent = self.accent
        bg, side, card, field, text, muted, border = (
            ("#0D1525", "#15253ABF", "#20334ACC", "#152238", "#EEF5FF", "#A4B5D0", "#465C7680") if dark else
            ("#EAF1FB", "#E4ECF5D9", "#FFFFFFDC", "#F5F8FE", "#18253D", "#728099", "#D2DCEBE0")
        )
        self.setStyleSheet(f"""
            QWidget#shell {{background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {bg}, stop:1 {'#182B46' if dark else '#DAE8FA'});}}
            QWidget#workspace, QWidget#pageBody, QScrollArea#pageScroll {{background: transparent;}}
            QFrame#sidebar {{background-color: {side}; border: 1px solid {border}; border-radius: 22px;}}
            QFrame#glassCard {{background-color: {card}; border: 1px solid {border}; border-radius: 18px;}}
            QFrame#sidebarFoot {{background-color: {card}; border: 1px solid {border}; border-radius: 14px;}}
            QLabel {{background: transparent; color: {text}; font-family: 'Segoe UI', 'PingFang SC', sans-serif; font-size: 13px;}}
            QLabel#brand {{font-size: 19px; font-weight: 800; color: {accent};}}
            QLabel#pageTitle {{font-size: 27px; font-weight: 800;}}
            QLabel#sectionTitle {{font-size: 16px; font-weight: 700;}}
            QLabel#statValue {{font-size: 22px; font-weight: 800;}}
            QLabel#muted {{font-size: 12px; color: {muted};}}
            QLabel#fieldLabel {{font-size: 12px; font-weight: 600; color: {muted};}}
            QPushButton {{background-color: {field}; color: {text}; border: 1px solid {border}; border-radius: 11px; padding: 11px 15px; font-size: 13px; font-weight: 600;}}
            QPushButton:hover {{border-color: {accent}; background-color: {'#283F5B' if dark else '#DFEBFB'};}}
            QPushButton:disabled {{color: {muted};}}
            QPushButton[primary=true] {{background-color: {accent}; color: white; border: 1px solid {accent};}}
            QPushButton#navButton {{text-align: left; border: none; background: transparent; padding-left: 15px;}}
            QPushButton#navButton:checked {{background-color: {accent}; color: white; border-radius: 11px;}}
            QLineEdit, QComboBox, QTextEdit {{background-color: {field}; color: {text}; border: 1px solid {border}; border-radius: 10px; padding: 10px; selection-background-color: {accent};}}
            QLineEdit:focus, QComboBox:focus {{border: 1px solid {accent};}}
            QComboBox QAbstractItemView {{background-color: {field}; color: {text}; selection-background-color: {accent};}}
            QTextEdit {{font-family: 'Cascadia Code', 'Menlo', monospace;}}
            QScrollBar:vertical {{background: transparent; width: 9px;}}
            QScrollBar::handle:vertical {{background: {border}; border-radius: 4px; min-height: 18px;}}
            QCheckBox {{color: {text}; background: transparent;}}
        """)
        self.light_btn.setChecked(self.theme == "light")
        self.dark_btn.setChecked(self.theme == "dark")
        self.system_btn.setChecked(self.theme == "system")
        self.theme_shortcut.setText("☀  浅色模式" if dark else "☾  深色模式")

    def _select_bank(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 Excel 题库", "", "Excel 文件 (*.xlsx)")
        if path: self.bank.setText(path)

    def _activity_changed(self, *_):
        activity = ACTIVITIES[self.activity.currentText()]
        is_exam = activity in ("mock", "formal")
        self.score.setEnabled(is_exam)
        self.duration.setEnabled(is_exam)
        self.start_button.setText("查询项目和活动" if activity == "list" else f"开始{self.activity.currentText()}")

    @staticmethod
    def _optional_int(value, label):
        if not value.strip(): return None
        try: result = int(value.strip())
        except ValueError: raise ValueError(f"{label}必须是整数")
        if result < 0: raise ValueError(f"{label}不能为负数")
        return result

    def _start(self):
        if self.running: return
        activity = ACTIVITIES[self.activity.currentText()]
        username = self.username.text().strip()
        password = self.password.text()
        school = self.school.text().strip()
        cached = self.client
        reuse = cached is not None and cached.u == username and cached.s == school and not password
        bank = Path(self.bank.text()).expanduser() if self.bank.text().strip() else bundled_bank_path()
        try:
            if not username or not school or (not reuse and not password):
                raise ValueError("首次登录或更换账号、学校时，请填写账号、密码和学校")
            if not bank.is_file(): raise ValueError("找不到题库文件")
            score = self._optional_int(self.score.text(), "目标分数") if activity in ("mock", "formal") else None
            duration = self._optional_int(self.duration.text(), "目标用时") if activity in ("mock", "formal") else None
            if duration == 0: raise ValueError("目标用时至少为 1 秒")
        except ValueError as exc:
            QMessageBox.warning(self, "输入有误", str(exc))
            return
        if not reuse and cached is not None:
            cached.p = ""
            cached.session.close()
            self.client = None
        self.password.clear()
        self.running = True
        self.start_button.setEnabled(False)
        self.state_label.setText("正在连接平台…")
        self.status_value.setText("● 执行中")
        self._append("开始：" + self.activity.currentText())
        self.thread = QThread(self)
        self.worker = TaskWorker((username, password, school, activity, score, duration, bank), cached if reuse else None)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self._append)
        self.worker.authenticated.connect(self._authenticated)
        self.worker.finished.connect(self._finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _authenticated(self, client):
        self.client = client
        self.session_value.setText("已登录")

    def _finished(self, client, message):
        self.client = client
        self.running = False
        self.start_button.setEnabled(True)
        self.status_value.setText("● 准备就绪" if client is not None else "● 待登录")
        self.session_value.setText("已保持" if client is not None else "未登录")
        self.state_label.setText(message)
        self._append(message)
        if self.notifications.isChecked() and message.startswith("执行失败"):
            QMessageBox.warning(self, "任务结果", message)

    def _append(self, line):
        self.logs.append(line)
        self.inline_log.append(line)
        self.full_log.append(line)

    def _clear_logs(self):
        self.logs.clear()
        self.inline_log.clear()
        self.full_log.clear()

    def closeEvent(self, event):
        if self.running:
            QMessageBox.information(self, "任务运行中", "请先等待当前任务完成，再关闭窗口。")
            event.ignore()
        else:
            if self.client:
                self.client.p = ""
                self.client.session.close()
            event.accept()

def self_test(report_path=None):
    from xxxx import AnswerResolver
    import ddddocr
    resolver = AnswerResolver(bundled_bank_path())
    if not resolver.bank: raise RuntimeError("内置题库为空")
    ddddocr.DdddOcr(show_ad=False)
    app = QApplication.instance() or QApplication(sys.argv)
    window = MarsWindow()
    window.show()
    app.processEvents()
    window.close()
    if report_path:
        Path(report_path).write_text(json.dumps({
            "ok": True, "frozen": bool(getattr(sys, "frozen", False)),
            "system": platform.system(), "architecture": platform.machine(),
            "bank_questions": len(resolver.bank), "window_created": True,
            "ocr_model_loaded": True, "network_used": False,
            "ui_framework": "PySide6 Qt Widgets",
        }, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        report = Path(sys.argv[sys.argv.index("--self-test-report") + 1]) if "--self-test-report" in sys.argv else None
        self_test(report)
    else:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        win = MarsWindow()
        win.show()
        sys.exit(app.exec())
