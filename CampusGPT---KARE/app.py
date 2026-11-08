#!/usr/bin/env python3
"""
Campus Platform Launcher — starts Campus GPT and University Information System
from a single command: python app.py
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "config.json"
LOG_DIR = ROOT / "logs"

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
COLORS = {
    "bg": "#0f172a",
    "card": "#1e293b",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "success": "#22c55e",
    "error": "#ef4444",
    "warning": "#f59e0b",
    "muted": "#94a3b8",
    "text": "#f1f5f9",
    "border": "#334155",
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass
class ServiceConfig:
    key: str
    label: str
    backend_dir: Path
    frontend_dir: Path
    backend_port: int
    frontend_port: int
    backend_health: str
    frontend_url: str


@dataclass
class PlatformConfig:
    campus_gpt: ServiceConfig
    uis: ServiceConfig
    health_timeout: float = 120.0
    health_interval: float = 1.5
    auto_open_browser: bool = True


def load_config() -> PlatformConfig:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    cg = raw["campus_gpt"]
    uis_raw = raw["university_information_system"]
    uis_root = ROOT / uis_raw.get("root", "campus-platform/university-information-system")
    startup = raw.get("startup", {})

    campus_gpt = ServiceConfig(
        key="campus_gpt",
        label=cg.get("label", "Campus GPT"),
        backend_dir=ROOT / cg["backend_dir"],
        frontend_dir=ROOT / cg["frontend_dir"],
        backend_port=cg["backend_port"],
        frontend_port=cg["frontend_port"],
        backend_health=cg["backend_health"],
        frontend_url=cg["frontend_url"],
    )
    uis = ServiceConfig(
        key="uis",
        label=uis_raw.get("label", "University Information System"),
        backend_dir=uis_root / uis_raw["backend_dir"],
        frontend_dir=uis_root / uis_raw["frontend_dir"],
        backend_port=uis_raw["backend_port"],
        frontend_port=uis_raw["frontend_port"],
        backend_health=uis_raw["backend_health"],
        frontend_url=uis_raw["frontend_url"],
    )
    return PlatformConfig(
        campus_gpt=campus_gpt,
        uis=uis,
        health_timeout=float(startup.get("health_check_timeout_seconds", 120)),
        health_interval=float(startup.get("health_check_interval_seconds", 1.5)),
        auto_open_browser=bool(startup.get("auto_open_browser", True)),
    )


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
class LauncherLog:
    def __init__(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.path = LOG_DIR / "launcher.log"
        self._lock = threading.Lock()

    def write(self, level: str, message: str) -> str:
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {message}"
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return line

    def info(self, message: str) -> str:
        return self.write("INFO", message)

    def error(self, message: str) -> str:
        return self.write("ERROR", message)

    def read_all(self) -> str:
        if not self.path.exists():
            return "No log entries yet."
        return self.path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Dependency & health utilities
# ---------------------------------------------------------------------------
def python_executable(backend_dir: Path) -> Path:
    if sys.platform == "win32":
        venv_py = backend_dir / "venv" / "Scripts" / "python.exe"
    else:
        venv_py = backend_dir / "venv" / "bin" / "python"
    return venv_py if venv_py.exists() else Path(sys.executable)


def npm_command() -> list[str]:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise FileNotFoundError("npm is not installed or not on PATH")
    return [npm]


def check_command(cmd: list[str], name: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            shell=False,
        )
        if result.returncode == 0:
            version = (result.stdout or result.stderr or "").strip().splitlines()[0]
            return True, version
        return False, result.stderr.strip() or f"{name} check failed"
    except FileNotFoundError:
        return False, f"{name} is not installed."
    except subprocess.TimeoutExpired:
        return False, f"{name} check timed out."
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def wait_for_url(url: str, timeout: float, interval: float, alive: Callable[[], bool]) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not alive():
            return False
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(interval)
    return False


def open_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        pass


def kill_process_tree(proc: Optional[subprocess.Popen]) -> None:
    if proc is None:
        return
    if proc.poll() is not None:
        return
    pid = proc.pid
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                shell=False,
            )
        else:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, OSError, subprocess.SubprocessError):
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------
@dataclass
class ManagedService:
    config: ServiceConfig
    backend_proc: Optional[subprocess.Popen] = None
    frontend_proc: Optional[subprocess.Popen] = None
    backend_log: Optional[object] = None
    frontend_log: Optional[object] = None
    status: str = "idle"
    error: str = ""

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    def processes_alive(self) -> bool:
        for proc in (self.backend_proc, self.frontend_proc):
            if proc is not None and proc.poll() is not None:
                return False
        return True


class ServiceManager:
    def __init__(self, platform: PlatformConfig, log: LauncherLog) -> None:
        self.platform = platform
        self.log = log
        self.campus = ManagedService(platform.campus_gpt)
        self.uis = ManagedService(platform.uis)
        self._stopping = False

    def validate_projects(self) -> list[str]:
        errors: list[str] = []
        for svc in (self.campus, self.uis):
            cfg = svc.config
            if not cfg.backend_dir.is_dir():
                errors.append(f"{cfg.label}: backend not found at {cfg.backend_dir}")
            elif not (cfg.backend_dir / "run.py").exists():
                errors.append(f"{cfg.label}: run.py missing in backend")
            if not cfg.frontend_dir.is_dir():
                errors.append(f"{cfg.label}: frontend not found at {cfg.frontend_dir}")
            elif not (cfg.frontend_dir / "package.json").exists():
                errors.append(f"{cfg.label}: package.json missing in frontend")
        return errors

    def check_dependencies(self) -> list[tuple[str, bool, str]]:
        checks: list[tuple[str, bool, str]] = []
        ok, msg = check_command([sys.executable, "--version"], "Python")
        checks.append(("Python", ok, msg))
        try:
            npm = npm_command()
            ok, msg = check_command(npm + ["--version"], "Node.js (npm)")
            checks.append(("Node.js (npm)", ok, msg))
        except FileNotFoundError as exc:
            checks.append(("Node.js (npm)", False, str(exc)))
        for svc in (self.campus, self.uis):
            cfg = svc.config
            found = cfg.backend_dir.is_dir() and cfg.frontend_dir.is_dir()
            checks.append((cfg.label, found, "Project found" if found else "Project missing"))
        return checks

    def _log_handle(self, name: str):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = LOG_DIR / f"{name}.log"
        return open(path, "a", encoding="utf-8")

    def _popen(self, cmd: list[str], cwd: Path, log_name: str) -> subprocess.Popen:
        log_file = self._log_handle(log_name)
        kwargs: dict = {
            "cwd": str(cwd),
            "stdout": log_file,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        self.log.info(f"Starting: {' '.join(cmd)} (cwd={cwd})")
        return subprocess.Popen(cmd, **kwargs)

    def _port_errors(self, svc: ManagedService) -> list[str]:
        errors: list[str] = []
        cfg = svc.config
        if is_port_in_use(cfg.backend_port):
            errors.append(f"Port {cfg.backend_port} is already in use ({cfg.label} backend).")
        if is_port_in_use(cfg.frontend_port):
            errors.append(f"Port {cfg.frontend_port} is already in use ({cfg.label} frontend).")
        return errors

    def start_service(
        self,
        svc: ManagedService,
        on_status: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> bool:
        cfg = svc.config
        svc.status = "starting"
        svc.error = ""

        port_errs = self._port_errors(svc)
        if port_errs:
            svc.status = "failed"
            svc.error = "\n".join(port_errs)
            on_error(svc.error)
            self.log.error(f"{cfg.label} failed: {svc.error}")
            return False

        py = python_executable(cfg.backend_dir)
        if not py.exists():
            svc.status = "failed"
            svc.error = f"Python not found for {cfg.label} backend."
            on_error(svc.error)
            return False

        try:
            npm = npm_command()
        except FileNotFoundError as exc:
            svc.status = "failed"
            svc.error = str(exc)
            on_error(svc.error)
            return False

        on_status(f"Starting {cfg.label} backend...")
        try:
            svc.backend_proc = self._popen([str(py), "run.py"], cfg.backend_dir, f"{cfg.key}_backend")
            svc.backend_log = svc.backend_proc.stdout
        except Exception as exc:  # noqa: BLE001
            svc.status = "failed"
            svc.error = f"Backend start failed: {exc}"
            on_error(svc.error)
            self.log.error(f"{cfg.label} backend: {exc}")
            return False

        on_status(f"Waiting for {cfg.label} backend...")
        if not wait_for_url(
            cfg.backend_health,
            self.platform.health_timeout,
            self.platform.health_interval,
            svc.processes_alive,
        ):
            svc.status = "failed"
            if not svc.processes_alive():
                svc.error = f"{cfg.label} backend process exited unexpectedly."
            else:
                svc.error = (
                    f"{cfg.label} backend did not become ready within "
                    f"{int(self.platform.health_timeout)}s."
                )
            on_error(svc.error)
            self.log.error(svc.error)
            self.stop_service(svc)
            return False

        on_status(f"Starting {cfg.label} frontend...")
        try:
            svc.frontend_proc = self._popen(npm + ["run", "dev"], cfg.frontend_dir, f"{cfg.key}_frontend")
            svc.frontend_log = svc.frontend_proc.stdout
        except Exception as exc:  # noqa: BLE001
            svc.status = "failed"
            svc.error = f"Frontend start failed: {exc}"
            on_error(svc.error)
            self.log.error(f"{cfg.label} frontend: {exc}")
            self.stop_service(svc)
            return False

        on_status(f"Waiting for {cfg.label} frontend...")
        if not wait_for_url(
            cfg.frontend_url,
            self.platform.health_timeout,
            self.platform.health_interval,
            svc.processes_alive,
        ):
            svc.status = "failed"
            if not svc.processes_alive():
                svc.error = f"{cfg.label} frontend process exited unexpectedly."
            else:
                svc.error = (
                    f"{cfg.label} frontend did not become ready within "
                    f"{int(self.platform.health_timeout)}s."
                )
            on_error(svc.error)
            self.log.error(svc.error)
            self.stop_service(svc)
            return False

        svc.status = "running"
        on_status(f"{cfg.label} is running.")
        self.log.info(f"{cfg.label} started successfully.")
        return True

    def stop_service(self, svc: ManagedService) -> None:
        kill_process_tree(svc.frontend_proc)
        kill_process_tree(svc.backend_proc)
        for fh in (svc.backend_log, svc.frontend_log):
            if fh and not fh.closed:
                try:
                    fh.close()
                except Exception:
                    pass
        svc.backend_proc = None
        svc.frontend_proc = None
        svc.backend_log = None
        svc.frontend_log = None
        if svc.status != "failed":
            svc.status = "stopped"

    def stop_all(self) -> None:
        self._stopping = True
        self.stop_service(self.campus)
        self.stop_service(self.uis)

    def start_all(
        self,
        on_status: Callable[[str], None],
        on_service_update: Callable[[], None],
    ) -> tuple[bool, bool]:
        self._stopping = False
        uis_ok = self.start_service(
            self.uis,
            on_status,
            lambda _: on_service_update(),
        )
        on_service_update()
        cg_ok = False
        if uis_ok:
            cg_ok = self.start_service(
                self.campus,
                on_status,
                lambda _: on_service_update(),
            )
            on_service_update()
        return uis_ok, cg_ok


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class CampusPlatformLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Campus Platform")
        self.geometry("640x720")
        self.minsize(560, 640)
        self.configure(bg=COLORS["bg"])
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.log = LauncherLog()
        self.config_data = load_config()
        self.manager = ServiceManager(self.config_data, self.log)
        self.ui_queue: queue.Queue = queue.Queue()
        self._startup_thread: Optional[threading.Thread] = None
        self._monitor_job: Optional[str] = None

        self._build_styles()
        self._build_ui()
        self.after(100, self._process_queue)
        self.after(300, self._begin_startup)

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["card"])
        style.configure(
            "Title.TLabel",
            background=COLORS["bg"],
            foreground=COLORS["text"],
            font=("Segoe UI", 22, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=COLORS["bg"],
            foreground=COLORS["muted"],
            font=("Segoe UI", 11),
        )
        style.configure(
            "Body.TLabel",
            background=COLORS["card"],
            foreground=COLORS["text"],
            font=("Segoe UI", 10),
        )
        style.configure(
            "Muted.TLabel",
            background=COLORS["card"],
            foreground=COLORS["muted"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "Status.TLabel",
            background=COLORS["card"],
            foreground=COLORS["text"],
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "Accent.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 8),
        )
        style.map(
            "Accent.TButton",
            background=[("active", COLORS["accent_hover"]), ("!disabled", COLORS["accent"])],
            foreground=[("!disabled", "white")],
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=24)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="CAMPUS PLATFORM", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="AI + University Information",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 16))

        self.startup_frame = ttk.Frame(outer)
        self.startup_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            self.startup_frame,
            text="Initializing platform...",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        self.startup_list = tk.Listbox(
            self.startup_frame,
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=("Consolas", 10),
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            selectbackground=COLORS["accent"],
            height=14,
        )
        self.startup_list.pack(fill=tk.BOTH, expand=True)

        self.dashboard_frame = ttk.Frame(outer)
        self._service_cards: dict[str, dict] = {}
        for key, svc in (
            ("campus", self.config_data.campus_gpt),
            ("uis", self.config_data.uis),
        ):
            card = self._make_service_card(self.dashboard_frame, svc)
            self._service_cards[key] = card

        btn_row = ttk.Frame(self.dashboard_frame)
        btn_row.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(btn_row, text="Open Campus GPT", style="Accent.TButton", command=self.open_campus).pack(
            fill=tk.X, pady=4
        )
        ttk.Button(
            btn_row,
            text="Open University System",
            style="Accent.TButton",
            command=self.open_uis,
        ).pack(fill=tk.X, pady=4)
        ttk.Button(btn_row, text="Restart Services", command=self.restart_services).pack(fill=tk.X, pady=4)
        ttk.Button(btn_row, text="Stop All Services", command=self.stop_services).pack(fill=tk.X, pady=4)
        ttk.Button(btn_row, text="View Logs", command=self.show_logs).pack(fill=tk.X, pady=4)

    def _make_service_card(self, parent: ttk.Frame, svc: ServiceConfig) -> dict:
        frame = ttk.Frame(parent, style="Card.TFrame", padding=16)
        frame.pack(fill=tk.X, pady=8)

        inner = tk.Frame(frame, bg=COLORS["card"])
        inner.pack(fill=tk.X)

        title = tk.Label(inner, text=svc.label, bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 12, "bold"))
        title.pack(anchor="w")

        status = tk.Label(inner, text="● Starting...", bg=COLORS["card"], fg=COLORS["warning"], font=("Segoe UI", 10, "bold"))
        status.pack(anchor="w", pady=(6, 2))

        url = tk.Label(inner, text=svc.frontend_url, bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 9))
        url.pack(anchor="w")

        error = tk.Label(inner, text="", bg=COLORS["card"], fg=COLORS["error"], font=("Segoe UI", 9), wraplength=520, justify=tk.LEFT)
        error.pack(anchor="w", pady=(6, 0))

        return {"frame": frame, "status": status, "url": url, "error": error, "config": svc}

    def _append_startup(self, message: str) -> None:
        prefix = "✓ " if not message.lower().startswith(("error", "✕", "failed")) else "  "
        self.startup_list.insert(tk.END, f"{prefix}{message}")
        self.startup_list.see(tk.END)

    def _process_queue(self) -> None:
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()
                if kind == "startup":
                    self._append_startup(payload)
                elif kind == "refresh":
                    self._refresh_cards()
                elif kind == "show_dashboard":
                    self._show_dashboard()
                elif kind == "open_browsers":
                    self._open_browsers()
        except queue.Empty:
            pass
        self.after(100, self._process_queue)

    def _show_dashboard(self) -> None:
        self.startup_frame.pack_forget()
        self.dashboard_frame.pack(fill=tk.BOTH, expand=True)
        self._refresh_cards()
        self._start_monitor()

    def _refresh_cards(self) -> None:
        mapping = {
            "campus": self.manager.campus,
            "uis": self.manager.uis,
        }
        for key, svc in mapping.items():
            card = self._service_cards[key]
            if svc.is_running:
                card["status"].configure(text="● Running", fg=COLORS["success"])
                card["error"].configure(text="")
            elif svc.status == "failed":
                card["status"].configure(text="✕ Failed", fg=COLORS["error"])
                card["error"].configure(text=svc.error or "Unknown error")
            elif svc.status == "stopped":
                card["status"].configure(text="○ Stopped", fg=COLORS["muted"])
            else:
                card["status"].configure(text="● Starting...", fg=COLORS["warning"])

    def _begin_startup(self) -> None:
        self._startup_thread = threading.Thread(target=self._run_startup, daemon=True)
        self._startup_thread.start()

    def _run_startup(self) -> None:
        def post_startup(msg: str) -> None:
            self.ui_queue.put(("startup", msg))

        post_startup("Checking Python...")
        checks = self.manager.check_dependencies()
        failed = False
        for name, ok, detail in checks:
            if ok:
                post_startup(f"Checking {name}... ✓ {detail}")
            else:
                post_startup(f"Checking {name}... ✕ {detail}")
                failed = True

        if failed:
            post_startup("Dependency check failed. Fix the issues above and restart.")
            self.ui_queue.put(("show_dashboard", None))
            return

        post_startup("Checking project structure...")
        proj_errors = self.manager.validate_projects()
        if proj_errors:
            for err in proj_errors:
                post_startup(f"✕ {err}")
            post_startup("Project validation failed.")
            self.ui_queue.put(("show_dashboard", None))
            return
        post_startup("✓ Projects found")

        def on_status(msg: str) -> None:
            post_startup(msg)

        def on_update() -> None:
            self.ui_queue.put(("refresh", None))

        post_startup("Starting University Information System...")
        post_startup("Starting Campus GPT...")

        uis_ok, cg_ok = self.manager.start_all(on_status, on_update)

        if uis_ok and cg_ok and self.config_data.auto_open_browser:
            self.ui_queue.put(("open_browsers", None))

        self.ui_queue.put(("show_dashboard", None))

    def _open_browsers(self) -> None:
        open_browser(self.config_data.uis.frontend_url)
        time.sleep(0.5)
        open_browser(self.config_data.campus_gpt.frontend_url)

    def open_campus(self) -> None:
        open_browser(self.config_data.campus_gpt.frontend_url)

    def open_uis(self) -> None:
        open_browser(self.config_data.uis.frontend_url)

    def show_logs(self) -> None:
        win = tk.Toplevel(self)
        win.title("Launcher Logs")
        win.geometry("720x480")
        win.configure(bg=COLORS["bg"])
        text = scrolledtext.ScrolledText(
            win,
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=("Consolas", 9),
            relief=tk.FLAT,
        )
        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        content = self.log.read_all()
        for name in ("uis_backend", "uis_frontend", "campus_gpt_backend", "campus_gpt_frontend"):
            path = LOG_DIR / f"{name}.log"
            if path.exists():
                content += f"\n\n--- {name}.log ---\n"
                content += path.read_text(encoding="utf-8", errors="replace")[-8000:]
        text.insert(tk.END, content)
        text.configure(state=tk.DISABLED)

    def restart_services(self) -> None:
        if self._startup_thread and self._startup_thread.is_alive():
            messagebox.showinfo("Please wait", "Startup is still in progress.")
            return

        def worker() -> None:
            self.manager.stop_all()
            self.ui_queue.put(("refresh", None))
            self.ui_queue.put(("startup", "Restarting all services..."))

            def on_status(msg: str) -> None:
                self.ui_queue.put(("startup", msg))

            def on_update() -> None:
                self.ui_queue.put(("refresh", None))

            self.manager.start_all(on_status, on_update)
            self.ui_queue.put(("refresh", None))

        threading.Thread(target=worker, daemon=True).start()

    def stop_services(self) -> None:
        self.manager.stop_all()
        self._refresh_cards()
        self.log.info("All services stopped by user.")

    def _start_monitor(self) -> None:
        if self._monitor_job:
            self.after_cancel(self._monitor_job)
        self._monitor_job = self.after(3000, self._monitor_services)

    def _monitor_services(self) -> None:
        changed = False
        for svc in (self.manager.campus, self.manager.uis):
            if svc.is_running and not svc.processes_alive():
                svc.status = "failed"
                svc.error = f"{svc.config.label} process terminated unexpectedly."
                self.log.error(svc.error)
                changed = True
        if changed:
            self._refresh_cards()
        self._monitor_job = self.after(3000, self._monitor_services)

    def on_close(self) -> None:
        if messagebox.askokcancel("Exit", "Stop all services and close the launcher?"):
            self._append_startup("Stopping Campus GPT...")
            self._append_startup("Stopping University Information System...")
            self._append_startup("Cleaning up processes...")
            self.manager.stop_all()
            self.log.info("Launcher closed.")
            self.destroy()


def main() -> int:
    if not CONFIG_PATH.exists():
        print(f"[ERROR] Config not found: {CONFIG_PATH}", file=sys.stderr)
        return 1
    app = CampusPlatformLauncher()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
