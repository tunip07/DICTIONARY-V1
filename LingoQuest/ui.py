from __future__ import annotations

import os
import platform
from tkinter import font as tkfont
import tkinter as tk
import customtkinter as ctk


PRIVATE_FONT_FILES = (
    "SpaceGrotesk-Bold.ttf",
    "SpaceGrotesk-Regular.ttf",
    "SpaceGrotesk-Medium.ttf",
    "Inter-Regular.ttf",
)


def _normalize_ctk_font(font_value):
    if isinstance(font_value, ctk.CTkFont):
        return font_value

    if isinstance(font_value, tuple) and len(font_value) >= 2:
        family = str(font_value[0])
        family_lower = family.strip().lower()
        if not any(hint in family_lower for hint in MONO_FONT_HINTS) and not any(
            hint in family_lower for hint in ("emoji", "symbol", "fluent")
        ):
            family = "Space Grotesk"
        size = abs(int(font_value[1])) or 13
        weight = "normal"
        slant = "roman"

        for part in font_value[2:]:
            part_str = str(part).lower()
            if part_str in {"bold", "normal"}:
                weight = part_str
            elif part_str in {"italic", "roman"}:
                slant = "italic" if part_str == "italic" else "roman"

        return ctk.CTkFont(family=family, size=size, weight=weight, slant=slant)

    return font_value


def patch_customtkinter_font_support() -> None:
    if getattr(ctk, "_lingoquest_font_patch", False):
        return

    def wrap_method(method):
        def patched(self, *args, __method=method, **kwargs):
            if "font" in kwargs:
                kwargs["font"] = _normalize_ctk_font(kwargs["font"])
            return __method(self, *args, **kwargs)

        return patched

    for widget_name in (
        "CTkButton",
        "CTkLabel",
        "CTkEntry",
        "CTkTextbox",
        "CTkCheckBox",
        "CTkRadioButton",
        "CTkOptionMenu",
    ):
        widget_cls = getattr(ctk, widget_name, None)
        if widget_cls is None:
            continue
        widget_cls.__init__ = wrap_method(widget_cls.__init__)
        if hasattr(widget_cls, "configure"):
            widget_cls.configure = wrap_method(widget_cls.configure)

    ctk._lingoquest_font_patch = True


def load_private_fonts(base_dir: str) -> None:
    if platform.system() != "Windows":
        return

    font_dir = os.path.join(base_dir, "assets", "fonts")
    try:
        from ctypes import windll
    except Exception:
        return

    for font_name in PRIVATE_FONT_FILES:
        font_path = os.path.join(font_dir, font_name)
        if not os.path.exists(font_path):
            continue
        try:
            windll.gdi32.AddFontResourceW(font_path)
        except Exception:
            pass

    try:
        windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)
    except Exception:
        pass


UI_PALETTE = {
    "bg_top": "#0a0a1a",
    "bg_bottom": "#1a0a2e",
    "bg_mid": "#11142b",
    "dot": "#24294a",
    "glass": "#14182c",
    "glass_alt": "#171c34",
    "glass_border": "#28345a",
    "glass_hover": "#3b4f86",
    "text": "#f8fbff",
    "muted": "#9b99b7",
    "section": "#7f7699",
    "accent_start": "#7c3aed",
    "accent_end": "#2563eb",
    "accent_cyan": "#00d4ff",
    "accent_teal": "#3dd9c6",
    "success": "#2dd4bf",
    "warning": "#fbbf24",
    "danger": "#fb7185",
    "nav_active": "#1a2340",
}

BADGE_COLORS = {
    "A1": ("#3dd9c6", "#00d4ff"),
    "A2": ("#22c55e", "#3dd9c6"),
    "B1": ("#7c3aed", "#00d4ff"),
    "B2": ("#8b5cf6", "#2563eb"),
    "C1": ("#f59e0b", "#7c3aed"),
    "C2": ("#fb7185", "#7c3aed"),
}


PREFERRED_UI_FONTS = [
    "Space Grotesk",
    "Inter",
    "Segoe UI",
    "Trebuchet MS",
    "Verdana",
    "Tahoma",
    "Arial",
    "Noto Sans",
    "Liberation Sans",
]

PREFERRED_MONO_FONTS = [
    "Consolas",
    "Cascadia Mono",
    "Courier",
    "Courier New",
    "DejaVu Sans Mono",
]

MONO_FONT_HINTS = {
    "cascadia mono",
    "consolas",
    "courier new",
    "dejavu sans mono",
    "courier",
}


def pick_font_family(root, preferred_fonts):
    try:
        available = set(tkfont.families(root))
    except Exception:
        available = set()

    for font_name in preferred_fonts:
        if font_name in available:
            return font_name

    for font_name in preferred_fonts:
        if " " not in font_name:
            return font_name

    return preferred_fonts[0]


def init_font_preferences(app):
    app.ui_font_family = pick_font_family(app, PREFERRED_UI_FONTS)
    app.ui_mono_font_family = pick_font_family(app, PREFERRED_MONO_FONTS)
    _configure_named_fonts(app)
    try:
        app.option_add("*Font", (app.ui_font_family, 15))
    except Exception:
        pass


def init_app_font_constants(app) -> None:
    try:
        available_fonts = set(tkfont.families(app))
    except Exception:
        available_fonts = set()

    hero_family = "Space Grotesk" if "Space Grotesk" in available_fonts else getattr(app, "ui_font_family", PREFERRED_UI_FONTS[0])
    body_family = hero_family
    if "Segoe UI Emoji" in available_fonts:
        icon_family = "Segoe UI Emoji"
    elif "Segoe Fluent Icons" in available_fonts:
        icon_family = "Segoe Fluent Icons"
    elif "Segoe UI Symbol" in available_fonts:
        icon_family = "Segoe UI Symbol"
    else:
        icon_family = body_family

    app.FONT_HERO = ctk.CTkFont(family=hero_family, size=66, weight="bold")
    app.FONT_TITLE = ctk.CTkFont(family=hero_family, size=34, weight="bold")
    app.ui_font_family = body_family
    app.icon_font_family = icon_family
    app.FONT_BUTTON = ctk.CTkFont(family=body_family, size=14, weight="bold")
    app.FONT_BODY = ctk.CTkFont(family=body_family, size=16)
    app.FONT_BADGE = ctk.CTkFont(family=body_family, size=12, weight="bold")
    app.FONT_INPUT = ctk.CTkFont(family=body_family, size=22)
    app.FONT_ICON = ctk.CTkFont(family=icon_family, size=22)
    app.FONT_ICON_LARGE = ctk.CTkFont(family=icon_family, size=30)


def _configure_named_fonts(app):
    for font_name in (
        "TkDefaultFont",
        "TkTextFont",
        "TkMenuFont",
        "TkHeadingFont",
        "TkCaptionFont",
        "TkSmallCaptionFont",
        "TkTooltipFont",
        "TkFixedFont",
        "TkIconFont",
    ):
        try:
            named_font = tkfont.nametofont(font_name, root=app)
        except Exception:
            continue

        family = app.ui_mono_font_family if font_name == "TkFixedFont" else app.ui_font_family
        try:
            named_font.configure(family=family)
        except Exception:
            pass


def _font_tuple(family: str, size: int, weight: str = "normal", slant: str = "roman") -> tuple:
    parts = [family, size]
    if weight != "normal":
        parts.append(weight)
    if slant != "roman":
        parts.append(slant)
    return tuple(parts)


def _is_mono_family(font_family: str) -> bool:
    return font_family.strip().lower() in MONO_FONT_HINTS


def _actual_font(widget, font_value):
    try:
        return tkfont.Font(root=widget, font=font_value).actual()
    except Exception:
        return None


def apply_font_preferences(root_widget) -> None:
    for child in root_widget.winfo_children():
        try:
            font_value = child.cget("font")
        except Exception:
            font_value = None

        font_actual = _actual_font(child, font_value) if font_value else None
        if font_actual:
            target_family = (
                getattr(root_widget, "ui_mono_font_family", PREFERRED_MONO_FONTS[0])
                if _is_mono_family(str(font_actual.get("family", "")))
                else getattr(root_widget, "ui_font_family", PREFERRED_UI_FONTS[0])
            )
            try:
                child.configure(
                    font=_font_tuple(
                        target_family,
                        abs(int(font_actual.get("size", 13))) or 13,
                        str(font_actual.get("weight", "normal")),
                        str(font_actual.get("slant", "roman")),
                    )
                )
            except Exception:
                pass

        apply_font_preferences(child)


def ui_font(app, size: int, weight: str = "normal", slant: str = "roman") -> tuple:
    return _font_tuple(getattr(app, "ui_font_family", PREFERRED_UI_FONTS[0]), size, weight, slant)


def mono_font(app, size: int, weight: str = "normal", slant: str = "roman") -> tuple:
    return _font_tuple(getattr(app, "ui_mono_font_family", PREFERRED_MONO_FONTS[0]), size, weight, slant)


def blend_hex(start: str, end: str, ratio: float) -> str:
    ratio = max(0.0, min(1.0, ratio))
    start = start.lstrip("#")
    end = end.lstrip("#")
    start_rgb = tuple(int(start[i : i + 2], 16) for i in (0, 2, 4))
    end_rgb = tuple(int(end[i : i + 2], 16) for i in (0, 2, 4))
    blended = tuple(int(a + (b - a) * ratio) for a, b in zip(start_rgb, end_rgb))
    return "#{:02x}{:02x}{:02x}".format(*blended)


def build_gradient_text_row(
    parent,
    text: str,
    font,
    start_color: str | None = None,
    end_color: str | None = None,
    space_color: str | None = None,
):
    start_color = start_color or UI_PALETTE["accent_cyan"]
    end_color = end_color or UI_PALETTE["accent_start"]
    space_color = space_color or UI_PALETTE["text"]

    for child in parent.winfo_children():
        child.destroy()

    for index, char in enumerate(text):
        if char == " ":
            label = ctk.CTkLabel(
                parent,
                text=" ",
                font=font,
                text_color=space_color,
                fg_color="transparent",
            )
            label.pack(side="left")
            continue

        ratio = index / max(len(text) - 1, 1)
        label = ctk.CTkLabel(
            parent,
            text=char,
            font=font,
            text_color=blend_hex(start_color, end_color, ratio),
            fg_color="transparent",
        )
        label.pack(side="left")


def draw_cosmic_background(canvas: tk.Canvas, width: int, height: int) -> None:
    width = max(1, int(width))
    height = max(1, int(height))
    canvas.delete("all")

    steps = max(height, 1)
    for y in range(steps):
        ratio = y / max(steps - 1, 1)
        canvas.create_line(
            0,
            y,
            width,
            y,
            fill=blend_hex(UI_PALETTE["bg_top"], UI_PALETTE["bg_bottom"], ratio),
        )

    glow_color = blend_hex(UI_PALETTE["accent_start"], UI_PALETTE["accent_end"], 0.4)
    canvas.create_oval(
        width * 0.22,
        -height * 0.12,
        width * 0.78,
        height * 0.42,
        fill=glow_color,
        outline="",
        stipple="gray25",
    )
    canvas.create_oval(
        width * 0.32,
        height * 0.02,
        width * 0.68,
        height * 0.26,
        fill=blend_hex(UI_PALETTE["accent_cyan"], UI_PALETTE["bg_mid"], 0.7),
        outline="",
        stipple="gray50",
    )

    dot_gap = 32
    for x in range(0, width + dot_gap, dot_gap):
        for y in range(0, height + dot_gap, dot_gap):
            radius = 1 if (x // dot_gap + y // dot_gap) % 4 else 2
            canvas.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill=UI_PALETTE["dot"],
                outline="",
            )


def install_cosmic_background(frame: tk.Widget) -> tk.Canvas:
    canvas = tk.Canvas(frame, highlightthickness=0, bd=0, relief="flat", bg=UI_PALETTE["bg_top"])
    canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
    try:
        canvas.tk.call("lower", canvas._w)
    except Exception:
        pass

    def redraw(event=None):
        width = max(frame.winfo_width(), getattr(event, "width", 1), 1)
        height = max(frame.winfo_height(), getattr(event, "height", 1), 1)
        draw_cosmic_background(canvas, width, height)

    frame.bind("<Configure>", redraw, add="+")
    try:
        frame.after(30, redraw)
    except Exception:
        pass
    return canvas


def glass_frame_style(border_color: str | None = None) -> dict:
    return {
        "fg_color": UI_PALETTE["glass"],
        "border_width": 1,
        "border_color": border_color or UI_PALETTE["glass_border"],
        "corner_radius": 22,
    }


def glass_button_style() -> dict:
    return {
        "fg_color": UI_PALETTE["glass_alt"],
        "hover_color": UI_PALETTE["nav_active"],
        "border_width": 1,
        "border_color": UI_PALETTE["glass_border"],
        "corner_radius": 999,
        "text_color": UI_PALETTE["text"],
    }


def primary_button_style() -> dict:
    return {
        "fg_color": UI_PALETTE["accent_start"],
        "hover_color": UI_PALETTE["accent_end"],
        "corner_radius": 999,
        "text_color": UI_PALETTE["text"],
        "border_width": 1,
        "border_color": blend_hex(UI_PALETTE["accent_start"], UI_PALETTE["accent_end"], 0.6),
    }


def bind_glow_hover(widget, normal_color: str | None = None, hover_color: str | None = None) -> None:
    normal = normal_color or UI_PALETTE["glass_border"]
    hover = hover_color or UI_PALETTE["accent_cyan"]

    def on_enter(_event):
        try:
            widget.configure(border_color=hover)
        except Exception:
            pass

    def on_leave(_event):
        try:
            widget.configure(border_color=normal)
        except Exception:
            pass

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


def bind_entry_glow(entry_widget, normal_color: str | None = None, focus_color: str | None = None) -> None:
    normal = normal_color or UI_PALETTE["glass_border"]
    focus = focus_color or UI_PALETTE["accent_cyan"]

    def on_focus_in(_event):
        try:
            entry_widget.configure(border_color=focus)
        except Exception:
            pass

    def on_focus_out(_event):
        try:
            entry_widget.configure(border_color=normal)
        except Exception:
            pass

    entry_widget.bind("<FocusIn>", on_focus_in, add="+")
    entry_widget.bind("<FocusOut>", on_focus_out, add="+")


def badge_colors(level: str) -> tuple[str, str]:
    return BADGE_COLORS.get(level or "", (UI_PALETTE["accent_start"], UI_PALETTE["accent_end"]))
