import math
import time
import tkinter as tk

import customtkinter as ctk

from ui import apply_font_preferences, bind_glow_hover, blend_hex


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def _ease_out_cubic(value):
    value = _clamp(value)
    return 1.0 - (1.0 - value) ** 3


def _build_gradient_title(container, font):
    for child in container.winfo_children():
        child.destroy()

    title = "Adam Dictionary"
    for index, char in enumerate(title):
        if char == " ":
            spacer = ctk.CTkLabel(
                container,
                text=" ",
                font=font,
                text_color="#f8fbff",
            )
            spacer.pack(side="left")
            continue

        ratio = index / max(len(title) - 1, 1)
        label = ctk.CTkLabel(
            container,
            text=char,
            font=font,
            text_color=blend_hex("#22d3ee", "#8b5cf6", ratio),
        )
        label.pack(side="left")


def setup_intro_overlay(app):
    if app.intro_active:
        return

    app.intro_active = True
    app.intro_phase = 0
    app.intro_ready_visible = False
    app.intro_start_time = time.perf_counter()
    if hasattr(app, "bottom_nav"):
        app.bottom_nav.place_forget()

    app.intro_overlay = ctk.CTkFrame(app, fg_color="#020617", corner_radius=0)
    app.intro_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
    app.intro_overlay.lift()

    app.intro_canvas = tk.Canvas(
        app.intro_overlay,
        highlightthickness=0,
        bd=0,
        relief="flat",
        bg="#020617",
    )
    app.intro_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

    app.intro_title_frame = ctk.CTkFrame(
        app.intro_overlay,
        fg_color="#040816",
        corner_radius=12,
        border_width=1,
        border_color="#13233f",
    )

    app.intro_title_row = ctk.CTkFrame(app.intro_title_frame, fg_color="transparent")
    app.intro_title_row.pack(padx=22, pady=10)
    _build_gradient_title(app.intro_title_row, app.FONT_HERO)

    app.intro_badge_frame = ctk.CTkFrame(
        app.intro_overlay,
        fg_color="#082742",
        corner_radius=999,
        border_width=1,
        border_color="#0ea5e9",
    )

    app.intro_badge_icon = ctk.CTkLabel(
        app.intro_badge_frame,
        text="\u25ce",
        font=app.FONT_BADGE,
        text_color="#67e8f9",
    )
    app.intro_badge_icon.pack(side="left", padx=(12, 6), pady=5)

    app.intro_badge = ctk.CTkLabel(
        app.intro_badge_frame,
        text="NOW COMBINE WITH GOOGLE SEARCH ENGINE",
        font=app.FONT_BADGE,
        text_color="#d8fbff",
    )
    app.intro_badge.pack(side="left", padx=(0, 14), pady=5)

    app.intro_enter_btn = ctk.CTkButton(
        app.intro_overlay,
        text="START SEARCH   \u25b6",
        command=app.finish_intro,
        font=app.FONT_BUTTON,
        width=250,
        height=52,
        fg_color="#10335a",
        hover_color="#154474",
        border_width=1,
        border_color="#16b8e8",
        text_color="#7feaff",
        corner_radius=999,
    )
    bind_glow_hover(app.intro_enter_btn, "#155e75", "#22d3ee")

    app.intro_title_frame.place_forget()
    app.intro_badge_frame.place_forget()
    app.intro_enter_btn.place_forget()
    apply_font_preferences(app.intro_overlay)

    app.intro_after_ids = [
        app.after(1200, lambda: app._set_intro_phase(1)),
        app.after(4000, lambda: app._set_intro_phase(2)),
        app.after(5500, lambda: app._set_intro_phase(3)),
    ]
    app._animate_intro()


def set_intro_phase(app, phase):
    app.intro_phase = phase
    if phase >= 3:
        app._show_intro_ready_state()


def show_intro_ready_state(app):
    if app.intro_ready_visible or not app.intro_active:
        return
    app.intro_ready_visible = True
    app.intro_title_frame.place(relx=0.5, rely=0.78, anchor="center")
    app.intro_badge_frame.place(relx=0.5, rely=0.85, anchor="center")
    app.intro_enter_btn.place(relx=0.5, rely=0.92, anchor="center")


def animate_intro(app):
    if not app.intro_active or not hasattr(app, "intro_canvas"):
        return
    app._draw_intro_scene()
    app.intro_anim_after = app.after(33, app._animate_intro)


def draw_intro_scene(app):
    width = max(app.intro_canvas.winfo_width(), app.winfo_width(), 1)
    height = max(app.intro_canvas.winfo_height(), app.winfo_height(), 1)
    if (width, height) != app._intro_canvas_size:
        app._intro_canvas_size = (width, height)
        app._draw_intro_background(width, height)

    app.intro_canvas.delete("dynamic")

    elapsed = time.perf_counter() - app.intro_start_time
    center_x = width / 2
    center_y = height * 0.34
    globe_radius = min(width, height) * 0.12

    globe_collapse = _clamp((elapsed - 4.0) / 1.2)
    sphere_scale = 1.0 - globe_collapse
    sphere_radius = max(0.0, globe_radius * sphere_scale)

    if sphere_radius > 3:
        rotation_deg = elapsed * 55
        app.intro_canvas.create_oval(
            center_x - sphere_radius,
            center_y - sphere_radius,
            center_x + sphere_radius,
            center_y + sphere_radius,
            outline="#22d3ee",
            width=2,
            stipple="gray50",
            tags="dynamic",
        )
        app.intro_canvas.create_oval(
            center_x - sphere_radius * 1.18,
            center_y - sphere_radius * 1.18,
            center_x + sphere_radius * 1.18,
            center_y + sphere_radius * 1.18,
            outline="#6366f1",
            width=1,
            dash=(4, 6),
            stipple="gray50",
            tags="dynamic",
        )

        for step in range(4):
            phase_angle = math.radians(rotation_deg + step * 45)
            meridian_width = max(12, sphere_radius * abs(math.cos(phase_angle)) * 2)
            app.intro_canvas.create_oval(
                center_x - meridian_width / 2,
                center_y - sphere_radius,
                center_x + meridian_width / 2,
                center_y + sphere_radius,
                outline="#818cf8",
                width=1,
                stipple="gray50",
                tags="dynamic",
            )

        for ratio in (0.38, 0.7):
            ring_height = sphere_radius * ratio
            app.intro_canvas.create_oval(
                center_x - sphere_radius,
                center_y - ring_height,
                center_x + sphere_radius,
                center_y + ring_height,
                outline="#0ea5e9",
                width=1,
                stipple="gray50",
                tags="dynamic",
            )

        app.intro_canvas.create_oval(
            center_x - sphere_radius * 0.55,
            center_y - sphere_radius * 0.55,
            center_x + sphere_radius * 0.55,
            center_y + sphere_radius * 0.55,
            fill="#083344",
            outline="",
            stipple="gray25",
            tags="dynamic",
        )

    if app.intro_phase >= 1 and app.intro_phase < 2 and sphere_radius > 0:
        strand_count = 12
        for index in range(strand_count):
            strand_elapsed = elapsed - 1.2 - index * 0.08
            if strand_elapsed <= 0:
                continue
            progress = min(1.0, (strand_elapsed % 2.0) / 2.0)
            angle = math.radians(index * (360 / strand_count))
            inner_x = center_x + math.cos(angle) * sphere_radius * 0.25
            inner_y = center_y + math.sin(angle) * sphere_radius * 0.25
            outer_x = center_x + math.cos(angle) * (sphere_radius + progress * 145)
            outer_y = center_y + math.sin(angle) * (sphere_radius + progress * 145)
            app.intro_canvas.create_line(
                inner_x,
                inner_y,
                outer_x,
                outer_y,
                fill="#22d3ee",
                width=1,
                stipple="gray50",
                tags="dynamic",
            )
            app.intro_canvas.create_oval(
                outer_x - 4,
                outer_y - 4,
                outer_x + 4,
                outer_y + 4,
                fill="#ffffff",
                outline="",
                tags="dynamic",
            )

    if app.intro_phase >= 2:
        appear = _ease_out_cubic((elapsed - 4.0) / 1.05)
        card_width = min(width * 0.16, 160) * (0.74 + appear * 0.26)
        card_height = min(height * 0.25, 226) * (0.74 + appear * 0.26)
        card_center_y = center_y + (1.0 - appear) * 18
        left = center_x - card_width / 2
        top = card_center_y - card_height / 2
        right = center_x + card_width / 2
        bottom = card_center_y + card_height / 2

        dot_radius = min(width, height) * 0.19
        ray_radius = dot_radius * 1.55
        for index in range(16):
            angle = math.radians((index / 16) * 360 + elapsed * 10)
            ray_x = center_x + math.cos(angle) * ray_radius
            ray_y = center_y + math.sin(angle) * ray_radius
            px = center_x + math.cos(angle) * dot_radius
            py = center_y + math.sin(angle) * dot_radius
            app.intro_canvas.create_line(
                center_x,
                center_y,
                ray_x,
                ray_y,
                fill="#14365c",
                width=1,
                tags="dynamic",
            )
            app.intro_canvas.create_oval(
                px - 2.5,
                py - 2.5,
                px + 2.5,
                py + 2.5,
                fill="#22d3ee",
                outline="",
                tags="dynamic",
            )

        app.intro_canvas.create_rectangle(
            left - 10,
            top - 10,
            right + 10,
            bottom + 10,
            fill="",
            outline="#0d2744",
            width=2,
            tags="dynamic",
        )
        app.intro_canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            fill="#020617",
            outline="#0ea5e9",
            width=1,
            tags="dynamic",
        )
        app.intro_canvas.create_rectangle(
            left + 14,
            top + 14,
            right - 14,
            bottom - 14,
            outline="#12324e",
            width=1,
            dash=(2, 4),
            tags="dynamic",
        )

        reveal_x = left + (right - left) * appear
        app.intro_canvas.create_rectangle(
            max(left + 4, reveal_x - card_width * 0.18),
            top + 5,
            min(right - 4, reveal_x + card_width * 0.04),
            bottom - 5,
            fill="",
            outline="#12324e",
            width=8,
            stipple="gray25",
            tags="dynamic",
        )

        scan_position = top + ((elapsed * 105) % max(card_height, 1))
        app.intro_canvas.create_line(
            left + 6,
            scan_position,
            right - 6,
            scan_position,
            fill="#67e8f9",
            width=2,
            tags="dynamic",
        )

        icon_box = (
            center_x - card_width * 0.16,
            top + card_height * 0.12,
            center_x + card_width * 0.16,
            top + card_height * 0.12 + card_width * 0.32,
        )
        app.intro_canvas.create_rectangle(
            *icon_box,
            fill="#0284c7",
            outline="#38bdf8",
            width=1,
            tags="dynamic",
        )
        bar_left = icon_box[0] + 10
        for idx, ratio in enumerate((0.45, 0.75, 0.58)):
            app.intro_canvas.create_rectangle(
                bar_left + idx * 12,
                icon_box[3] - (ratio * 22) - 8,
                bar_left + idx * 12 + 6,
                icon_box[3] - 8,
                fill=("#e879f9", "#22d3ee", "#f59e0b")[idx],
                outline="",
                tags="dynamic",
            )

        line_start_y = top + card_height * 0.52
        for idx, ratio in enumerate((0.75, 0.5, 0.86)):
            app.intro_canvas.create_rectangle(
                left + card_width * 0.18,
                line_start_y + idx * 18,
                left + card_width * (0.18 + ratio * 0.62),
                line_start_y + idx * 18 + 6,
                fill=("#06b6d4", "#6366f1", "#a855f7")[idx],
                outline="",
                tags="dynamic",
            )


def draw_intro_background(app, width, height):
    app.intro_canvas.delete("all")
    app.intro_canvas.create_rectangle(0, 0, width, height, fill="#050816", outline="", tags="static")

    for y in range(0, height, 18):
        ratio = y / max(height, 1)
        app.intro_canvas.create_line(
            0,
            y,
            width,
            y,
            fill=blend_hex("#050816", "#111631", ratio),
            tags="static",
        )

    center_x = width / 2
    band_half = max(120, int(width * 0.2))
    for offset in range(-band_half, band_half + 1, 2):
        mix = 1.0 - abs(offset) / max(band_half, 1)
        color = blend_hex("#0a1022", "#201b55", mix)
        x = center_x + offset
        app.intro_canvas.create_line(x, 0, x, height, fill=color, tags="static")

    dot_gap = 36
    for x in range(0, width + dot_gap, dot_gap):
        for y in range(0, height + dot_gap, dot_gap):
            app.intro_canvas.create_oval(
                x - 1,
                y - 1,
                x + 1,
                y + 1,
                fill="#16213a",
                outline="",
                tags="static",
            )

    circle_radius = min(width, height) * 0.28
    circle_center_y = height * 0.36
    app.intro_canvas.create_oval(
        center_x - circle_radius,
        circle_center_y - circle_radius,
        center_x + circle_radius,
        circle_center_y + circle_radius,
        fill=blend_hex("#131a36", "#282269", 0.55),
        outline="",
        tags="static",
    )


def finish_intro(app):
    if not app.intro_active:
        return

    app.intro_active = False
    for after_id in app.intro_after_ids:
        try:
            app.after_cancel(after_id)
        except Exception:
            pass
    app.intro_after_ids = []

    if app.intro_anim_after:
        try:
            app.after_cancel(app.intro_anim_after)
        except Exception:
            pass
        app.intro_anim_after = None

    if hasattr(app, "intro_overlay"):
        app.intro_overlay.destroy()

    if hasattr(app, "bottom_nav"):
        app.bottom_nav.place(relx=0.5, rely=0.975, anchor="s", relwidth=0.92)
    app.show_screen(app.home_frame)
