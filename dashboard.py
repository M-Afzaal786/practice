# THIS MUST BE THE VERY FIRST LINE OF THE FILE
from __future__ import annotations


import os
import sys
import subprocess
import ctypes
import customtkinter as ctk
import threading
import queue
from tkinter import filedialog, messagebox
from typing import Any, Dict, List, Optional, cast
from datetime import datetime
from functools import partial
from pathlib import Path

# Core application imports
from core.config import config_manager, get_counts, save_config, decrement_count
from core.sorter import FileSorter
from core.watcher import FileWatcher
from core.utils import get_logger, resource_path, set_log_callback
from core.cleanup import Cleaner
from core.i18n import _
from core.controllers.service_controller import ServiceController
from core.controllers.operation_manager import OperationManager
from core.controllers.search_controller import SearchController

# GUI Components
from .components import Sidebar, CategoryGrid, CleanupDialog
from core.scanner import FileScanner
from .components.wizard import WelcomeWizard
from gui.dialogs.first_run_wizard import FirstRunWizard
from .components.model_download_manager import show_download_manager_if_needed
from .components.undo_panel import UndoPanel
from .components.toast import ToastNotification  # Phase 24
from .components.dashboard_panels import (
    build_kpi_row, build_status_strip, build_activity_chart, build_recent_activity,
    build_storage_overview, build_smart_suggestions
)
# Views
from .views.dashboard_view import DashboardView
# Views are lazy-loaded in _show_view

import math
import tkinter as tk

# ── Global High-Performance Smooth Scroll Engine ──────────────────────
def _fast_smooth_mouse_wheel(self, event):
    """Instant, lag-free Windows scrolling; eliminates thrashing and idle-deferral tearing."""
    try:
        if not self.winfo_exists() or not self.winfo_ismapped():
            return
        x, y = event.x_root, event.y_root
        rx = self.winfo_rootx()
        ry = self.winfo_rooty()
        rw = self.winfo_width()
        rh = self.winfo_height()
        if not (rx <= x <= rx + rw and ry <= y <= ry + rh):
            return

        delta = getattr(event, "delta", 0)
        if not delta or not hasattr(self, "_parent_canvas"):
            return

        # Buttery-smooth, responsive Windows scrolling (~34px per wheel notch)
        pixels = -int(delta / 3.5)
        self._parent_canvas.yview_scroll(pixels, "units")
    except Exception:
        return

ctk.CTkScrollableFrame._mouse_wheel_all = _fast_smooth_mouse_wheel

logger = get_logger(__name__)

class AuroraBackground:
    """Animates subtle 3D 'Aurora' light waves in the background for premium aesthetics."""
    def __init__(self, master, bg_color):
        self.master = master
        self.canvas = tk.Canvas(master, bg=bg_color, highlightthickness=0, bd=0)
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        tk.Misc.lower(self.canvas)
        
        self.width = 1400
        self.height = 850
        self.phase = 0.0
        
        # Light blobs: (base_x, base_y, radius, speed, color)
        self.lights = [
            {"bx": 0.2, "by": 0.3, "r": 500, "sp": 0.012, "color": "#1E293B"}, # Deep Slate
            {"bx": 0.8, "by": 0.2, "r": 600, "sp": 0.008, "color": "#1E1B4B"}, # Deep Purple-Indigo
            {"bx": 0.5, "by": 0.8, "r": 550, "sp": 0.015, "color": "#0C1336"}, # Deep Navy
            {"bx": 0.1, "by": 0.9, "r": 400, "sp": 0.02,  "color": "#0F172A"}, # Deep Midnight
        ]
        
        for i in range(len(self.lights)):
            color_val = str(self.lights[i]["color"])
            self.canvas.create_oval(0, 0, 0, 0, fill=color_val, outline="", tags=f"light_{i}")
            
        self.running = True
        self._animate()

    def stop(self):
        """Stop animation and hide lights."""
        self.running = False
        for i in range(len(self.lights)):
            self.canvas.coords(f"light_{i}", -1000, -1000, -1000, -1000)

    def start(self):
        """Resume animation."""
        if not self.running:
            self.running = True
            self._animate()

    def _animate(self):
        if not self.canvas.winfo_exists():
            return
            
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w > 1: self.width, self.height = w, h
        
        self.phase += 0.02
        
        for i, light in enumerate(self.lights):
            # Calculate 3D-like orbital movement
            sp = float(light["sp"])
            off_x = math.cos(self.phase * sp * 10) * 100
            off_y = math.sin(self.phase * sp * 8) * 80
            
            x = (float(light["bx"]) * self.width) + off_x
            y = (float(light["by"]) * self.height) + off_y
            r = float(light["r"])
            
            self.canvas.coords(f"light_{i}", x-r, y-r, x+r, y+r)
            
        if self.running:
            self.master.after(50, self._animate)


class App(ctk.CTk):
    """The main application window with unified dashboard."""

    def __init__(self, *args, **kwargs):
        import time
        self._t_init_start = time.perf_counter()
        super().__init__(*args, **kwargs)

        # --- Main Window Configuration ---
        self.title("DevNova - SmartSorter")
        self.geometry("1400x850")
        self.minsize(1180, 680)

        # --- Theme and Appearance ---
        self.app_config = config_manager.load_config()
        
        from gui.services.ui_state import get_ui_state
        ui_state = get_ui_state()
        ctk.set_appearance_mode(ui_state.theme)
        ctk.set_default_color_theme("blue")

        from gui.theme import (
            apply_theme_customizations,
            COLOR_PAGE_BG, COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_RAISED, COLOR_BORDER,
            COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_ACCENT, COLOR_ACCENT_HOVER,
            COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER,
            CATEGORY_COLORS as THEME_CAT_COLORS, THEME_COLORS, THEME_FONTS,
            RADIUS_CARD, RADIUS_BUTTON, RADIUS_PILL,
            SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG
        )
        apply_theme_customizations(
            preset=self.app_config.get("theme_preset", "Default"),
            accent=self.app_config.get("accent_color"),
            bg_light=self.app_config.get("bg_color_light"),
            bg_dark=self.app_config.get("bg_color_dark"),
            surface_light=self.app_config.get("surface_color_light"),
            surface_dark=self.app_config.get("surface_color_dark"),
            font_size=self.app_config.get("ui_font_size", 14),
        )

        self.COLORS = THEME_COLORS
        self.CATEGORY_COLORS = THEME_CAT_COLORS
        self.FONTS = THEME_FONTS
        
        self.configure(fg_color=COLOR_PAGE_BG)
        self.sorting_menu_expanded = False
        self.service_running = False
        
        # --- Logic Layer Implementation (MVVM) ---
        self.sorter = FileSorter(update_callback=self._on_operation_complete)
        self.service_controller = ServiceController(
            self.sorter, 
            on_status_change=self._on_service_status_change
        )
        self.operation_manager = OperationManager(
            self.sorter, 
            on_refresh=lambda: self._on_operation_complete(None),
            on_error=self._on_error
        )
        self.search_controller = SearchController(
            self.sorter.brain,
            on_results=self._on_search_results_ready
        )
        self.search_job = None # Debounce job for search
        self.view_history: List[str] = []
        self.forward_stack: List[str] = []
        self.current_view: Optional[str] = None
        self.current_category = None
        self.file_checkboxes = {}
        self.category_checkboxes = {}
        self.file_list_frame = None
        
        # --- UI State Variables (Hardened for Type Stability) ---
        self.ai_enabled = ctk.BooleanVar(value=self.app_config.get("ai_enabled", True))
        self.copy_mode_var = ctk.BooleanVar(value=self.app_config.get("copy_mode", False))
        self.smart_rename_var = ctk.BooleanVar(value=self.app_config.get("smart_rename", False))
        self.search_var = ctk.StringVar()
        self.remote_url_var = ctk.StringVar(value=self.app_config.get("remote_config_url", ""))
        self.rename_format_entry_var = ctk.StringVar(value=self.app_config.get("rename_format", "{year}-{month}-{day}_{original}"))
        self.theme_var = ctk.StringVar(value=self.app_config.get("theme", "Dark"))
        self.lang_var = ctk.StringVar(value=self.app_config.get("language", "EN"))
        self.auto_update_var = ctk.BooleanVar(value=self.app_config.get("auto_update", True))
        self.notifications_var = ctk.BooleanVar(value=self.app_config.get("notifications_enabled", True))
        self.startup_var = ctk.BooleanVar(value=False)
        self.webhook_enabled_var = ctk.BooleanVar(value=self.app_config.get("webhook_enabled", False))
        self.webhook_url_var = ctk.StringVar(value=self.app_config.get("webhook_url", ""))
        self.profile_var = ctk.StringVar(value=self.app_config.get("active_profile", "Universal"))
        self.gallery_mode_var = ctk.BooleanVar(value=self.app_config.get("gallery_mode", True))
        self.strict_offline_var = ctk.BooleanVar(value=self.app_config.get("strict_offline_mode", True))
        self.cleanup_days_var = ctk.StringVar(value=str(self.app_config.get("cleanup_days", 30)))
        self.views: Dict[str, Any] = {} # Standardize views dictionary typing

        # --- Performance Management (FileListCache) ---
        from core.utils.bounded_cache import BoundedCache
        self.file_cache = BoundedCache(max_entries=2000, name="dashboard_file_cache")
        self.msg_queue = queue.Queue(maxsize=1000) # Thread-safe message bridge
        self._check_msg_queue()
        
        # --- UI Responsiveness & Debouncing (P4 & P5) ---
        self._active_toast = None
        self._pending_toast_items: List[Dict[str, str]] = []
        self._toast_coalesce_job = None
        self._dashboard_refresh_job = None
        
        # --- Window Icon Branding ---
        self._setup_window_icon()

        # --- Build UI ---
        import time
        t_layout_start = time.perf_counter()
        self._build_main_layout()
        t_layout_end = time.perf_counter()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Log startup performance without synchronously stalling GUI event loop
        def _log_first_paint(t_paint_start=t_layout_end):
            t_paint_end = time.perf_counter()
            _startup_start_str = os.environ.get("SMARTSORTER_START_TIME")
            if _startup_start_str:
                try:
                    _t0 = float(_startup_start_str)
                    _total_startup = t_paint_end - _t0
                    _import_dur = getattr(self, "_t_init_start", t_layout_start) - _t0
                    _layout_dur = t_layout_end - t_layout_start
                    _paint_dur = max(0.01, t_paint_end - t_paint_start)
                    logger.info(
                        f"startup: first window in {_total_startup:.2f} s "
                        f"(imports={_import_dur:.2f}s, layout={_layout_dur:.2f}s, paint={_paint_dur:.2f}s)"
                    )
                except Exception as e:
                    logger.debug(f"Startup timing calculation note: {e}")
        self.after(0, _log_first_paint)
        
        logger.info("Professional Dashboard initialized.")

        # Deferred dynamic classifier centroid training & folder sync in background (staggered to 22s)
        dest_root = self.app_config.get("dest_root") or self.app_config.get("destination")
        if dest_root:
            def _bg_dynamic_sync():
                try:
                    from core.dynamic_classifier import dynamic_autonomous_classifier
                    dynamic_autonomous_classifier.sync_user_folders(dest_root)
                except Exception as ex:
                    logger.debug(f"Background dynamic folder sync error: {ex}")
            self.after(22000, lambda: threading.Thread(target=_bg_dynamic_sync, daemon=True).start())
        
        # Auto-start watcher if source is configured (starts after UI is stable at 1500ms)
        if self.app_config.get("source") and os.path.exists(self.app_config["source"]):
            self.after(1500, self._start_auto_sort_from_config)
            
        # Initial Cloud Sync (Guarded by Strict Offline Mode)
        if self.app_config.get("remote_config_url") and not self.app_config.get("strict_offline_mode", True):
            threading.Thread(target=self._initial_cloud_sync, daemon=True).start()

        # Staggered background preloading of views for instant tab switching (starts at 2.0s)
        self.after(2000, self._background_preload_views)

        # Delay heavy file scan until AFTER the UI is fully rendered and views preloaded (12s)
        self.after(12000, self._start_background_scan)

        # Sequential low-priority component warm-up in background thread (16s after startup)
        self.after(16000, self._start_startup_warmup)

        # Auto-Update (Background Check at 28s - Guarded by Strict Offline Mode)
        if not self.app_config.get("strict_offline_mode", True):
            self.after(28000, self._background_update_check)
        
        # Register log callback late for stability
        self.after(1000, lambda: set_log_callback(self.add_log_entry))

        # Weekly Summary Toast (shown 25s after launch so UI is fully stable)
        self.after(25000, self._check_weekly_summary)

        # Archive sweep — runs once per week in the background (30s)
        self.after(30000, self._run_archive_sweep)

    def _background_preload_views(self):
        """Pre-instantiates heavy views using staggered scheduling to ensure 'Instant' first navigation without thread errors."""
        logger.debug("Background Pre-loading Views (Thread-Safe)...")
        preload_names = ["manual", "auto", "smart_rename", "review_queue", "logs", "automation", "settings"]
        
        # Schedule each view to load at a different time offset to avoid freezing the main loop
        for i, name in enumerate(preload_names):
            self.after(i * 350, lambda n=name: self._load_view_silently(n))

    def _start_startup_warmup(self):
        """Sequential component warm-up (ML -> Embedding -> MobileNet -> OCR) after first window is visible."""
        try:
            from core.warmup import start_startup_warmup
            start_startup_warmup(delay_seconds=0.0)
        except Exception as e:
            logger.debug(f"Could not trigger startup warmup: {e}")

    def _load_view_silently(self, name):
        """Initializes a view without showing it."""
        if name in self.views and self.views[name] is not None:
            return
            
        logger.debug(f"Silent Pre-load: {name}")
        try:
            self._lazy_load_view(name)
        except Exception as e:
            logger.debug(f"Silent Pre-load failed for {name}: {e}")
    def _check_msg_queue(self) -> None:
        """
        Poll the bridge queue for background task requests.
        Ensures thread-safe communication between workers and the main GUI thread.
        """
        try:
            while True:
                task = self.msg_queue.get_nowait()
                if callable(task):
                    try:
                        task()
                    except Exception as e:
                        logger.error(f"GUI Queue task failed: {e}")
        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Error checking message queue: {e}")
        finally:
            self.after(100, self._check_msg_queue)

    def _safe_put_msg(self, task) -> None:
        """Safely enqueues task on msg_queue, dropping non-critical UI updates if queue is full."""
        try:
            self.msg_queue.put_nowait(task)
        except queue.Full:
            logger.debug("msg_queue full (1000 items) — coalescing/dropping UI update")

    def _start_background_scan(self):
        """Starts a background thread to scan files. This keeps the UI responsive."""
        threading.Thread(target=self._background_scan_task, daemon=True).start()

    def _background_scan_task(self):
        """Worker thread that populates the cache using a single-pass high-performance scan."""
        logger.info("Starting optimized background file scan...")

        # 1. NEW: Single-pass scan of EVERYTHING
        # Lesson: os.walk is heavy. Doing it 20 times is 20x heavier.
        all_files = FileScanner.get_category_files("All Files", self.sorter.EXTENSION_CATEGORIES)
        # 2. Slice the monster list into categories in memory (0ms cost compared to I/O)
        ext_to_cat = self.sorter.EXTENSION_CATEGORIES
        categories = ["Documents", "Images", "Videos", "Audio", "Archives", 
                      "Spreadsheets", "Presentations", "Code", "Executables", 
                      "Databases", "Design", "Fonts", "3D Models", "Backups", 
                      "Web", "System", "Medical", "Duplicates", "Others",
                      "Academic", "Legal", "Finance", "Religious", "Company", "Projects"]
        
        # NEW: Double-buffering! Create a fresh temporary cache
        temp_cache = {cat: [] for cat in categories}
        temp_cache["All Files"] = all_files
        
        for f in all_files:
            parent_folder = os.path.basename(os.path.dirname(f['full_path']))
            matched_cat = None
            for cat in categories:
                if parent_folder.lower() == cat.lower() or (cat.lower() == "duplicates" and parent_folder.lower() == "review_duplicates"):
                    matched_cat = cat
                    break
            
            if matched_cat:
                temp_cache[matched_cat].append(f)
            else:
                file_name = f['name']
                ext = os.path.splitext(file_name)[1].lower()
                cat = ext_to_cat.get(ext, "Others")
                if cat in temp_cache:
                    temp_cache[cat].append(f)
                else:
                    temp_cache["Others"].append(f)
        
        # 3. ATOMIC UPDATE: Sync to SQLite Cache instead of just RAM
        # This is Task 1: Enterprise Memory Management
        self.sorter.brain.sync_file_cache("All Files", all_files)
        for cat, files in temp_cache.items():
            if cat != "All Files":
                self.sorter.brain.sync_file_cache(cat, files)
        
        # Keep a small 'recent' cache in RAM for the Dashboard Grid, but not the whole list
        self.file_cache.update({cat: files[:100] for cat, files in temp_cache.items()})
            
        # Update counts SAFELY via Queue and Physical Sync
        sync_data = {cat: len(files) for cat, files in self.file_cache.items() if cat != "All Files"}
        config_manager.sync_counts(sync_data)
        
        self._safe_put_msg(self._refresh_category_counts)
        self._safe_put_msg(self._refresh_active_view)
        logger.info(f"Background scan complete! Cached {len(all_files)} files across {len(categories)} categories.")
        




    def _mix_colors(self, color: str, base: str, alpha: float) -> str:
        """Alpha-composite `color` over `base` at `alpha` opacity."""
        c = color.lstrip('#'); b = base.lstrip('#')
        cr, cg, cb = int(c[0:2],16), int(c[2:4],16), int(c[4:6],16)
        br, bg, bb = int(b[0:2],16), int(b[2:4],16), int(b[4:6],16)
        r  = int(br + (cr - br) * alpha)
        g  = int(bg + (cg - bg) * alpha)
        b_ = int(bb + (cb - bb) * alpha)
        return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b_)):02x}"

    # ── Gap 3: Weekly Summary Toast ───────────────────────────────────────
    def _check_weekly_summary(self):
        """Show a weekly digest toast if 7 days have passed since last shown."""
        try:
            import json, time
            state_path = str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SmartFileSorter" / "weekly_state.json")
            last_shown = 0
            if os.path.exists(state_path):
                with open(state_path) as f:
                    last_shown = json.load(f).get("last_weekly_ts", 0)

            # Show if never shown OR 7 days have passed
            SEVEN_DAYS = 7 * 24 * 3600
            if time.time() - last_shown < SEVEN_DAYS:
                return

            # Fetch stats in background thread
            def _fetch_and_show():
                try:
                    stats = self.sorter.brain.get_weekly_stats()
                    if stats["files_sorted"] == 0:
                        return  # Nothing to show
                    self._safe_put_msg(lambda s=stats: self._show_weekly_summary(s))
                    # Save timestamp
                    os.makedirs(os.path.dirname(state_path), exist_ok=True)
                    with open(state_path, "w") as f:
                        json.dump({"last_weekly_ts": time.time()}, f)
                except Exception as e:
                    logger.debug(f"Weekly summary fetch failed: {e}")

            threading.Thread(target=_fetch_and_show, daemon=True).start()
        except Exception as e:
            logger.debug(f"Weekly summary check failed: {e}")

    def _show_weekly_summary(self, stats: dict):
        """Renders the Weekly Summary Toast notification."""
        try:
            from .components.toast import ToastNotification
            n = stats["files_sorted"]
            mins = stats["est_minutes"]
            top = stats["top_category"]
            dups = stats["duplicates"]

            # Build a rich multi-line message
            msg = (
                f"Week in review: {n} files sorted\n"
                f"Saved ~{mins} min  |  Top: {top}"
            )
            if dups:
                msg += f"  |  {dups} duplicates caught"

            ToastNotification(
                parent=self.content_area,
                message=msg,
                icon="STATS",
                duration_ms=9000,
                colors=self.COLORS,
            )
            logger.info(f"Weekly Summary: {n} files sorted, {mins} min saved, top={top}")
        except Exception as e:
            logger.debug(f"Weekly toast render failed: {e}")

    # ── Gap 2: Archive Sweep ──────────────────────────────────────────────
    def _run_archive_sweep(self):
        """Trigger archive sweep once per week in background thread."""
        try:
            import json, time
            state_path = str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SmartFileSorter" / "weekly_state.json")
            last_archive = 0
            if os.path.exists(state_path):
                with open(state_path) as f:
                    last_archive = json.load(f).get("last_archive_ts", 0)

            SEVEN_DAYS = 7 * 24 * 3600
            if time.time() - last_archive < SEVEN_DAYS:
                logger.debug("Archive sweep: skipped (ran < 7 days ago)")
                return

            dest_root = self.app_config.get("dest_root", "")
            if not dest_root or not os.path.exists(dest_root):
                logger.debug("Archive sweep: no dest_root configured")
                return

            def _on_archive_done(archive_stats):
                archived = archive_stats.get("archived", 0)
                if archived > 0:
                    msg = f"Archive sweep: {archived} old file(s) moved to Archive/"
                    self._safe_put_msg(lambda m=msg: self._show_archive_toast(m))
                # Save timestamp
                try:
                    os.makedirs(os.path.dirname(state_path), exist_ok=True)
                    data = {}
                    if os.path.exists(state_path):
                        with open(state_path) as f:
                            data = json.load(f)
                    data["last_archive_ts"] = time.time()
                    with open(state_path, "w") as f:
                        json.dump(data, f)
                except Exception:
                    pass

            from core.archive_manager import archive_manager
            archive_manager.run_background(
                dest_root=dest_root,
                brain=self.sorter.brain,
                on_complete=_on_archive_done
            )
            logger.info(f"Archive sweep started for: {dest_root}")
        except Exception as e:
            logger.debug(f"Archive sweep trigger failed: {e}")

    def _show_archive_toast(self, msg: str):
        """Shows archive sweep result toast."""
        try:
            from .components.toast import ToastNotification
            ToastNotification(
                parent=self.content_area,
                message=msg,
                icon="ARCHIVE",
                duration_ms=7000,
                colors=self.COLORS,
            )
        except Exception as e:
            logger.debug(f"Archive toast failed: {e}")

    def _build_main_layout(self):
        """Constructs the main layout with sidebar and content area."""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Header row - fixed height
        self.grid_rowconfigure(1, weight=1)  # Content row - expands
        
        # --- Sidebar (Modular Component) ---
        self.sidebar = Sidebar(
            self,
            colors=self.COLORS,
            fonts=self.FONTS,
            nav_callback=self._show_view,
            toggle_sorting_callback=self.toggle_sorting_menu,
            search_callback=lambda q: self._on_search_change_modular(q),
            app=self,
            search_var=self.search_var
        )
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=0, pady=0)
        
        # Check initial status
        self._update_service_status_ui()

        # Modern layout gives the content area the full viewport
        self.global_header = None
        self.bell_btn = None


        self.content_area = ctk.CTkFrame(
            self, 
            fg_color=self.COLORS["bg_content"], 
            corner_radius=0
        )
        self.content_area.grid(row=0, column=1, rowspan=2, sticky="nsew")
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

        # Keyboard Navigation & Shortcuts
        self.bind_all("<Alt-Left>", lambda e: self._go_back())
        self.bind_all("<Alt-Right>", lambda e: self._go_forward())
        self.bind_all("<Control-k>", self._on_ctrl_k)
        self.bind_all("<Control-K>", self._on_ctrl_k)
        
        # Lazy-Loading State (Views are created only when first needed)
        self.views.update({
            "dashboard": DashboardView(self.content_area, self),
            "manual": None,
            "auto": None,
            "logs": None,
            "settings": None,
            "automation": None,
            "smart_rename": None,
            "review_queue": None,
            "concept_search": None,
            "ask_files": None,
        })
        
        # --- First-Run Setup Wizard (Phase 2.2) ---
        # Triggers only on very first launch if setup is not complete and first_run is True
        if self.app_config.get("first_run", True) and not self.app_config.get("setup_complete", False):
            self.after(600, self._open_first_run_wizard)
        else:
            # Existing users: silently check models in the background only if enabled
            if self.app_config.get("show_model_download_prompt", False):
                self.after(4000, self._check_ai_models)
        self._show_view("dashboard")

    def _show_notifications_popup(self):
        """Displays a sleek notification dropdown menu."""
        popup = ctk.CTkToplevel(self)
        popup.title("Notifications")
        popup.geometry("400x420")
        popup.overrideredirect(True) # Remove windows border to look like a dropdown
        
        # Position it dynamically at top right corner of the window
        self.update_idletasks() # Ensure geometry is updated before calculation
        if hasattr(self, 'bell_btn') and self.bell_btn is not None and self.bell_btn.winfo_exists():
            x = self.bell_btn.winfo_rootx() - 340
            y = self.bell_btn.winfo_rooty() + 45
        else:
            x = self.winfo_rootx() + self.winfo_width() - 410
            y = self.winfo_rooty() + 70
        popup.geometry(f"+{x}+{y}")
        popup.focus_force()
        
        # Click outside to close (bind to focus out)
        popup.bind("<FocusOut>", lambda e: popup.destroy())
        
        main_frame = ctk.CTkFrame(popup, fg_color="#0C1336", corner_radius=12, border_width=1, border_color="#1E293B")
        main_frame.pack(fill="both", expand=True)
        
        # Header
        hdr = ctk.CTkFrame(main_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(hdr, text="Notifications", font=self.FONTS["header"](s=16), text_color="#FFFFFF").pack(side="left")
        ctk.CTkLabel(hdr, text="2 New", font=self.FONTS["small"](s=10, w="bold"), text_color="#3B82F6", fg_color="#1E293B", corner_radius=6).pack(side="right", ipadx=6, ipady=2)
        
        ctk.CTkFrame(main_frame, height=1, fg_color="#1E293B").pack(fill="x")
        
        # Notifications List
        scroll = ctk.CTkScrollableFrame(main_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        notifs = [
            ("AI Engine", "Background scan completed successfully. System is optimized.", "Just now", "#34D399"),
            ("Auto-Sort", "Organized 14 new files from Downloads folder.", "5m ago", "#6366F1"),
            ("Security", "System backup was completed and verified.", "2h ago", "#A78BFA"),
            ("System", "Welcome to SmartSorter PRO. All systems are operational.", "1d ago", "#64748B")
        ]
        
        for title, msg, time_str, color in notifs:
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=8)
            
            # Dot
            dot = ctk.CTkFrame(row, width=8, height=8, corner_radius=4, fg_color=color)
            dot.pack(side="left", padx=(0, 12), pady=(5,0), anchor="n")
            dot.pack_propagate(False)
            
            # Content
            text_col = ctk.CTkFrame(row, fg_color="transparent")
            text_col.pack(side="left", fill="x", expand=True)
            
            top_row = ctk.CTkFrame(text_col, fg_color="transparent")
            top_row.pack(fill="x")
            ctk.CTkLabel(top_row, text=title, font=self.FONTS["body"](w="bold"), text_color="#E2E8F0").pack(side="left")
            ctk.CTkLabel(top_row, text=time_str, font=self.FONTS["small"](s=9), text_color="#64748B").pack(side="right")
            
            ctk.CTkLabel(text_col, text=msg, font=self.FONTS["small"](), text_color="#94A3B8", justify="left", wraplength=300).pack(anchor="w", pady=(2,0))



    def _open_first_run_wizard(self, is_reopened: bool = False):
        """Launches the 3-step First-Run Wizard dialog (Phase 2.2)."""
        wizard = FirstRunWizard(
            parent=self,
            app=self,
            on_complete=self._on_setup_finish,
            is_reopened=is_reopened,
        )
        return wizard

    def _on_setup_finish(self):
        """Called when WelcomeWizard completes."""
        logger.info("Setup complete! Refreshing paths...")
        self.app_config = config_manager.load_config()
        self._show_view("dashboard")
        # After onboarding: check and prompt to download AI models only if enabled
        if self.app_config.get("show_model_download_prompt", False):
            self.after(800, self._check_ai_models)

    def _check_ai_models(self):
        """
        Checks whether all required AI models (GLiNER, DistilBART) are present
        in the local HuggingFace cache. Opens the ModelDownloadManager if any
        are missing, otherwise proceeds silently.
        """
        if not self.app_config.get("show_model_download_prompt", False):
            return
        def _on_models_ready():
            logger.info("AI Model check complete — all models are ready.")
            # Show a quick toast to confirm AI is armed
            try:
                ToastNotification(
                    self.content_area,
                    message="AI Engines Armed",
                    icon="AI",
                    duration_ms=3500,
                    colors=self.COLORS
                )
            except Exception:
                pass  # Toast is cosmetic; silently ignore failures

        show_download_manager_if_needed(self, self, completion_callback=_on_models_ready)

    def _show_undo_panel(self):
        """Displays the Undo History floating panel."""
        UndoPanel(self, self, self.sorter.brain)

    def open_duplicate_cleaner(self, target_dir: Optional[str] = None):
        """Displays the Intelligent Duplicate & Storage Space Optimizer."""
        from gui.components.duplicate_cleaner_modal import show_duplicate_cleaner
        if not target_dir:
            target_dir = self.app_config.get("source") or self.app_config.get("dest_root")
        show_duplicate_cleaner(self, target_dir=target_dir)

    def _go_back(self):
        """Navigate to the previous view in history."""
        if self.view_history:
            prev = self.view_history.pop()
            self.forward_stack.append(self.current_view)
            self._show_view(prev, save_history=False)

    def _go_forward(self):
        """Navigate forward in history."""
        if self.forward_stack:
            nxt = self.forward_stack.pop()
            self.view_history.append(self.current_view)
            self._show_view(nxt, save_history=False)

    def _on_ctrl_k(self, event=None):
        """Navigate to Home and focus the search prompt box."""
        self._show_view("dashboard")
        home = self.views.get("dashboard")
        if home and hasattr(home, "focus_prompt_box"):
            self.after(50, home.focus_prompt_box)
        return "break"

    def _deep_dive_throughput(self, days: Optional[int]):
        """Opens the search view filtered by the files processed in the selected range."""
        logger.info(f"Deep Dive: Opening file view for last {days or 'all'} days.")
        self.sidebar.search_var.set(f"range:{days or 'all'}")
        self._show_view("search_results")

    def _refresh_view(self):
        """Manually triggers a full refresh of current data and UI components."""
        if self.current_view == "dashboard":
            self.views["dashboard"].refresh()
        
        if hasattr(self, 'category_grid'):
            self.category_grid.refresh()

    def _show_notifications_popup(self):
        """Next-Gen Notification Hub — Premium Overlay design."""
        # Create a high-fidelity popup frame over the dashboard
        overlay = ctk.CTkFrame(self, fg_color=self.COLORS["bg_card"], 
                               border_width=1, border_color=("#818CF8", "#6366F1"),
                               corner_radius=16, width=320, height=400)
        overlay.place(relx=0.88, rely=0.08, anchor="ne")
        overlay.pack_propagate(False)

        # Header
        hdr = ctk.CTkFrame(overlay, fg_color="transparent")
        hdr.pack(fill="x", padx=15, pady=(15, 10))
        ctk.CTkLabel(hdr, text="Smart Notifications", 
                     font=self.FONTS["header"](s=15, w="bold"),
                     text_color=self.COLORS["text_header"]).pack(side="left")
        ctk.CTkButton(hdr, text="✕", width=24, height=24, corner_radius=12,
                      fg_color="transparent", hover_color=("#FEE2E2", "#450A0A"),
                      text_color=("#EF4444", "#F87171"),
                      command=overlay.destroy).pack(side="right")

        # Notification List (Simulated)
        scroll = ctk.CTkScrollableFrame(overlay, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=5, pady=5)

        notifications = [
            ("OK", "Success", "14 files sorted into 'Engineering'"),
            ("SEC", "Security", "All file operations encrypted"),
            ("AI", "Intelligence", "Universal Engine mode active"),
            ("SYNC", "Sync", "Database backup complete"),
            ("SYS", "System", "Aesthetic mode: Jewel-Glow active")
        ]

        for icon, title, desc in notifications:
            item = ctk.CTkFrame(scroll, fg_color=self.COLORS["bg_subcard"], corner_radius=10)
            item.pack(fill="x", pady=4, padx=5)
            
            ctk.CTkLabel(item, text=icon, font=ctk.CTkFont(size=18)).pack(side="left", padx=10, pady=10)
            txt_box = ctk.CTkFrame(item, fg_color="transparent")
            txt_box.pack(side="left", fill="both", expand=True)
            
            ctk.CTkLabel(txt_box, text=title, font=self.FONTS["body"](s=12, w="bold"),
                         text_color=self.COLORS["text_primary"]).pack(anchor="w", pady=(5, 0))
            ctk.CTkLabel(txt_box, text=desc, font=self.FONTS["small"](s=10),
                         text_color=self.COLORS["text_secondary"]).pack(anchor="w", pady=(0, 5))

        # Footer
        ctk.CTkButton(overlay, text="Clear All", height=32, corner_radius=8,
                      fg_color="transparent", border_width=1, border_color=("#818CF8", "#6366F1"),
                      text_color=("#4F46E5", "#A5B4FC"),
                      command=overlay.destroy).pack(pady=15, padx=20, fill="x")

    def _toggle_theme_quick(self):
        """Standard Mode Switch: Bulletproof Implementation."""
        try:
            print(">>> THEME TOGGLE: EXPLICIT CALL STARTED")
            current_mode = ctk.get_appearance_mode().lower()
            new_mode = "light" if current_mode == "dark" else "dark"
            
            # Change Mode
            ctk.set_appearance_mode(new_mode)
            print(f">>> THEME TOGGLE: Successfully set mode to {new_mode}")
            
            # Re-apply window icon so Tkinter does not revert to the default feather
            self.after(50, self._setup_window_icon)
            self.after(200, self._setup_window_icon)

            # Force App Refresh
            self.configure(fg_color=("#FFFFFF", "#060B27"))
            self._show_view(self.current_view, save_history=False)
            
            print(">>> THEME TOGGLE: Refresh complete.")
        except Exception as e:
            print(f">>> THEME TOGGLE ERROR: {e}")

    def _show_view(self, name: str, save_history: bool = True):
        """Premium view switching with lazy-initialization and smooth transitions."""
        if name not in self.views and not name.startswith("category_") and name != "search_results":
            return

        # No-op if already viewing the requested tab and its widget is already gridded
        if getattr(self, "current_view", None) == name:
            target_obj = self.views.get(name)
            if target_obj and target_obj.winfo_exists() and bool(target_obj.grid_info()):
                return
            
        # History management
        if save_history and hasattr(self, 'current_view') and self.current_view and self.current_view != name:
            self.view_history.append(self.current_view)
            self.forward_stack.clear()
            if len(self.view_history) > 50: self.view_history.pop(0) # Cap memory
            
        # 1. Lazy Initialization
        if name in self.views and self.views[name] is None:
            self._lazy_load_view(name)
            
        # 2. Hide Current (with state check)
        target_view = None
        if name.startswith("category_"):
            cat_name = name.replace("category_", "")
            if name not in self.views:
                self._on_category_click(cat_name)
                return
            target_view = self.views[name]
        elif name == "search_results":
            if not hasattr(self, 'search_results_view'):
                from .views.search_view import SearchView
                self.search_results_view = SearchView(self.content_area, self)
            target_view = self.search_results_view
        else:
            target_view = self.views[name]

        # Switch logic - cleanly hide previous active view
        prev_view_name = getattr(self, "current_view", None)
        if prev_view_name and prev_view_name in self.views and self.views[prev_view_name] and prev_view_name != name:
            try:
                self.views[prev_view_name].grid_remove()
            except Exception:
                pass
        if hasattr(self, 'search_results_view') and self.search_results_view and target_view != self.search_results_view:
            try:
                self.search_results_view.grid_remove()
            except Exception:
                pass
        
        if target_view:
            target_view.grid(row=0, column=0, sticky="nsew")

        self.current_view = name
        self.sidebar.update_active_state(name)
        
        # Side effects
        if name == "logs": self.after(50, self._flush_log_buffer)
        if name in ["manual", "auto", "smart_rename"] and not self.sorting_menu_expanded: self.toggle_sorting_menu()
        if name == "review_queue" and self.views.get("review_queue"): self.views["review_queue"].refresh()

    def _lazy_load_view(self, name: str):
        logger.debug(f"⚡ Lazy Loading: {name}")
        if name == "manual": 
            from .views.manual_sort_view import ManualSortView
            self.views[name] = ManualSortView(self.content_area, self)
        elif name == "auto": 
            from .views.auto_sort_view import AutoSortView
            self.views[name] = AutoSortView(self.content_area, self)
        elif name == "logs": 
            from .views.logs_view import LogsView
            self.views[name] = LogsView(self.content_area, self)
        elif name == "settings": 
            from .views.settings_view import SettingsView
            self.views[name] = SettingsView(self.content_area, self)
        elif name == "automation": 
            from .views.automation_view import AutomationView
            self.views[name] = AutomationView(self.content_area, self)
        elif name == "smart_rename":
            from .views.smart_rename_view import SmartRenameView
            self.views[name] = SmartRenameView(self.content_area, self)
        elif name == "review_queue":
            from .views.review_queue_view import ReviewQueueView
            self.views[name] = ReviewQueueView(self.content_area, self)
        elif name == "concept_search":
            from .views.concept_search_view import ConceptSearchView
            self.views[name] = ConceptSearchView(self.content_area, self)
        elif name == "ask_files":
            from .views.ask_files_view import AskFilesView
            self.views[name] = AskFilesView(self.content_area, self)

    def toggle_sorting_menu(self):
        """Toggle the sorting submenu visibility in the sidebar."""
        if hasattr(self.sidebar, "toggle_sorting_menu"):
            self.sorting_menu_expanded = self.sidebar.toggle_sorting_menu()
        else:
            self.sorting_menu_expanded = not self.sorting_menu_expanded

    def _update_nav_active_state(self, active_view):
        """Forward navigation state update to modular sidebar."""
        self.sidebar.update_active_state(active_view)

    def _on_search_change(self, event=None):
        """Handle search input changes with a slight delay (Debouncing)."""
        # Cancel pending search job
        if self.search_job:
            self.after_cancel(self.search_job)
            
        # Schedule new search job
        self.search_job = self.after(300, self._perform_search)
        
    def _perform_search(self):
        """Execute search via SearchController."""
        query = self.search_var.get().strip()
        self.search_controller.perform_search(query)

    def _on_search_results_ready(self, results):
        """Callback from SearchController when results are ready."""
        self.after(0, lambda: self._show_search_results_from_data(results))

    def _show_search_results_from_data(self, results):
        """Displays processed search results."""
        self._show_view("search_results")
        if hasattr(self, 'search_results_view'):
            self.search_results_view.populate_file_list(filtered_files=results)




    # --- View Creation Methods ---
    


    def _toggle_theme_quick(self):
        """Quick toggle between light and dark themes."""
        current = self.app_config.get("theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        self.change_theme(new_theme.capitalize())

    def change_theme(self, theme_name: str):
        """Update the global appearance mode and persist configuration."""
        theme_name = theme_name.lower().strip()
        if theme_name not in ("light", "dark", "system"):
            theme_name = "light"
        self.app_config["theme"] = theme_name
        save_config(self.app_config)
        
        # 1. Update CustomTkinter appearance mode
        ctk.set_appearance_mode(theme_name)
        self.after(50, self._setup_window_icon)
        self.after(200, self._setup_window_icon)
        
        if hasattr(self, 'theme_btn') and self.theme_btn.winfo_exists():
            self.theme_btn.configure(text="Light" if theme_name == "light" else "Dark")

        # 2. Refresh sidebar nav items if present
        if hasattr(self, 'sidebar') and hasattr(self.sidebar, 'refresh_theme'):
            try:
                self.sidebar.refresh_theme()
            except Exception as e:
                logger.debug(f"Sidebar theme refresh error: {e}")

        # 3. Notify active view if it supports theme updates
        current = getattr(self, 'current_view', None)
        if current and current in self.views:
            view = self.views[current]
            if hasattr(view, 'on_theme_changed'):
                try:
                    view.on_theme_changed(theme_name)
                except Exception as e:
                    logger.debug(f"View theme callback error: {e}")

        logger.info(f"Theme changed to: {theme_name}")

    def apply_custom_theme(
        self,
        preset=None,
        accent=None,
        bg_light=None,
        bg_dark=None,
        surface_light=None,
        surface_dark=None,
        font_size=None,
        mode=None
    ):
        """Update global theme tokens, persist configuration, and live-refresh UI."""
        from gui.theme import apply_theme_customizations, COLOR_PAGE_BG
        apply_theme_customizations(
            preset=preset,
            accent=accent,
            bg_light=bg_light,
            bg_dark=bg_dark,
            surface_light=surface_light,
            surface_dark=surface_dark,
            font_size=font_size
        )
        if preset:
            self.app_config["theme_preset"] = preset
        if accent:
            self.app_config["accent_color"] = accent
        if bg_light:
            self.app_config["bg_color_light"] = bg_light
        if bg_dark:
            self.app_config["bg_color_dark"] = bg_dark
        if surface_light:
            self.app_config["surface_color_light"] = surface_light
        if surface_dark:
            self.app_config["surface_color_dark"] = surface_dark
        if font_size:
            self.app_config["ui_font_size"] = font_size

        from core.config import save_config
        save_config(self.app_config)

        if mode:
            self.change_theme(mode)
        else:
            self.configure(fg_color=COLOR_PAGE_BG)
            if hasattr(self, 'sidebar') and hasattr(self.sidebar, 'refresh_theme'):
                self.sidebar.refresh_theme()
            current = getattr(self, 'current_view', None)
            if current and current in self.views:
                view = self.views[current]
                if hasattr(view, 'on_theme_changed'):
                    try:
                        view.on_theme_changed(self.app_config.get("theme", "light"))
                    except Exception as e:
                        logger.debug(f"View refresh error: {e}")

    def _adjust_brightness(self, hex_color, factor):
        """Adjust color brightness for hover effects."""
        if isinstance(hex_color, (tuple, list)):
            mode = ctk.get_appearance_mode().lower()
            hex_color = hex_color[1] if mode == "dark" else hex_color[0]
        hex_color = str(hex_color).lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _on_category_click(self, category):
        """Handle clicking a category on the dashboard."""
        # Map synthetic "Total Files" category to "All Files" for the view
        # We check both the localized string and the raw code string for robustness
        from core.i18n import _
        is_total_files = (category == _("total_files") or category == "Total Files Organized")
        
        category_for_view = "All Files" if is_total_files else category
        view_name = f"category_{category_for_view.replace(' ', '_')}"
        
        if view_name not in self.views:
            from .views.category_view import CategoryView
            self.views[view_name] = CategoryView(self.content_area, category_for_view, self)
            
        # Load files for the category from cache
        files = self.file_cache.get(category_for_view, [])
        
        # Reactive scan: if cache is empty, do it in a non-blocking background thread
        if not files:
            logger.info(f"Empty cache for {category_for_view}, performing non-blocking reactive scan...")
            
            def reactive_scan_task():
                res = FileScanner.get_category_files(category_for_view, self.sorter.EXTENSION_CATEGORIES)
                self.file_cache[category_for_view] = res
                # Update UI safely via msg_queue
                self._safe_put_msg(lambda c=category_for_view: self._on_reactive_scan_complete(c))
            
            threading.Thread(target=reactive_scan_task, daemon=True).start()
            # Show the view immediately (it will be populated once the thread finishes)
            self._show_view(view_name)
            return

        self._show_view(view_name)

    def _on_reactive_scan_complete(self, category):
        """Called when a reactive background scan finishes to refresh the currently visible view."""
        # Only refresh if the user is still looking at that category
        active_view_obj = self.views.get(self.current_view)
        if active_view_obj and hasattr(active_view_obj, 'category') and active_view_obj.category == category:
            self._refresh_active_view()
        self._refresh_category_counts()
    def _open_cleanup_tool(self):
        """Open the auto-cleanup utility window."""
        CleanupDialog(self, self.COLORS, self.FONTS)

    def _on_search_change_modular(self, query):
        """Bridge for modular sidebar search."""
        if hasattr(self, '_search_timer'):
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(500, lambda: self.search_controller.perform_search(query))

    def _on_operation_complete(self, category=None, filename=None, action="sorted"):
        """
        Comprehensive callback for all file operations.
        Dispatches to main thread for UI refresh and toasts securely via msg_queue.
        """
        self._safe_put_msg(lambda c=category, f=filename, a=action: self._on_operation_complete_ui(c, f, a))

    def _on_operation_complete_ui(self, category, filename, action):
        """Internal UI update for operation completion with debounced redraws and coalesced toasts."""
        if not self.winfo_exists(): return
        
        # 1. Refresh Category View and Debounced Dashboard Counts (P5)
        self._refresh_category_file_list(category)
        self._schedule_dashboard_refresh()
            
        # 2. Queue Coalesced Toast (P4)
        if filename and category:
            self._queue_coalesced_toast(category, filename, action)
        elif action != "sorted":
            self._show_toast(f"Operation {action}", icon="↩️")

    def _schedule_dashboard_refresh(self):
        """Debounce dashboard redraws to prevent CPU spikes during rapid batch operations (P5)."""
        if self._dashboard_refresh_job is not None:
            try:
                self.after_cancel(self._dashboard_refresh_job)
            except Exception:
                pass
        self._dashboard_refresh_job = self.after(250, self._debounced_dashboard_refresh)

    def _debounced_dashboard_refresh(self):
        """Execute debounced dashboard redraw on the UI thread."""
        self._dashboard_refresh_job = None
        if not self.winfo_exists():
            return
        if self.current_view == "dashboard" and "dashboard" in self.views:
            try:
                self.views["dashboard"].refresh()
            except Exception as e:
                logger.debug(f"Dashboard refresh error: {e}")

    def _queue_coalesced_toast(self, category: str, filename: str, action: str = "sorted"):
        """Coalesce rapid file sorting operations into a single consolidated toast notification (P4)."""
        self._pending_toast_items.append({
            'category': category,
            'filename': filename,
            'action': action
        })
        if self._toast_coalesce_job is not None:
            try:
                self.after_cancel(self._toast_coalesce_job)
            except Exception:
                pass
        self._toast_coalesce_job = self.after(300, self._flush_coalesced_toast)

    def _flush_coalesced_toast(self):
        """Render a single summary toast for accumulated file operations (P4)."""
        self._toast_coalesce_job = None
        if not self.winfo_exists() or not self._pending_toast_items:
            return

        items = list(self._pending_toast_items)
        self._pending_toast_items.clear()

        if len(items) == 1:
            item = items[0]
            msg = f"{item['filename']} {item['action']} to {item['category']}"
        else:
            categories = list(dict.fromkeys(item['category'] for item in items))
            if len(categories) == 1:
                target_desc = categories[0]
            elif len(categories) == 2:
                target_desc = f"{categories[0]} and {categories[1]}"
            else:
                target_desc = f"{categories[0]}, {categories[1]}, and {len(categories) - 2} more"
            msg = f"Sorted {len(items)} files to {target_desc}"

        self._show_toast(msg, icon="✅", action_text="Undo")

    def _show_toast(self, message, icon="✅", action_text=None, action_callback=None):
        """Display a professional slide-in toast notification, closing any existing toast."""
        if action_text == "Undo":
            action_callback = self.undo_last_action

        # Cleanly dismiss previous active toast if still visible
        if hasattr(self, '_active_toast') and self._active_toast is not None:
            try:
                if self._active_toast.winfo_exists():
                    self._active_toast.destroy()
            except Exception:
                pass
            self._active_toast = None

        try:
            self._active_toast = ToastNotification(
                self, 
                message=message, 
                icon=icon, 
                action_text=action_text, 
                action_callback=action_callback,
                colors=self.COLORS
            )
        except Exception as e:
            logger.debug(f"Toast notification display failed: {e}")


    def _refresh_category_file_list(self, category=None):
        """Refresh the file list and counts for a category."""
        if category:
            view_name = f"category_{category}"
            if view_name in self.views:
                view = self.views[view_name]
                if hasattr(view, 'refresh'):
                    view.refresh()
        self._refresh_category_counts()
    
    def _close_category_content(self):
        """Close the category content panel."""
        if hasattr(self, 'category_content_frame'):
            try:
                if self.category_content_frame.winfo_exists():
                    self.category_content_frame.destroy()
                    logger.info("Category content closed")
            except:
                pass

    # --- Utility Methods ---
    
    def add_log_entry(self, message: str):
        """Add entry to log buffer (True Thread-safe)."""
        # NO Tkinter calls here! This is executed by background logger threads.
        if not hasattr(self, '_log_buffer'):
            self._log_buffer = []
        
        # Buffer the message in memory (thread safe in python due to GIL for append)
        self._log_buffer.append(message)
        
        # Dispatch UI update securely to main thread via queue
        self._safe_put_msg(self._add_log_entry_ui)

    def _add_log_entry_ui(self, message=None):
        """Internal UI update for logs on Main Thread."""
        try:
            if not self.winfo_exists(): return
            
            if not hasattr(self, '_log_buffer'):
                self._log_buffer = []

            # If we were called without a specific message, it means we should flush the buffer
            messages_to_process = []
            if message:
                messages_to_process.append(message)
            else:
                messages_to_process = self._log_buffer[:]
                self._log_buffer = []
                
            if not messages_to_process:
                return

            if hasattr(self, 'log_textbox') and self.log_textbox.winfo_exists():
                self.log_textbox.configure(state="normal")
                for msg in messages_to_process:
                    self.log_textbox.insert("end", msg + "\n")
                self.log_textbox.see("end")
                self.log_textbox.configure(state="disabled")
            else:
                # UI not ready yet, store back in buffer
                self._log_buffer.extend(messages_to_process)
                if len(self._log_buffer) > 2000: # Safety cap
                    self._log_buffer = self._log_buffer[-2000:]
        except Exception as e:
            logger.debug(f"Log UI update failed: {e}")

    def _clear_logs(self):
        """Clear the log textbox."""
        if hasattr(self, 'log_textbox'):
            self.log_textbox.configure(state="normal")
            self.log_textbox.delete("1.0", "end")
            self.log_textbox.configure(state="disabled")

    def _flush_log_buffer(self):
        """Immediately insert all buffered logs into the textbox."""
        if hasattr(self, 'log_textbox') and self.log_textbox.winfo_exists():
            if hasattr(self, '_log_buffer') and self._log_buffer:
                self.log_textbox.configure(state="normal")
                for msg in self._log_buffer:
                    self.log_textbox.insert("end", msg + "\n")
                self.log_textbox.see("end")
                self.log_textbox.configure(state="disabled")
                self._log_buffer = []

    def _on_error(self, message: str):
        """Standardized error callback for professional Toast feedback."""
        self.after(0, lambda: self._show_toast(message, icon="⚠️", action_text=None))

    def _export_audit_log(self):
        """Open the audit logs directory and show a short summary."""
        from core.auditor import auditor
        audit_path = auditor.audit_dir
        summary = auditor.get_audit_summary()
        if audit_path.exists() and summary["log_files"] > 0:
            retention = summary["retention_days"]
            retention_label = "forever" if retention <= 0 else f"{retention} days"
            messagebox.showinfo(
                "Audit Log",
                f"Entries: {summary['entries']:,} (one line per sort action)\n"
                f"Log files: {summary['log_files']}\n"
                f"Retention: {retention_label}\n\n"
                "Opening audit folder…",
            )
            if sys.platform == "win32":
                os.startfile(audit_path)
            else:
                subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(audit_path)])
        else:
            messagebox.showinfo("No Logs", "No audit logs have been generated yet.")

    def _setup_window_icon(self):
        """Load and set the application icon, protecting against GC and theme changes."""
        try:
            icon_ico = resource_path("resources/icon.ico")
            icon_png = resource_path("resources/icon.png")
            
            ico_loaded = False
            if sys.platform == "win32" and os.path.exists(icon_ico):
                try:
                    self.iconbitmap(default=icon_ico)
                    self.iconbitmap(icon_ico)
                    ico_loaded = True
                except Exception as e:
                    logger.debug(f"iconbitmap error: {e}")
            
            if not ico_loaded and os.path.exists(icon_png):
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(icon_png)
                    resolutions = [16, 20, 24, 32, 40, 48, 64, 128, 256]
                    self._window_icon_photos = [
                        ImageTk.PhotoImage(img.resize((s, s), Image.Resampling.LANCZOS))
                        for s in resolutions
                    ]
                    self.iconphoto(True, *self._window_icon_photos)
                except Exception as e:
                    logger.debug(f"iconphoto error: {e}")
        except Exception as e:
            logger.warning(f"Could not load branding icon: {e}")

    def sort_single_file(self):
        """Sort a single file with rapid-click protection."""
        if hasattr(self, '_manual_sorting_active') and self._manual_sorting_active:
             return
        
        filepath = filedialog.askopenfilename(title="Select a file to sort")
        if filepath:
            self._manual_sorting_active = True
            logger.info(f"Sorting file: {filepath}")
            threading.Thread(
                target=self._sort_file_thread,
                args=(filepath,),
                daemon=True
            ).start()
            self._show_view("logs")

    def _sort_file_thread(self, filepath):
        """Background thread for sorting a file."""
        try:
            system_paths = config_manager.load_system_paths()
            # Fix: Pass rename format so manual sorts also get professional naming
            config = config_manager.load_config()
            rename_format = config.get("rename_format", "")
            
            success = self.sorter.process_file(filepath, {}, system_paths, rename_format=rename_format)
            if success:
                logger.info(f"✅ Successfully sorted: {os.path.basename(filepath)}")
            else:
                logger.error(f"❌ Failed to sort: {os.path.basename(filepath)}")
        finally:
            self._manual_sorting_active = False

    def select_folder_for_sorting(self):
        """Select a folder to sort."""
        folderpath = filedialog.askdirectory(title="Select a folder to sort")
        if folderpath:
            logger.info(f"Sorting folder: {folderpath}")
            threading.Thread(
                target=self._sort_folder_thread,
                args=(folderpath,),
                daemon=True
            ).start()
            self._show_view("logs")

    def _sort_folder_thread(self, folderpath):
        """Background thread for sorting a folder recursively."""
        system_paths = config_manager.load_system_paths()
        # Fix: Pass rename format so manual folder sorts get professional naming
        config = config_manager.load_config()
        rename_format = config.get("rename_format", "")
        
        logger.info(f"Recursively sorting folder: {folderpath}")
        results = self.sorter.process_directory(folderpath, {}, system_paths, rename_format=rename_format)
        logger.info(f"✅ Folder sorted: {folderpath} ({results['success']} files processed)")

    def browse_source_folder(self):
        """Public alias for browsing a source folder to monitor."""
        return self._browse_folder()

    def _browse_folder(self):
        """Browse for folder to monitor and perform initial scan."""
        folder_path = filedialog.askdirectory(title="Select folder to monitor")
        if folder_path:
            # Phase 19: Dynamic Path Reconfiguration
            # Capture state before change
            was_running = self.service_running
            if was_running:
                self._toggle_service() # Stop it first
            
            if hasattr(self, 'folder_entry'):
                self.folder_entry.delete(0, "end")
                self.folder_entry.insert(0, folder_path)
            self.app_config["source"] = folder_path
            save_config(self.app_config)
            
            # Auto-update dashboard counts immediately
            self._refresh_category_counts()
            
            # Restart if it was running
            if was_running:
                self._toggle_service()
                messagebox.showinfo("Monitoring Switched", f"Now monitoring:\n{folder_path}")
            
            # Start initial sort in background
            threading.Thread(target=self._initial_folder_sort_thread, args=(folder_path,), daemon=True).start()

    def _initial_folder_sort_thread(self, folderpath):
        """Background thread for initial folder sort."""
        try:
            system_paths = config_manager.load_system_paths()
            copy_mode = self.copy_mode_var.get()
            dest_root = self.dest_root_entry.get().strip() if hasattr(self, 'dest_root_entry') else self.app_config.get("dest_root", "")
            
            files = []
            for root, _, filenames in os.walk(folderpath):
                for f in filenames:
                    files.append(os.path.join(root, f))
            
            if files:
                for filepath in files:
                    self.sorter.process_file(filepath, {}, system_paths, copy_mode=copy_mode, dest_root=dest_root)
                
                logger.info(f"✅ Initial scan complete for: {folderpath}")
                self.after(500, self._refresh_category_counts)
        except Exception as e:
            logger.error(f"Error during initial scan: {e}")

    def _browse_dest_root(self):
        """Browse for destination root folder."""
        folder_path = filedialog.askdirectory(title="Select Destination Root")
        if folder_path:
            # Phase 19: Dynamic Path Reconfiguration
            was_running = self.service_running
            if was_running:
                self._toggle_service() # Stop it first
                
            if hasattr(self, 'dest_root_entry'):
                self.dest_root_entry.delete(0, "end")
                self.dest_root_entry.insert(0, folder_path)
            self.app_config["dest_root"] = folder_path
            save_config(self.app_config)
            
            # Restart if it was running
            if was_running:
                self._toggle_service()
                messagebox.showinfo("Destination Updated", f"New files will be sorted to:\n{folder_path}")

    def _save_auto_sort_options(self):
        """Save auto sort specific options to config with defensive attribute checks."""
        if hasattr(self, 'dest_root_entry'):
            self.app_config["dest_root"] = self.dest_root_entry.get().strip()
        
        self.app_config["copy_mode"] = self.copy_mode_var.get()
        self.app_config["smart_rename"] = self.smart_rename_var.get()
        
        if hasattr(self, 'rename_format_entry'):
            self.app_config["rename_format"] = self.rename_format_entry.get().strip()
            
        save_config(self.app_config)
        logger.info("Auto sort options saved.")

    def _toggle_rename_options(self):
        """Show/hide rename format entry."""
        if hasattr(self, 'rename_format_frame'):
            if self.smart_rename_var.get():
                self.rename_format_frame.pack(side="left")
            else:
                self.rename_format_frame.pack_forget()
        self._save_auto_sort_options()

    def _update_service_status_ui(self):
        """Update the sidebar status indicator based on actual service state using modular sidebar."""
        is_running = self.service_running
        
        # Also check windows service if applicable
        if sys.platform == "win32" and not is_running:
            try:
                import win32serviceutil
                status = win32serviceutil.QueryServiceStatus('SmartFileSorterService')[1]
                if status == 4: # 4 is SERVICE_RUNNING
                    is_running = True
            except:
                pass
        
        if hasattr(self, 'sidebar'):
            self.sidebar.update_status(is_running)

    def _stop_file_watcher(self):
        """Stop the file watcher via controller."""
        self.service_controller.stop()
    
    def _refresh_category_counts(self):
        """Refresh the category counts on the dashboard."""
        if hasattr(self, 'views') and 'dashboard' in self.views:
            self.after(0, self._update_category_counts)


    
    def _refresh_active_view(self):
        """Force-refreshes the current view from cache if it supports it."""
        if self.current_view in self.views:
            view: Any = self.views[self.current_view]
            if view and hasattr(view, 'populate_file_list'):
                view.populate_file_list()
            elif self.current_view.startswith("category_"):
                # Handle dynamic category views
                cat_view: Any = self.views.get(self.current_view)
                if cat_view and hasattr(cat_view, 'populate_file_list'):
                    cat_view.populate_file_list()

    def _update_category_counts(self):
        """Update category counts in the UI."""
        try:
            counts = get_counts()
            
            # Use the new Component-based grid if available
            if hasattr(self, 'category_grid'):
                self.category_grid.refresh()
            # Fallback for backward compatibility
            elif hasattr(self, 'category_cards'):
                for category, elements in self.category_cards.items():
                    count = counts.get(category, 0)
                    if isinstance(elements, dict):
                        count_label = elements['count_label']
                        if count_label.winfo_exists():
                            count_label.configure(text=f"{count} items")
                    else: # Case where category_cards contains CategoryCard objects
                        elements.update_count(count)
            
            logger.debug(f"Category counts refreshed: {counts}")
        except Exception as e:
            logger.error(f"Error updating category counts: {e}")
    

    def _toggle_service(self):
        """Toggle monitoring service via controller."""
        success = self.service_controller.toggle()
        if success:
            self.service_running = self.service_controller.check_status()
            self._update_service_ui()
            
            # Phase 18: Safe-Start Persistence
            # Remember the user's choice for next startup
            self.app_config["auto_sort"] = self.service_running
            save_config(self.app_config)
            
        return success

    def _check_service_status(self):
        """Bridge to service controller status."""
        return self.service_controller.check_status()

    def _toggle_startup_service(self):
        """Toggle startup registration via controller."""
        return self.service_controller.toggle_startup()

    def _on_service_status_change(self, running: bool):
        """Callback from controller to sync UI safely on main thread."""
        self._safe_put_msg(lambda: self._on_service_status_change_ui(running))

    def _on_service_status_change_ui(self, running: bool):
        """Internal UI status update."""
        if not self.winfo_exists(): return
        self.service_running = running
        
        if hasattr(self, 'sidebar'):
            self.sidebar.update_status(running)

        # Update DashboardView status chip if it exists
        if "dashboard" in self.views and self.views["dashboard"]:
            d_view = self.views["dashboard"]
            if hasattr(d_view, "status_chip"):
                src_folder = "Downloads"
                try:
                    src = self.app_config.get("source")
                    if src:
                        src_folder = os.path.basename(src.rstrip("\\/")) or "Downloads"
                except Exception:
                    pass
                d_view.status_chip.update_status(running, src_folder)
            
        # Update Start/Stop button in AutoSortView/Service UI if it exists
        self._update_service_ui()
        
        # Specifically update AutoSortView if it is already loaded
        if "auto" in self.views and self.views["auto"]:
            view = self.views["auto"]
            if hasattr(view, 'app') and hasattr(view.app, 'start_btn'):
                btn_text = _("stop_monitor") if running else _("start_monitor")
                btn_color = self.COLORS["accent_destructive"] if running else self.COLORS["accent_active"]
                view.app.start_btn.configure(text=btn_text, fg_color=btn_color)

    def _update_service_ui(self):
        """Update dashboard and view buttons based on service state."""
        if hasattr(self, 'start_btn') and self.start_btn.winfo_exists():
            if self.service_running:
                self.start_btn.configure(text=_("stop_monitor"), fg_color=self.COLORS["accent_destructive"])
            else:
                self.start_btn.configure(text=_("start_monitor"), fg_color=self.COLORS["accent_active"])

    def _open_file(self, filepath):
        """Delegate to operation manager."""
        self.operation_manager.open_file(filepath)

    def _move_file_to_desktop(self, filepath, category):
        """Delegate to operation manager with refresh hook."""
        if self.operation_manager.move_to_location(filepath, category, os.path.join(os.path.expanduser("~"), "Desktop")):
             self._refresh_category_file_list(category)
             messagebox.showinfo("Success", f"Moved to Desktop:\n{os.path.basename(filepath)}")

    def _move_file_to_location(self, filepath, category):
        """Delegate to operation manager with custom dialog."""
        dest_dir = filedialog.askdirectory(title="Select Destination Folder")
        if dest_dir:
            if self.operation_manager.move_to_location(filepath, category, dest_dir):
                self._refresh_category_file_list(category)
                messagebox.showinfo("Success", f"Moved to:\n{dest_dir}")

    def _teach_ai_correction(self, filepath, current_category):
        """Refactored teaching logic using operation manager."""
        categories = sorted(list(self.sorter.CATEGORIES.keys()))
        dialog = ctk.CTkInputDialog(text=f"Correct Category for:\n{os.path.basename(filepath)}\n\nCategories: {', '.join(categories)}", title="Teach AI")
        new_category = dialog.get_input()
        
        if new_category:
            match = next((c for c in categories if c.lower() == new_category.lower()), None)
            if match:
                if self.operation_manager.teach_ai(filepath, match):
                    messagebox.showinfo("AI Learning", f"Learned: {os.path.basename(filepath)} -> {match}")
                    self._refresh_category_file_list(current_category)
            else:
                messagebox.showerror("Error", f"'{new_category}' is invalid.")

    def undo_last_action(self):
        """Delegate 'Magic Undo' toast callback to the OperationManager."""
        success = self.operation_manager.undo_last_action()
        if not success:
            self._show_toast("Nothing to undo, or file no longer exists.", icon="⚠️")

    def open_undo_panel(self):
        """Opens the full Undo History floating panel."""
        from .components.undo_panel import UndoPanel
        UndoPanel(self, self, self.sorter.brain)

    def _start_auto_sort_from_config(self):
        """Start the watcher using saved configuration (if enabled)."""
        # Phase 18: Safe-Start
        # Only start if the USER has explicitly enabled it previously.
        if not self.app_config.get("auto_sort", False):
            logger.info("Safe-Start: Auto-sort is disabled by default. Waiting for user to click Start.")
            return

        if not self.service_running:
            logger.info("Auto-starting file watcher")
            self._toggle_service()

    def _gui_check_updates(self):
        """Trigger an update check and show a message box."""
        if self.app_config.get("strict_offline_mode", True):
            messagebox.showinfo(
                "Strict Offline Mode Active",
                f"SmartFileSorter is running in Strict Offline Mode (v{config_manager.VERSION}).\n\n"
                "External update checks are prohibited for air-gapped privacy."
            )
            return

        update_info = config_manager.check_for_updates()
        if update_info["available"]:
            if messagebox.askyesno("Update Available", f"A new version ({update_info['version']}) is available!\n\nWould you like to visit the download page?"):
                import webbrowser
                webbrowser.open(update_info["url"])
        else:
            messagebox.showinfo("Up to Date", f"You are running the latest version: {config_manager.VERSION}")

    def _background_update_check(self):
        """Silently check for updates and notify via Toast if found."""
        if self.app_config.get("strict_offline_mode", True):
            logger.info("[OFFLINE MODE] Background update check aborted by Strict Offline Mode.")
            return

        def _check():
            try:
                update_info = config_manager.check_for_updates()
                if update_info["available"]:
                    self._safe_put_msg(lambda: self._show_toast(
                        f"Update Available: v{update_info['version']}", 
                        icon="UPDATE", 
                        action_text="View", 
                        action_callback=lambda: self._gui_check_updates()
                    ))
            except Exception as e:
                logger.debug(f"Silent update check failed: {e}")
        
        threading.Thread(target=_check, daemon=True).start()

    def _initial_cloud_sync(self):
        """Perform a silent sync on startup."""
        if self.app_config.get("strict_offline_mode", True):
            logger.info("[OFFLINE MODE] Initial cloud sync aborted by Strict Offline Mode.")
            return

        url = self.app_config.get("remote_config_url")
        if url:
            config_manager.sync_from_cloud(url)

    def _manual_cloud_sync(self):
        """User triggered cloud sync."""
        if self.app_config.get("strict_offline_mode", True):
            messagebox.showwarning(
                "Strict Offline Mode Active",
                "Cloud sync is blocked because Strict Offline Mode is enabled.\n\n"
                "To sync configuration from a remote URL, first disable Strict Offline Mode in Settings."
            )
            return

        url = self.remote_url_var.get().strip()
        if not url:
            messagebox.showwarning("Input Required", "Please enter a valid Cloud Config URL.")
            return
            
        success = config_manager.sync_from_cloud(url)
        if success:
            messagebox.showinfo("Sync Successful", "Sorting rules updated from cloud everywhere!")
            # Reload settings in UI
            self.app_config = config_manager.load_config()
        else:
            messagebox.showerror("Sync Failed", "Could not reach the cloud URL. Check your internet or link.")


    def _on_ai_toggle(self):
        """Syncs the UI AI toggle with the core sorting logic."""
        is_on = self.ai_enabled.get()
        self.sorter.ai_enabled = is_on
        
        if is_on:
            # Check for AI 'Eyes' (OCR Engine)
            if not self.sorter.is_tesseract_available():
                logger.warning("AI Enabled but OCR Engine (Tesseract) is missing.")
                
                # Ask user if they want to see instructions
                if messagebox.askyesno("AI Setup Required", "AI is enabled, but the 'OCR Engine' (Tesseract) is missing from your system.\n\nWithout it, the AI cannot 'Read' text inside images/PDFs.\n\nWould you like to see the download link?"):
                    import webbrowser
                    webbrowser.open("https://github.com/UB-Mannheim/tesseract/wiki")
            else:
                logger.info("Deep AI Content Scanning enabled.")
        else:
            logger.info("Deep AI Content Scanning disabled.")

    def _show_decision_trace(self, file_path: str):
        """Displays the AI decision reasoning for a sorted file."""
        trace = self.sorter.brain.get_decision_trace(file_path)
        messagebox.showinfo("Compliance Audit Trace", f"File: {os.path.basename(file_path)}\n\nReasoning:\n{trace}")

    def _on_close(self):
        """Handle application shutdown: stop services and save state."""
        try:
            logger.info("Application shutting down...")
            
            # Cancel debounced timers
            if self._toast_coalesce_job is not None:
                try: self.after_cancel(self._toast_coalesce_job)
                except Exception: pass
                self._toast_coalesce_job = None

            if self._dashboard_refresh_job is not None:
                try: self.after_cancel(self._dashboard_refresh_job)
                except Exception: pass
                self._dashboard_refresh_job = None

            if self._active_toast is not None:
                try:
                    if self._active_toast.winfo_exists():
                        self._active_toast.destroy()
                except Exception: pass
                self._active_toast = None

            # Flush background indexing queue cleanly
            if hasattr(self, 'sorter') and hasattr(self.sorter, 'brain'):
                try:
                    self.sorter.brain.flush_indexing_queue(timeout=1.0)
                except Exception:
                    pass

            # Stop background services via controller
            if hasattr(self, 'service_controller') and self.service_controller:
                self.service_controller.stop()
                
            # Save window geometry
            self.app_config["geometry"] = self.geometry()
            save_config(self.app_config)
            
            self.destroy()
            sys.exit(0)
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            try:
                self.destroy()
            except:
                pass
            sys.exit(1)

def main():
    """Main entry point to run the application."""
    app = App()
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()


SmartFileSorterApp = App

if __name__ == "__main__":
    main()
