# login page theme change
"""
Central Theme and Design Tokens for DevNova - SmartSorter.
Modern Light Shell Design System (1440x900 Reference Specification).
Strict 8px grid, WCAG AA contrast compliance (>= 4.5:1), and legacy compatibility.
"""
from __future__ import annotations
import os
import sys
import ctypes
from typing import Dict, Any, List, Tuple, Optional
import customtkinter as ctk

# ── 1. DUAL-MODE DESIGN TOKENS (LIGHT & DARK SPECIFICATION) ───────────────────
COLOR_PAGE_BG = ("#F6F7F9", "#0B0F19")
COLOR_SURFACE = ("#FFFFFF", "#161F30")
COLOR_BORDER = ("#E6E9EF", "#232F46")
COLOR_BORDER_HOVER = ("#D5DBE5", "#334155")
COLOR_TEXT = ("#0F172A", "#F8FAFC")
COLOR_TEXT_SECONDARY = ("#3B4557", "#94A3B8")
COLOR_MUTED = ("#5B6577", "#64748B")
COLOR_TEXT_MUTED = ("#5B6577", "#64748B")
COLOR_HEADING_MUTED = ("#64748B", "#94A3B8")

# Accent Tokens (Teal / Jade)
COLOR_ACCENT = "#0B8F7E"
COLOR_ACCENT_TINT = ("#E6F5F2", "#0D2E2B")
COLOR_ACCENT_RING = ("#BFE5DD", "#134E48")
COLOR_ACCENT_ACTIVE_ICON = ("#0B7F70", "#14B8A6")
COLOR_ACCENT_HOVER = ("#097A6B", "#0D9488")
COLOR_LINK_FOCUS = ("#3B5BDB", "#60A5FA")

# Status & Feedback
COLOR_SUCCESS_DOT = "#16A34A"
COLOR_SUCCESS_TEXT = ("#15803D", "#4ADE80")
COLOR_SUCCESS = "#16A34A"
COLOR_WARNING = "#F59E0B"
COLOR_DANGER = "#EF4444"
COLOR_DANGER_HOVER = "#B91C1C"

# Neutral controls, tags, and chips
COLOR_NEUTRAL_TRACK = ("#EEF1F6", "#1E293B")
COLOR_NEUTRAL_TAG = ("#EEF1F6", "#1E293B")
COLOR_CHIP_BORDER = ("#D9DEE7", "#334155")

# Amber Tile & Button Tokens
COLOR_AMBER_BUTTON = "#F59E0B"
COLOR_AMBER_TILE_BG = ("#FFF8EA", "#261C0E")
COLOR_AMBER_TILE_BORDER = ("#F3DDB0", "#4A3515")
COLOR_AMBER_ROW_BORDER = ("#F1E0B8", "#3D2C12")
COLOR_AMBER_BIG_NUMBER = ("#B45309", "#F59E0B")
COLOR_AMBER_TAG_BG = ("#FDEBC4", "#3D2A10")
COLOR_AMBER_TAG_TEXT = ("#8A4B08", "#FCD34D")
COLOR_AMBER_BUTTON_TEXT = ("#2A1700", "#FFFFFF")

# Category Colors
CAT_COLOR_DOCUMENTS = "#3B6CF0"
CAT_COLOR_IMAGES = "#14B8A6"
CAT_COLOR_SCREENSHOTS = "#EC4899"
CAT_COLOR_FINANCE = "#F59E0B"

CATEGORY_FALLBACK_PALETTE: List[str] = [
    "#8B5CF6",  # purple
    "#0EA5E9",  # sky blue
    "#EF4444",  # red
    "#84CC16",  # lime
    "#64748B",  # slate
]

CATEGORY_COLORS: Dict[str, str] = {
    "Documents": CAT_COLOR_DOCUMENTS,
    "Images": CAT_COLOR_IMAGES,
    "Videos": "#8B5CF6",
    "Audio": "#84CC16",
    "Archives": "#EF4444",
    "Screenshots": CAT_COLOR_SCREENSHOTS,
    "Spreadsheets": "#10B981",
    "Presentations": "#F97316",
    "Finance": CAT_COLOR_FINANCE,
    "Invoices": "#D97706",
    "Academic": "#7C3AED",
    "Medical": "#0284C7",
    "Legal": "#4F46E5",
    "Books": "#A855F7",
    "Code": "#0D9488",
    "Design": "#E11D48",
    "3D Models": "#6366F1",
    "Executables": "#475569",
    "Databases": "#2563EB",
    "Fonts": "#DB2777",
    "Backups": "#78716C",
    "WhatsApp": "#22C55E",
    "Others": "#64748B",
}


def get_category_color(category_name: str) -> str:
    """Return specific category color or deterministic fallback from palette."""
    if not category_name:
        return CATEGORY_FALLBACK_PALETTE[4]
    name_clean = category_name.strip()
    if name_clean in CATEGORY_COLORS:
        return CATEGORY_COLORS[name_clean]
    idx = abs(hash(name_clean)) % len(CATEGORY_FALLBACK_PALETTE)
    return CATEGORY_FALLBACK_PALETTE[idx]


# ── 2. GEOMETRY & SPACING (8px Grid & Exact Radii) ───────────────────────────
GRID_8 = 8
SPACING_GAP_TILES = 16
SPACING_SECTION = 30
SPACING_XS = 8
SPACING_SM = 16
SPACING_MD = 24
SPACING_LG = 32

RADIUS_TILE = 24
RADIUS_PROMPT_BOX = 28
RADIUS_PILL = 99
RADIUS_BUTTON = 12
RADIUS_BUTTON_ALT = 13
RADIUS_NAV_ITEM = 12
RADIUS_SEGMENTED_OUTER = 12
RADIUS_SEGMENTED_INNER = 9
RADIUS_BAR = 6
RADIUS_CARD = 24
BORDER_THIN = 1

# ── 3. FONT REGISTRATION & TYPOGRAPHY STACK ──────────────────────────────────
FR_PRIVATE = 0x10


def _register_bundled_fonts() -> bool:
    if sys.platform != "win32":
        return False
    fonts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "fonts")
    if not os.path.isdir(fonts_dir):
        return False
    registered = False
    for fname in os.listdir(fonts_dir):
        if fname.lower().endswith((".ttf", ".otf")):
            fpath = os.path.join(fonts_dir, fname)
            try:
                res = ctypes.windll.gdi32.AddFontResourceExW(fpath, FR_PRIVATE, 0)
                if res > 0:
                    registered = True
            except Exception:
                pass
    return registered


_BUNDLED_REGISTERED = _register_bundled_fonts()


def _resolve_font_family() -> str:
    # Avoid spinning up a temporary tk.Tk() at module import time,
    # which takes ~1.6 seconds and can cause Tcl runtime conflicts.
    if sys.platform == "win32":
        if _BUNDLED_REGISTERED:
            return "Plus Jakarta Sans"
        return "Segoe UI"
    return "Helvetica"


FONT_FAMILY = _resolve_font_family()


BASE_FONT_SIZE = 14

_FONT_CACHE: Dict[Tuple[str, int, str], ctk.CTkFont] = {}


def clear_font_cache() -> None:
    """Clear cached CTkFont instances (e.g. on font size change or root recreation)."""
    _FONT_CACHE.clear()


def set_base_font_size(size: int):
    global BASE_FONT_SIZE
    try:
        new_size = max(10, min(24, int(size)))
        if new_size != BASE_FONT_SIZE:
            BASE_FONT_SIZE = new_size
            clear_font_cache()
    except Exception:
        BASE_FONT_SIZE = 14


def get_font(size: int, weight: str = "normal") -> ctk.CTkFont:
    """Helper to generate standardized fonts for the active family with scaling and singleton caching."""
    scale = BASE_FONT_SIZE / 14.0
    adjusted_size = max(8, int(round(size * scale)))
    w = "bold" if weight in ("bold", "800", "700", "600", "semibold") else "normal"
    cache_key = (FONT_FAMILY, adjusted_size, w)
    cached = _FONT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    font = ctk.CTkFont(family=FONT_FAMILY, size=adjusted_size, weight=w)
    _FONT_CACHE[cache_key] = font
    return font


# Typography presets (Phase 3.2 P6: Responsive typography scaled for laptops)
FONT_GREETING_1 = lambda: get_font(28, "bold")
FONT_GREETING_2 = lambda: get_font(28, "bold")
FONT_EYEBROW = lambda: get_font(12, "bold")
FONT_TILE_TITLE = lambda: get_font(17, "bold")
FONT_BIG_NUMBER = lambda: get_font(52, "bold")
FONT_BODY = lambda: get_font(14, "normal")
FONT_LABEL = lambda: get_font(13, "bold")
FONT_INPUT = lambda: get_font(18, "normal")

THEME_FONTS = {
    "kpi": lambda: get_font(28, "bold"),
    "title": lambda s=20, w="bold": get_font(s, w),
    "header": lambda s=15, w="bold": get_font(s, w),
    "body": lambda s=14, w="normal": get_font(s, w),
    "small": lambda s=12, w="normal": get_font(s, w),
    "greeting": lambda: get_font(28, "bold"),
    "eyebrow": lambda: get_font(12, "bold"),
    "big_number": lambda: get_font(52, "bold"),
    "tile_title": lambda: get_font(17, "bold"),
    "label": lambda: get_font(13, "normal"),
    "input": lambda: get_font(18, "normal"),
}

# ── 4. COLOR UTILITIES & PRESET MANAGEMENT ───────────────────────────────────

def adjust_hex_brightness(hex_color: str, factor: float) -> str:
    h = str(hex_color).lstrip("#")
    if len(h) == 3:
        h = "".join([c * 2 for c in h])
    if len(h) != 6:
        return hex_color
    r, g, b = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    r, g, b = int(r * factor), int(g * factor), int(b * factor)
    r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def blend_colors(fg_hex: str, bg_hex: str, factor: float = 0.15) -> str:
    f = str(fg_hex).lstrip("#")
    b = str(bg_hex).lstrip("#")
    if len(f) == 3:
        f = "".join([c * 2 for c in f])
    if len(b) == 3:
        b = "".join([c * 2 for c in b])
    if len(f) != 6 or len(b) != 6:
        return fg_hex
    fr, fg, fb = tuple(int(f[i:i+2], 16) for i in (0, 2, 4))
    br, bg, bb = tuple(int(b[i:i+2], 16) for i in (0, 2, 4))
    r = int(fr * factor + br * (1 - factor))
    g = int(fg * factor + bg * (1 - factor))
    b_val = int(fb * factor + bb * (1 - factor))
    return f"#{r:02x}{g:02x}{b_val:02x}"


THEME_PRESETS: Dict[str, Dict[str, str]] = {
    "Default": {
        "accent": "#0B8F7E",
        "bg_light": "#F6F7F9",
        "bg_dark": "#0B0F19",
        "surface_light": "#FFFFFF",
        "surface_dark": "#161F30",
        "border_light": "#E6E9EF",
        "border_dark": "#232F46",
    },
    "Ocean Blue": {
        "accent": "#2563EB",
        "bg_light": "#F0F4F8",
        "bg_dark": "#0F172A",
        "surface_light": "#FFFFFF",
        "surface_dark": "#1E293B",
        "border_light": "#E2E8F0",
        "border_dark": "#334155",
    },
    "Nordic Violet": {
        "accent": "#7C3AED",
        "bg_light": "#F5F3FF",
        "bg_dark": "#13111C",
        "surface_light": "#FFFFFF",
        "surface_dark": "#1E1B2E",
        "border_light": "#EDE9FE",
        "border_dark": "#2E284A",
    },
    "Sunset Amber": {
        "accent": "#D97706",
        "bg_light": "#FAF8F5",
        "bg_dark": "#181512",
        "surface_light": "#FFFFFF",
        "surface_dark": "#241E18",
        "border_light": "#F3EBE1",
        "border_dark": "#382D22",
    },
    "Emerald Forest": {
        "accent": "#10B981",
        "bg_light": "#F0FDF4",
        "bg_dark": "#061A14",
        "surface_light": "#FFFFFF",
        "surface_dark": "#0D2820",
        "border_light": "#DCFCE7",
        "border_dark": "#1B3B30",
    },
    "Midnight Slate": {
        "accent": "#38BDF8",
        "bg_light": "#F8FAFC",
        "bg_dark": "#020617",
        "surface_light": "#FFFFFF",
        "surface_dark": "#0F172A",
        "border_light": "#E2E8F0",
        "border_dark": "#1E293B",
    },
    "Crimson Rose": {
        "accent": "#E11D48",
        "bg_light": "#FFF1F2",
        "bg_dark": "#1A0A0E",
        "surface_light": "#FFFFFF",
        "surface_dark": "#271218",
        "border_light": "#FFE4E6",
        "border_dark": "#3D1723",
    },
}


def apply_theme_customizations(
    preset: Optional[str] = None,
    accent: Optional[str] = None,
    bg_light: Optional[str] = None,
    bg_dark: Optional[str] = None,
    surface_light: Optional[str] = None,
    surface_dark: Optional[str] = None,
    font_size: Optional[int] = None,
):
    """Apply customized colors and typography tokens globally."""
    global COLOR_PAGE_BG, COLOR_SURFACE, COLOR_BORDER, COLOR_BORDER_HOVER
    global COLOR_ACCENT, COLOR_ACCENT_TINT, COLOR_ACCENT_RING, COLOR_ACCENT_ACTIVE_ICON, COLOR_ACCENT_HOVER
    global COLOR_BG, THEME_COLORS

    if font_size is not None:
        set_base_font_size(font_size)

    # 1. Preset lookup if applicable
    if preset and preset in THEME_PRESETS:
        p = THEME_PRESETS[preset]
        accent = accent or p["accent"]
        bg_light = bg_light or p["bg_light"]
        bg_dark = bg_dark or p["bg_dark"]
        surface_light = surface_light or p["surface_light"]
        surface_dark = surface_dark or p["surface_dark"]

    def_p = THEME_PRESETS["Default"]
    accent = accent or def_p["accent"]
    b_light = bg_light or (COLOR_PAGE_BG[0] if isinstance(COLOR_PAGE_BG, (tuple, list)) else def_p["bg_light"])
    b_dark = bg_dark or (COLOR_PAGE_BG[1] if isinstance(COLOR_PAGE_BG, (tuple, list)) else def_p["bg_dark"])
    s_light = surface_light or (COLOR_SURFACE[0] if isinstance(COLOR_SURFACE, (tuple, list)) else def_p["surface_light"])
    s_dark = surface_dark or (COLOR_SURFACE[1] if isinstance(COLOR_SURFACE, (tuple, list)) else def_p["surface_dark"])

    COLOR_PAGE_BG = (b_light, b_dark)
    COLOR_SURFACE = (s_light, s_dark)
    COLOR_BG = COLOR_PAGE_BG

    COLOR_ACCENT = accent
    COLOR_ACCENT_HOVER = adjust_hex_brightness(accent, 0.88)
    COLOR_ACCENT_ACTIVE_ICON = (adjust_hex_brightness(accent, 0.85), adjust_hex_brightness(accent, 1.15))
    COLOR_ACCENT_TINT = (blend_colors(accent, b_light, 0.12), blend_colors(accent, b_dark, 0.22))
    COLOR_ACCENT_RING = (blend_colors(accent, b_light, 0.35), blend_colors(accent, b_dark, 0.45))

    THEME_COLORS["bg_app"] = COLOR_PAGE_BG
    THEME_COLORS["bg_sidebar"] = COLOR_SURFACE
    THEME_COLORS["bg_content"] = COLOR_PAGE_BG
    THEME_COLORS["bg_card"] = COLOR_SURFACE
    THEME_COLORS["accent_active"] = COLOR_ACCENT
    THEME_COLORS["accent_hover"] = COLOR_ACCENT_HOVER
    THEME_COLORS["accent_tint"] = COLOR_ACCENT_TINT
    THEME_COLORS["accent_ring"] = COLOR_ACCENT_RING
    THEME_COLORS["accent_active_icon"] = COLOR_ACCENT_ACTIVE_ICON
    THEME_COLORS["accent"] = COLOR_ACCENT
    THEME_COLORS["primary"] = COLOR_ACCENT


# ── 5. LEGACY COMPATIBILITY TOKENS ───────────────────────────────────────────
COLOR_BG = COLOR_PAGE_BG
COLOR_SURFACE_RAISED = COLOR_NEUTRAL_TRACK

THEME_COLORS: Dict[str, Any] = {
    "bg_app": COLOR_PAGE_BG,
    "bg_sidebar": COLOR_SURFACE,
    "bg_content": COLOR_PAGE_BG,
    "bg_card": COLOR_SURFACE,
    "bg_subcard": COLOR_NEUTRAL_TRACK,
    "border": COLOR_BORDER,
    "border_hover": COLOR_BORDER_HOVER,
    "text_header": COLOR_TEXT,
    "text_primary": COLOR_TEXT,
    "text_secondary": COLOR_TEXT_SECONDARY,
    "text_muted": COLOR_MUTED,
    "heading_muted": COLOR_HEADING_MUTED,
    "accent_active": COLOR_ACCENT,
    "accent_hover": COLOR_ACCENT_HOVER,
    "accent_tint": COLOR_ACCENT_TINT,
    "accent_ring": COLOR_ACCENT_RING,
    "accent_active_icon": COLOR_ACCENT_ACTIVE_ICON,
    "accent_success": COLOR_SUCCESS,
    "accent_warning": COLOR_WARNING,
    "accent_destructive": COLOR_DANGER,
    "danger": COLOR_DANGER,
    "danger_hover": COLOR_DANGER_HOVER,
    "warning": COLOR_WARNING,
    "success": COLOR_SUCCESS,
    "accent": COLOR_ACCENT,
    "primary": COLOR_ACCENT,
    "secondary": COLOR_TEXT_SECONDARY,
    "sidebar_text": COLOR_TEXT_SECONDARY,
    "sidebar_text_dim": COLOR_MUTED,
    "sidebar_btn_hover": COLOR_ACCENT_TINT,
    "link": COLOR_LINK_FOCUS,
}

THEME_CAT_COLORS = CATEGORY_COLORS
