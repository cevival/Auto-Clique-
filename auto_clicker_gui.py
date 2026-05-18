#!/usr/bin/env python3
"""AutoClic - Interface graphique améliorée.

Fonctionnalités :
- Intervalle paramétrable (h / min / s / ms) ou CPS (clics par seconde)
- Bouton souris : gauche / droite / milieu
- Type de clic : simple / double
- Position : suivre la souris ou position fixe (capturée via F8)
- Variation aléatoire de l'intervalle (humanisation)
- Compteur de clics live, bouton de réinitialisation
- Hotkey toggle configurable (capture clavier)
- Sauvegarde / chargement automatique des paramètres (JSON)
- Tray icon, "toujours au-dessus", confirmation à la fermeture si actif
"""
import json
import os
import random
import sys
import threading
import time

from PyQt5.QtCore import QEvent, Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
from pynput.keyboard import Key, KeyCode, Listener
from pynput.mouse import Button, Controller

APP_NAME = "AutoClic"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "autoclic_config.json")

BUTTON_MAP = {
    "Gauche": Button.left,
    "Droite": Button.right,
    "Milieu": Button.middle,
}

UNIT_FACTORS_MS = {
    "ms": 1.0,
    "s": 1000.0,
    "min": 60_000.0,
    "h": 3_600_000.0,
}


# ---------------------------------------------------------------------------
# Helpers clavier
# ---------------------------------------------------------------------------
def parse_key(s: str):
    """Convertit une chaîne en touche pynput (Key ou KeyCode)."""
    s = (s or "").strip()
    if not s:
        return KeyCode.from_char("²")
    if s.startswith("vk") and s[2:].isdigit():
        return KeyCode.from_vk(int(s[2:]))
    if len(s) == 1:
        return KeyCode.from_char(s)
    name = s.lower()
    if hasattr(Key, name):
        return getattr(Key, name)
    return KeyCode.from_char("²")


def key_to_str(key) -> str:
    """Convertit une touche pynput en chaîne lisible et re-parsable."""
    if isinstance(key, KeyCode):
        if key.char:
            return key.char
        return f"vk{key.vk}" if key.vk else "?"
    if isinstance(key, Key):
        return key.name
    return str(key)


def keys_equal(a, b) -> bool:
    if a is None or b is None:
        return False
    if isinstance(a, Key) and isinstance(b, Key):
        return a == b
    if isinstance(a, KeyCode) and isinstance(b, KeyCode):
        if a.char and b.char:
            return a.char == b.char
        if a.vk and b.vk:
            return a.vk == b.vk
    return key_to_str(a) == key_to_str(b)


# ---------------------------------------------------------------------------
# Thread de clic
# ---------------------------------------------------------------------------
class ClickerThread(threading.Thread):
    """Thread de clic avec timing précis (perf_counter) et arrêt réactif."""

    def __init__(self, params, run_event, stop_event, counter, on_target_reached):
        super().__init__(daemon=True)
        self.params = params
        self.run_event = run_event
        self.stop_event = stop_event
        self.counter = counter
        self.on_target_reached = on_target_reached
        self.mouse = Controller()

    def _next_delay(self) -> float:
        base = self.params["interval_ms"]
        jitter = self.params["jitter_ms"]
        if jitter > 0:
            base = max(1.0, base + random.uniform(-jitter, jitter))
        return base / 1000.0

    def run(self):
        button = self.params["button"]
        clicks_per_action = 2 if self.params["double_click"] else 1
        target = self.params["target_clicks"]
        fixed_pos = self.params["fixed_position"]

        next_time = time.perf_counter()
        while not self.stop_event.is_set():
            self.run_event.wait()
            if self.stop_event.is_set():
                break

            with self.counter["lock"]:
                if target > 0 and self.counter["n"] >= target:
                    self.run_event.clear()
                    self.on_target_reached()
                    next_time = time.perf_counter()
                    continue

            if fixed_pos is not None:
                self.mouse.position = fixed_pos

            self.mouse.click(button, clicks_per_action)
            with self.counter["lock"]:
                self.counter["n"] += 1

            next_time += self._next_delay()
            sleep_for = next_time - time.perf_counter()
            if sleep_for > 0:
                end = time.perf_counter() + sleep_for
                while not self.stop_event.is_set():
                    remaining = end - time.perf_counter()
                    if remaining <= 0:
                        break
                    time.sleep(min(remaining, 0.05))
            else:
                # On a pris du retard, on recadre pour éviter une rafale
                next_time = time.perf_counter()


# ---------------------------------------------------------------------------
# Event Qt pour invoquer du code GUI depuis un thread
# ---------------------------------------------------------------------------
class _CallEvent(QEvent):
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, callback):
        super().__init__(self.EVENT_TYPE)
        self.callback = callback


# ---------------------------------------------------------------------------
# Fenêtre principale
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumWidth(440)

        self._capturing_hotkey = False
        self._capturing_position = False
        self.toggle_key_parsed = parse_key("²")
        self.fixed_position = None
        self._suppress_save = True

        self._build_ui()
        self._build_tray()

        self.run_event = threading.Event()
        self.stop_event = threading.Event()
        self.counter = {"n": 0, "lock": threading.Lock()}
        self.clicker = None

        self.klistener = Listener(on_press=self._on_global_key)
        self.klistener.daemon = True
        self.klistener.start()

        self.counter_timer = QTimer(self)
        self.counter_timer.setInterval(100)
        self.counter_timer.timeout.connect(self._refresh_counter_label)
        self.counter_timer.start()

        self._load_config()
        self._suppress_save = False
        self._update_position_label()
        self._update_hotkey_label()

    # ------------------------------------------------------------------
    # Construction UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)

        gb_rate = QGroupBox("Cadence")
        form_rate = QFormLayout(gb_rate)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Intervalle", "CPS (clics/seconde)"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        form_rate.addRow("Mode :", self.mode_combo)

        self.rate_stack = QStackedWidget()

        page_interval = QWidget()
        h_interval = QHBoxLayout(page_interval)
        h_interval.setContentsMargins(0, 0, 0, 0)
        self.interval_value = QDoubleSpinBox()
        self.interval_value.setRange(0.001, 1_000_000.0)
        self.interval_value.setDecimals(3)
        self.interval_value.setValue(100.0)
        self.interval_unit = QComboBox()
        self.interval_unit.addItems(list(UNIT_FACTORS_MS.keys()))
        self.interval_unit.setCurrentText("ms")
        h_interval.addWidget(self.interval_value, 1)
        h_interval.addWidget(self.interval_unit)
        self.rate_stack.addWidget(page_interval)

        page_cps = QWidget()
        h_cps = QHBoxLayout(page_cps)
        h_cps.setContentsMargins(0, 0, 0, 0)
        self.cps_value = QDoubleSpinBox()
        self.cps_value.setRange(0.01, 1000.0)
        self.cps_value.setDecimals(2)
        self.cps_value.setValue(10.0)
        h_cps.addWidget(self.cps_value, 1)
        h_cps.addWidget(QLabel("clics/s"))
        self.rate_stack.addWidget(page_cps)

        form_rate.addRow("Vitesse :", self.rate_stack)

        h_jitter = QHBoxLayout()
        self.jitter_value = QDoubleSpinBox()
        self.jitter_value.setRange(0.0, 100_000.0)
        self.jitter_value.setDecimals(2)
        self.jitter_value.setValue(0.0)
        h_jitter.addWidget(self.jitter_value, 1)
        h_jitter.addWidget(QLabel("ms (±)"))
        form_rate.addRow("Variation aléatoire :", h_jitter)

        root.addWidget(gb_rate)

        gb_click = QGroupBox("Clic")
        form_click = QFormLayout(gb_click)

        self.button_combo = QComboBox()
        self.button_combo.addItems(list(BUTTON_MAP.keys()))
        form_click.addRow("Bouton souris :", self.button_combo)

        self.double_click_cb = QCheckBox("Double clic")
        form_click.addRow("", self.double_click_cb)

        self.clicks_count = QSpinBox()
        self.clicks_count.setRange(0, 10_000_000)
        self.clicks_count.setValue(0)
        self.clicks_count.setSuffix("  (0 = infini)")
        form_click.addRow("Nombre de clics :", self.clicks_count)

        root.addWidget(gb_click)

        gb_pos = QGroupBox("Position")
        v_pos = QVBoxLayout(gb_pos)

        self.follow_mouse_cb = QCheckBox("Suivre la souris (position courante)")
        self.follow_mouse_cb.setChecked(True)
        self.follow_mouse_cb.toggled.connect(self._update_position_label)
        v_pos.addWidget(self.follow_mouse_cb)

        h_pos_btn = QHBoxLayout()
        self.pos_label = QLabel("Position fixe : —")
        self.pos_label.setObjectName("pos_label")
        self.capture_pos_btn = QPushButton("Capturer (F8)")
        self.capture_pos_btn.setObjectName("capture_pos_btn")
        self.capture_pos_btn.clicked.connect(self._start_capture_position)
        self.clear_pos_btn = QPushButton("Effacer")
        self.clear_pos_btn.setObjectName("clear_pos_btn")
        self.clear_pos_btn.clicked.connect(self._clear_position)
        h_pos_btn.addWidget(self.pos_label, 1)
        h_pos_btn.addWidget(self.capture_pos_btn)
        h_pos_btn.addWidget(self.clear_pos_btn)
        v_pos.addLayout(h_pos_btn)

        root.addWidget(gb_pos)

        gb_ctrl = QGroupBox("Contrôle")
        form_ctrl = QFormLayout(gb_ctrl)

        h_hk = QHBoxLayout()
        self.hotkey_label = QLabel("²")
        self.hotkey_label.setObjectName("hotkey_label")
        self.capture_hotkey_btn = QPushButton("Changer…")
        self.capture_hotkey_btn.setObjectName("capture_hotkey_btn")
        self.capture_hotkey_btn.clicked.connect(self._start_capture_hotkey)
        h_hk.addWidget(self.hotkey_label, 1)
        h_hk.addWidget(self.capture_hotkey_btn)
        form_ctrl.addRow("Touche démarrer/arrêter :", h_hk)

        self.always_on_top_cb = QCheckBox("Toujours au-dessus")
        self.always_on_top_cb.toggled.connect(self._toggle_always_on_top)
        form_ctrl.addRow("", self.always_on_top_cb)

        root.addWidget(gb_ctrl)

        action_row = QHBoxLayout()
        self.start_btn = QPushButton("Démarrer")
        self.start_btn.setObjectName("start_btn")
        self.start_btn.setProperty("running", "false")
        self.start_btn.clicked.connect(self.start_stop)
        self.tray_btn = QPushButton("Minimiser dans la zone de notification")
        self.tray_btn.setObjectName("tray_btn")
        self.tray_btn.clicked.connect(self.hide_to_tray)
        action_row.addWidget(self.start_btn, 1)
        action_row.addWidget(self.tray_btn)
        root.addLayout(action_row)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Prêt")
        self.status_label.setObjectName("status_label")
        self.counter_label = QLabel("Clics : 0")
        self.counter_label.setObjectName("counter_label")
        self.reset_btn = QPushButton("Réinitialiser")
        self.reset_btn.setObjectName("reset_btn")
        self.reset_btn.clicked.connect(self._reset_counter)
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.counter_label)
        status_row.addWidget(self.reset_btn)
        root.addLayout(status_row)

        for w in (self.interval_value, self.cps_value, self.jitter_value, self.clicks_count):
            w.valueChanged.connect(self._save_config)
        self.interval_unit.currentTextChanged.connect(self._save_config)
        self.button_combo.currentTextChanged.connect(self._save_config)
        self.double_click_cb.toggled.connect(self._save_config)
        self.follow_mouse_cb.toggled.connect(self._save_config)
        self.always_on_top_cb.toggled.connect(self._save_config)
        self.mode_combo.currentIndexChanged.connect(self._save_config)

        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f4f6fa;
                color: #1f2937;
                font-family: 'Segoe UI', 'Inter', Arial, sans-serif;
                font-size: 10pt;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #e3e8f0;
                border-radius: 10px;
                margin-top: 16px;
                padding: 14px 12px 10px 12px;
                font-weight: 600;
                color: #334155;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                background: #f4f6fa;
                color: #1e3a8a;
            }
            QLabel { color: #1f2937; }
            QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {
                background: #ffffff;
                color: #111827;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                min-height: 22px;
                selection-background-color: #1976d2;
                selection-color: #ffffff;
            }
            QSpinBox:focus, QDoubleSpinBox:focus,
            QComboBox:focus, QLineEdit:focus {
                border: 1px solid #1976d2;
            }
            QSpinBox:disabled, QDoubleSpinBox:disabled,
            QComboBox:disabled, QLineEdit:disabled {
                background: #f1f5f9;
                color: #94a3b8;
            }
            QComboBox::drop-down { border: none; width: 18px; }
            QComboBox QAbstractItemView {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                selection-background-color: #1976d2;
                selection-color: #ffffff;
                outline: 0;
            }
            QCheckBox { spacing: 8px; color: #1f2937; }
            QCheckBox::indicator {
                width: 16px; height: 16px;
                border: 1px solid #94a3b8;
                border-radius: 4px;
                background: #ffffff;
            }
            QCheckBox::indicator:hover { border-color: #1976d2; }
            QCheckBox::indicator:checked {
                background: #1976d2;
                border-color: #1976d2;
                image: none;
            }
            QPushButton {
                background: #1976d2;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #1565c0; }
            QPushButton:pressed { background: #0d47a1; }
            QPushButton:disabled {
                background: #cbd5e1;
                color: #64748b;
            }
            QPushButton#tray_btn,
            QPushButton#capture_pos_btn,
            QPushButton#clear_pos_btn,
            QPushButton#capture_hotkey_btn,
            QPushButton#reset_btn {
                background: #ffffff;
                color: #1976d2;
                border: 1px solid #1976d2;
            }
            QPushButton#tray_btn:hover,
            QPushButton#capture_pos_btn:hover,
            QPushButton#clear_pos_btn:hover,
            QPushButton#capture_hotkey_btn:hover,
            QPushButton#reset_btn:hover {
                background: #e3f2fd;
            }
            QPushButton#tray_btn:disabled,
            QPushButton#capture_pos_btn:disabled,
            QPushButton#clear_pos_btn:disabled,
            QPushButton#capture_hotkey_btn:disabled,
            QPushButton#reset_btn:disabled {
                background: #f1f5f9;
                color: #94a3b8;
                border-color: #cbd5e1;
            }
            QPushButton#start_btn {
                background: #16a34a;
                font-size: 11pt;
                padding: 10px 18px;
            }
            QPushButton#start_btn:hover { background: #15803d; }
            QPushButton#start_btn[running="true"] {
                background: #dc2626;
            }
            QPushButton#start_btn[running="true"]:hover {
                background: #b91c1c;
            }
            QLabel#status_label {
                color: #475569;
                font-style: italic;
            }
            QLabel#counter_label {
                color: #1e3a8a;
                font-weight: 700;
                padding: 2px 10px;
                background: #e0e7ff;
                border-radius: 12px;
            }
            QLabel#hotkey_label, QLabel#pos_label {
                background: #f1f5f9;
                color: #0f172a;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 4px 10px;
                font-family: 'Consolas', 'Cascadia Mono', monospace;
            }
            QMenu {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected { background: #1976d2; color: #ffffff; }
            QMenu::separator {
                height: 1px;
                background: #e2e8f0;
                margin: 4px 6px;
            }
            """
        )

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.tray.setIcon(QIcon(icon_path))
        else:
            self.tray.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon))
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(self._on_tray_activated)

        menu = QMenu()
        act_show = QAction("Afficher", self)
        act_show.triggered.connect(self._show_from_tray)
        menu.addAction(act_show)
        act_toggle = QAction("Démarrer / Arrêter", self)
        act_toggle.triggered.connect(self.start_stop)
        menu.addAction(act_toggle)
        menu.addSeparator()
        act_quit = QAction("Quitter", self)
        act_quit.triggered.connect(self.quit_app)
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)

    # ------------------------------------------------------------------
    # Réglages / état
    # ------------------------------------------------------------------
    def _on_mode_changed(self, idx: int):
        self.rate_stack.setCurrentIndex(idx)
        self._save_config()

    def _compute_interval_ms(self) -> float:
        if self.mode_combo.currentIndex() == 0:
            unit = self.interval_unit.currentText()
            return self.interval_value.value() * UNIT_FACTORS_MS[unit]
        cps = max(0.01, self.cps_value.value())
        return 1000.0 / cps

    def _snapshot_params(self) -> dict:
        return {
            "interval_ms": self._compute_interval_ms(),
            "jitter_ms": float(self.jitter_value.value()),
            "button": BUTTON_MAP[self.button_combo.currentText()],
            "double_click": self.double_click_cb.isChecked(),
            "target_clicks": int(self.clicks_count.value()),
            "fixed_position": None if self.follow_mouse_cb.isChecked() else self.fixed_position,
        }

    # ------------------------------------------------------------------
    # Démarrage / arrêt
    # ------------------------------------------------------------------
    def _set_running_style(self, running: bool):
        self.start_btn.setProperty("running", "true" if running else "false")
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)
        self.start_btn.setText("Arrêter" if running else "Démarrer")

    def start_stop(self):
        if self.run_event.is_set():
            self.run_event.clear()
            self._set_running_style(False)
            self.status_label.setText("Arrêté")
            return

        if not self.follow_mouse_cb.isChecked() and self.fixed_position is None:
            QMessageBox.warning(self, APP_NAME, "Aucune position fixe capturée. Cliquez sur « Capturer (F8) ».")
            return

        self.stop_event.set()
        if self.clicker and self.clicker.is_alive():
            self.run_event.set()
            self.clicker.join(timeout=0.5)
        self.stop_event.clear()
        self.run_event.clear()
        self.clicker = ClickerThread(
            self._snapshot_params(),
            self.run_event,
            self.stop_event,
            self.counter,
            self._on_target_reached_threadsafe,
        )
        self.clicker.start()
        self.run_event.set()
        self._set_running_style(True)
        self.status_label.setText("En cours…")

    def _on_target_reached_threadsafe(self):
        QApplication.instance().postEvent(self, _CallEvent(self._on_target_reached))

    def _on_target_reached(self):
        self._set_running_style(False)
        self.status_label.setText("Nombre de clics atteint")
        if self.isHidden():
            self.tray.showMessage(APP_NAME, "Nombre de clics atteint.")

    # ------------------------------------------------------------------
    # Compteur
    # ------------------------------------------------------------------
    def _refresh_counter_label(self):
        with self.counter["lock"]:
            n = self.counter["n"]
        self.counter_label.setText(f"Clics : {n}")

    def _reset_counter(self):
        with self.counter["lock"]:
            self.counter["n"] = 0
        self._refresh_counter_label()

    # ------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------
    def _update_position_label(self):
        if self.follow_mouse_cb.isChecked():
            self.pos_label.setText("Position fixe : (désactivée)")
            self.capture_pos_btn.setEnabled(False)
            self.clear_pos_btn.setEnabled(False)
        else:
            self.capture_pos_btn.setEnabled(True)
            self.clear_pos_btn.setEnabled(True)
            if self.fixed_position is None:
                self.pos_label.setText("Position fixe : — (non capturée)")
            else:
                x, y = self.fixed_position
                self.pos_label.setText(f"Position fixe : ({x}, {y})")

    def _start_capture_position(self):
        self._capturing_position = True
        self.status_label.setText("Placez la souris et appuyez sur F8…")

    def _clear_position(self):
        self.fixed_position = None
        self._update_position_label()
        self._save_config()

    # ------------------------------------------------------------------
    # Hotkey
    # ------------------------------------------------------------------
    def _update_hotkey_label(self):
        self.hotkey_label.setText(key_to_str(self.toggle_key_parsed))

    def _start_capture_hotkey(self):
        self._capturing_hotkey = True
        self.status_label.setText("Appuyez sur une touche…")
        self.capture_hotkey_btn.setText("En attente…")
        self.capture_hotkey_btn.setEnabled(False)

    def _finish_capture_hotkey(self, key):
        if isinstance(key, (Key, KeyCode)):
            self.toggle_key_parsed = key
        self._capturing_hotkey = False
        self._update_hotkey_label()
        self.capture_hotkey_btn.setText("Changer…")
        self.capture_hotkey_btn.setEnabled(True)
        self.status_label.setText("Touche enregistrée")
        self._save_config()

    # ------------------------------------------------------------------
    # Listener clavier global
    # ------------------------------------------------------------------
    def _on_global_key(self, key):
        try:
            if self._capturing_hotkey:
                QApplication.instance().postEvent(
                    self, _CallEvent(lambda k=key: self._finish_capture_hotkey(k))
                )
                return

            if self._capturing_position and key == Key.f8:
                pos = Controller().position
                pos_int = (int(pos[0]), int(pos[1]))

                def apply():
                    self.fixed_position = pos_int
                    self._capturing_position = False
                    self._update_position_label()
                    self.status_label.setText(f"Position capturée : {pos_int}")
                    self._save_config()

                QApplication.instance().postEvent(self, _CallEvent(apply))
                return

            if keys_equal(key, self.toggle_key_parsed):
                QApplication.instance().postEvent(self, _CallEvent(self.start_stop))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Fenêtre / tray
    # ------------------------------------------------------------------
    def _toggle_always_on_top(self, on: bool):
        flags = self.windowFlags()
        if on:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        self._save_config()

    def hide_to_tray(self):
        self.hide()
        self.tray.show()
        self.tray.showMessage(APP_NAME, "Minimisé dans la zone de notification")

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._show_from_tray()

    def customEvent(self, event):
        if isinstance(event, _CallEvent):
            event.callback()

    def closeEvent(self, event):
        if self.run_event.is_set():
            resp = QMessageBox.question(
                self,
                APP_NAME,
                "L'auto-clic est en cours. Quitter quand même ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                event.ignore()
                return
        self.quit_app()
        event.accept()

    def quit_app(self):
        self.stop_event.set()
        self.run_event.set()
        try:
            self.klistener.stop()
        except Exception:
            pass
        self.tray.hide()
        QApplication.instance().quit()

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------
    def _save_config(self, *_):
        if self._suppress_save:
            return
        data = {
            "mode": self.mode_combo.currentIndex(),
            "interval_value": self.interval_value.value(),
            "interval_unit": self.interval_unit.currentText(),
            "cps_value": self.cps_value.value(),
            "jitter_ms": self.jitter_value.value(),
            "button": self.button_combo.currentText(),
            "double_click": self.double_click_cb.isChecked(),
            "target_clicks": self.clicks_count.value(),
            "follow_mouse": self.follow_mouse_cb.isChecked(),
            "fixed_position": list(self.fixed_position) if self.fixed_position else None,
            "hotkey": key_to_str(self.toggle_key_parsed),
            "always_on_top": self.always_on_top_cb.isChecked(),
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_config(self):
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        self.mode_combo.setCurrentIndex(int(data.get("mode", 0)))
        self.rate_stack.setCurrentIndex(self.mode_combo.currentIndex())
        self.interval_value.setValue(float(data.get("interval_value", 100.0)))
        unit = data.get("interval_unit", "ms")
        if unit in UNIT_FACTORS_MS:
            self.interval_unit.setCurrentText(unit)
        self.cps_value.setValue(float(data.get("cps_value", 10.0)))
        self.jitter_value.setValue(float(data.get("jitter_ms", 0.0)))
        btn = data.get("button", "Gauche")
        if btn in BUTTON_MAP:
            self.button_combo.setCurrentText(btn)
        self.double_click_cb.setChecked(bool(data.get("double_click", False)))
        self.clicks_count.setValue(int(data.get("target_clicks", 0)))
        self.follow_mouse_cb.setChecked(bool(data.get("follow_mouse", True)))
        pos = data.get("fixed_position")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            self.fixed_position = (int(pos[0]), int(pos[1]))
        self.toggle_key_parsed = parse_key(str(data.get("hotkey", "²")))
        self.always_on_top_cb.setChecked(bool(data.get("always_on_top", False)))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
