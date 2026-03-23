import sys, os
os.environ["PYTHONUNBUFFERED"] = "1"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

from unittest.mock import MagicMock

# --- FIX HANGING ON WINDOWS (Robust Version) ---
# Bỏ qua darkdetect và tự động scale DPI để tránh treo ứng dụng trên Python 3.14+
mock_darkdetect = MagicMock()
mock_darkdetect.theme.return_value = "Dark"
sys.modules["darkdetect"] = mock_darkdetect

import customtkinter as ctk
# Vô hiệu hóa tính năng tự động phát hiện DPI có thể gây treo
ctk.ScalingTracker.activate_high_dpi_awareness = lambda: None
ctk.ScalingTracker.get_window_dpi_scaling = lambda window: 1.0
ctk.ScalingTracker.deactivate_automatic_dpi_awareness = True

import tkinter as tk
from tkinter import filedialog
from datetime import date
import base64
import ctypes
import json
import re
import subprocess
import threading
import queue
import glob
import time
import urllib.request
import urllib.parse
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET
import webbrowser

from api import (
    cache_lookup_result,
    fetch_and_cache_word,
    fetch_datamuse_collocations as api_fetch_datamuse_collocations,
    fetch_datamuse_suggestions,
    fetch_dictionary_entry,
    lookup_remote_word,
)
from crud import (
    delete_word_entries,
    delete_word_entry,
    favorite_word_entries,
    import_parsed_entries,
    parse_import_lines,
    pick_word_of_day,
    toggle_favorite_flag,
    update_entry_field,
)
from engine import SearchEngine
from storage import (
    VALID_CEFR_LEVELS,
    export_dictionary,
    load_dictionary,
    normalize_text,
    repair_text,
    save_dictionary,
)
from quiz import (
    build_daily_challenge,
    build_flashcard_round,
    build_hangman_round,
    build_matching_round,
    build_multiple_choice_question,
    build_reverse_round,
    build_scramble_round,
    crossword_candidates,
)
from intro import (
    animate_intro,
    draw_intro_background,
    draw_intro_scene,
    finish_intro as finish_intro_overlay,
    set_intro_phase,
    setup_intro_overlay as build_intro_overlay,
    show_intro_ready_state,
)
from news_panel import NewsPanel
from youtube_panel import YouTubePanel
from home_dashboard_ui import (
    C as DASHBOARD_COLORS,
    DailyChallengeCard,
    DotGrid,
    NavButton,
    RecentSearches,
    ResultPanel,
    SearchBar,
    WordOfDayCard,
    glass_frame as dashboard_glass_frame,
)
from ui import (
    UI_PALETTE,
    apply_font_preferences,
    build_gradient_text_row,
    bind_entry_glow,
    bind_glow_hover,
    blend_hex,
    glass_button_style,
    glass_frame_style,
    init_app_font_constants,
    init_font_preferences,
    install_cosmic_background,
    load_private_fonts,
    mono_font,
    patch_customtkinter_font_support,
    primary_button_style,
    ui_font,
)
from utils import load_json_state, resolve_app_file, save_json_state, today_key

DATA_FILE = str(resolve_app_file("genz_dict.json"))
STATE_FILE = str(resolve_app_file("app_state.json"))
CONFIG_FILE = str(resolve_app_file("config.json"))

try:
    with open(CONFIG_FILE, encoding="utf-8") as _cfg_file:
        _cfg = json.load(_cfg_file)
    YT_KEY = _cfg.get("youtube_api_key", "")
except Exception:
    YT_KEY = ""

# Chống crash âm thanh: Chúng ta sẽ load lười khi cần phát âm
AUDIO_ENABLED = True 

# --- THEME GAME/DASHBOARD HIỆN ĐẠI ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
patch_customtkinter_font_support()

class ModernDictApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        load_private_fonts(os.path.dirname(os.path.abspath(__file__)))
        self.title("Adam Dictionary - AI Dictionary & Gamified Dashboard")
        self.geometry("900x850")
        self.minsize(700, 700)
        init_font_preferences(self)
        init_app_font_constants(self)
        
        # Mặc định đang xem toàn bộ kho
        self.save_lock = threading.Lock() # Lock để chống lỗi Permission denied khi nhiều luồng cùng lưu file
        self.showing_favorites = False
        self.selected_words = set()  # Tập hợp từ đang được chọn (multi-select)
        
        # Load và Cấu trúc lại Data JSON 
        self.words = self.load_data()
        self.engine = SearchEngine(self.words)
        self.visible_words = []
        self.cleanup_temp_audio()
        self.score = 0
        self.search_timer = None
        self.home_search_timer = None
        self.current_home_suggestion = ""
        self.current_dict_suggestion = ""
        self.current_word_of_day = ""
        self.current_video_query = ""
        self.ui_queue = queue.Queue()
        self.intro_phase = 0
        self.intro_active = False
        self.intro_ready_visible = False
        self.intro_after_ids = []
        self.intro_anim_after = None
        self.intro_start_time = 0.0
        self._intro_canvas_size = (0, 0)
        self.app_state = self.load_state()
        self.youtube_api_key = YT_KEY
        self.recent_searches = list(self.app_state.get("recent_searches", []))
        self.daily_state = dict(self.app_state.get("daily_challenge", {}))
        self.daily_question_index = 0
        self.daily_questions = []
        self.daily_completed_today = self.daily_state.get("last_completed") == today_key()
        
        # UI Container: Dùng để chứa và đổi qua lại các màn hình
        self.container = ctk.CTkFrame(self, fg_color="#0F172A") 
        self.container.pack(fill="both", expand=True)
        
        # Khởi tạo các Màn hình (Screens) ẩn/hiện tự động thay vì Tab
        self.home_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.dict_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.add_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.game_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.news_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.youtube_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        
        self.setup_home_screen()
        self.setup_dict_screen()
        self.setup_add_screen()
        self.setup_game_screen()
        self.setup_news_screen()
        self.setup_youtube_screen()
        
        self.create_toast()
        self.init_card_pool()
        apply_font_preferences(self)
        self.bind_all("<Button-1>", self._handle_global_click, add="+")
        self.show_screen(self.home_frame)
        self.after(50, self._process_ui_queue)
        self.after(30, self.setup_intro_overlay)
        
    def show_screen(self, frame_to_show):
        for child in self.container.winfo_children():
            child.pack_forget()
        # Ẩn tất cả dropdown autocomplete
        if getattr(self, "home_ac_frame", None):
            self.home_ac_frame.place_forget()
        if getattr(self, "dict_ac_frame", None):
            self.dict_ac_frame.place_forget()
        self._clear_suggestion_state()
        frame_to_show.pack(fill="both", expand=True)
        if frame_to_show == getattr(self, 'home_frame', None):
            if hasattr(self, "home_search_entry"):
                self.home_search_entry.focus()
            if hasattr(self, 'home_stat_lbl'):
                self.home_stat_lbl.configure(text=f"{len(self.words)} words in your notebook")
            self.refresh_recent_searches()
            self.refresh_daily_challenge_panel()

    def _widget_is_descendant(self, widget, ancestor):
        current = widget
        while current is not None:
            if current == ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    def _handle_global_click(self, event):
        clicked_widget = getattr(event, "widget", None)

        home_entry = getattr(self, "home_search_entry", None)
        home_ac_frame = getattr(self, "home_ac_frame", None)
        if home_entry and home_ac_frame and str(home_ac_frame.winfo_manager()):
            inside_home = self._widget_is_descendant(clicked_widget, home_entry) or self._widget_is_descendant(clicked_widget, home_ac_frame)
            if not inside_home:
                home_ac_frame.place_forget()
                self._clear_suggestion_state(home_entry)

        dict_entry = getattr(self, "search_entry", None)
        dict_ac_frame = getattr(self, "dict_ac_frame", None)
        if dict_entry and dict_ac_frame and str(dict_ac_frame.winfo_manager()):
            inside_dict = self._widget_is_descendant(clicked_widget, dict_entry) or self._widget_is_descendant(clicked_widget, dict_ac_frame)
            if not inside_dict:
                dict_ac_frame.place_forget()
                self._clear_suggestion_state(dict_entry)

    def setup_intro_overlay(self):
        return build_intro_overlay(self)

    def _set_intro_phase(self, phase):
        return set_intro_phase(self, phase)

    def _show_intro_ready_state(self):
        return show_intro_ready_state(self)

    def _animate_intro(self):
        return animate_intro(self)

    def _draw_intro_scene(self):
        return draw_intro_scene(self)

    def _draw_intro_background(self, width, height):
        return draw_intro_background(self, width, height)

    def finish_intro(self):
        return finish_intro_overlay(self)

    def _apply_primary_button(self, button):
        button.configure(**primary_button_style())
        if not getattr(button, "_lingo_primary_bound", False):
            bind_glow_hover(
                button,
                blend_hex(UI_PALETTE["accent_start"], UI_PALETTE["accent_end"], 0.55),
                UI_PALETTE["accent_cyan"],
            )
            button._lingo_primary_bound = True

    def _apply_glass_button(self, button):
        button.configure(**glass_button_style())
        if not getattr(button, "_lingo_glass_bound", False):
            bind_glow_hover(button)
            button._lingo_glass_bound = True

    def _build_home_screen_pill(self, parent, command, width=210, height=42):
        pill = ctk.CTkFrame(
            parent,
            width=width,
            height=height,
            fg_color="#171C34",
            border_width=1,
            border_color="#324369",
            corner_radius=18,
        )
        pill.pack_propagate(False)
        bind_glow_hover(pill, "#324369", "#4C6FFF")

        label = ctk.CTkLabel(
            pill,
            text="HOME SCREEN",
            font=ui_font(self, 15, "bold"),
            text_color="#F8FBFF",
            fg_color="transparent",
        )
        label.place(relx=0.5, rely=0.5, anchor="center")

        def _go_home(_event=None):
            command()

        for widget in (pill, label):
            widget.bind("<Button-1>", _go_home)

        return pill

    def load_state(self):
        return load_json_state(
            STATE_FILE,
            default={"recent_searches": [], "daily_challenge": {"streak": 0, "last_completed": ""}},
        )

    def save_state(self):
        self.app_state["recent_searches"] = list(self.recent_searches)
        self.app_state["daily_challenge"] = dict(self.daily_state)
        save_json_state(STATE_FILE, self.app_state)

    def record_recent_search(self, word):
        normalized_word = normalize_text(word)
        if not normalized_word:
            return
        if normalized_word in self.recent_searches:
            self.recent_searches.remove(normalized_word)
        self.recent_searches.insert(0, normalized_word)
        self.recent_searches = self.recent_searches[:6]
        self.save_state()
        self.refresh_recent_searches()
            
    # ================= MIGRATION LÕI DATA OBJECT =================
    def setup_home_screen(self):
        self.home_bg_canvas = install_cosmic_background(self.home_frame)

        content = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(26, 18))

        hero = ctk.CTkFrame(content, fg_color="transparent")
        hero.pack(fill="x", pady=(0, 10))

        section_heading = ctk.CTkLabel(
            hero,
            text="SEARCH ENGINE",
            font=ui_font(self, 11, "bold"),
            text_color=UI_PALETTE["section"],
        )
        section_heading.pack(anchor="center")

        self.home_stat_lbl = ctk.CTkLabel(
            hero,
            text=f"{len(self.words)} words in your notebook",
            font=ui_font(self, 13),
            text_color="#9fb0d1",
        )
        self.home_stat_lbl.pack(anchor="center", pady=(6, 0))

        search_shell = ctk.CTkFrame(content, **glass_frame_style(UI_PALETTE["glass_border"]))
        search_shell.pack(fill="x", pady=(0, 16))
        search_shell.configure(height=86)
        search_shell.pack_propagate(False)

        search_row = ctk.CTkFrame(search_shell, fg_color="transparent")
        search_row.pack(fill="both", expand=True, padx=18, pady=14)

        search_icon = ctk.CTkLabel(
            search_row,
            text="\U0001F50D",
            font=self.FONT_ICON_LARGE,
            text_color=UI_PALETTE["accent_cyan"],
        )
        search_icon.pack(side="left", padx=(2, 12))

        home_input_frame = ctk.CTkFrame(search_row, fg_color="transparent", width=520, height=56)
        home_input_frame.pack(side="left", fill="both", expand=True, padx=(0, 16))
        home_input_frame.pack_propagate(False)

        self.home_search_var = ctk.StringVar()
        self.home_ghost_var = ctk.StringVar(value="")
        self.home_ghost_label = ctk.CTkLabel(
            home_input_frame,
            textvariable=self.home_ghost_var,
            font=self.FONT_INPUT,
            text_color="#5f7398",
            anchor="w",
        )
        self.home_ghost_label.place(x=24, rely=0.5, anchor="w")

        self.home_search_entry = ctk.CTkEntry(
            home_input_frame,
            textvariable=self.home_search_var,
            placeholder_text="Search English or Vietnamese words, meanings, or slang...",
            font=self.FONT_INPUT,
            corner_radius=24,
            border_width=1,
            border_color=UI_PALETTE["glass_border"],
            fg_color="#0c1428",
            text_color=UI_PALETTE["text"],
        )
        self.home_search_entry.pack(fill="both", expand=True)
        bind_entry_glow(self.home_search_entry, UI_PALETTE["glass_border"], UI_PALETTE["accent_cyan"])
        self.home_search_entry.bind("<Return>", self.on_home_search_enter)
        self.home_search_entry.bind("<Tab>", self.accept_home_suggestion)
        self.home_search_var.trace_add("write", lambda *a: self.debounce_home_search())

        search_btn = ctk.CTkFrame(
            search_row,
            width=190,
            height=54,
            corner_radius=999,
            fg_color=UI_PALETTE["accent_start"],
            border_width=1,
            border_color=blend_hex(UI_PALETTE["accent_start"], UI_PALETTE["accent_end"], 0.6),
        )
        search_btn.pack(side="right")
        search_btn.pack_propagate(False)
        bind_glow_hover(
            search_btn,
            blend_hex(UI_PALETTE["accent_start"], UI_PALETTE["accent_end"], 0.55),
            UI_PALETTE["accent_cyan"],
        )
        search_btn_label = ctk.CTkLabel(
            search_btn,
            text="SEARCH",
            font=ui_font(self, 14, "bold"),
            text_color=UI_PALETTE["text"],
        )
        search_btn_label.pack(expand=True)
        for widget in (search_btn, search_btn_label):
            widget.bind("<Button-1>", lambda _e: self.on_home_search_enter(None))

        shortcuts_shell = ctk.CTkFrame(content, **glass_frame_style())
        shortcuts_shell.pack(fill="x", pady=(0, 18))

        shortcut_grid = ctk.CTkFrame(shortcuts_shell, fg_color="transparent")
        shortcut_grid.pack(fill="x", padx=14, pady=14)
        for col in range(5):
            shortcut_grid.grid_columnconfigure(col, weight=1)

        shortcut_items = [
            ("\U0001F4DA", "Notebook", self.open_dict_all, UI_PALETTE["success"]),
            ("\u2795", "Import", lambda: self.show_screen(self.add_frame), UI_PALETTE["warning"]),
            ("\U0001F3AE", "Game", self.start_game, UI_PALETTE["accent_start"]),
            ("\u2B50", "Favorites", self.open_dict_fav, UI_PALETTE["danger"]),
            ("\U0001F4F0", "News", lambda: self.show_screen(self.news_frame), UI_PALETTE["accent_cyan"]),
        ]

        for idx, (icon, label, cmd, accent) in enumerate(shortcut_items):
            tile = ctk.CTkFrame(
                shortcut_grid,
                fg_color="#141a30",
                corner_radius=18,
                border_width=1,
                border_color=UI_PALETTE["glass_border"],
            )
            tile.grid(row=0, column=idx, padx=6, sticky="ew")
            bind_glow_hover(tile, UI_PALETTE["glass_border"], accent)

            icon_plate = ctk.CTkFrame(
                tile,
                width=42,
                height=42,
                corner_radius=999,
                fg_color=blend_hex(accent, UI_PALETTE["bg_mid"], 0.78),
                border_width=1,
                border_color=accent,
            )
            icon_plate.pack(side="left", padx=(12, 8), pady=10)
            icon_plate.pack_propagate(False)

            icon_lbl = ctk.CTkLabel(
                icon_plate,
                text=icon,
                font=self.FONT_ICON_LARGE,
                text_color=UI_PALETTE["text"],
            )
            icon_lbl.pack(expand=True)

            text_lbl = ctk.CTkLabel(
                tile,
                text=label,
                font=ui_font(self, 13, "bold"),
                text_color=UI_PALETTE["text"],
            )
            text_lbl.pack(side="left", padx=(0, 12))

            for widget in (tile, icon_plate, icon_lbl, text_lbl):
                widget.bind("<Button-1>", lambda _e, action=cmd: action())

        cards_grid = ctk.CTkFrame(content, fg_color="transparent")
        cards_grid.pack(fill="x")
        cards_grid.grid_columnconfigure(0, weight=1)
        cards_grid.grid_columnconfigure(1, weight=1)

        self.word_day_frame = ctk.CTkFrame(cards_grid, **glass_frame_style())
        self.word_day_frame.grid(row=0, column=0, padx=(0, 10), pady=(0, 12), sticky="nsew")

        word_day_header = ctk.CTkFrame(self.word_day_frame, fg_color="transparent")
        word_day_header.pack(fill="x", padx=18, pady=(16, 8))
        ctk.CTkLabel(
            word_day_header,
            text="WORD OF THE DAY",
            font=ui_font(self, 11, "bold"),
            text_color="#f8d48a",
        ).pack(side="left")

        self.word_day_level_lbl = ctk.CTkLabel(
            word_day_header,
            text="",
            font=ui_font(self, 12, "bold"),
            text_color="#8fd8ff",
        )
        self.word_day_level_lbl.pack(side="right")

        self.word_day_word_lbl = ctk.CTkLabel(
            self.word_day_frame,
            text="",
            font=ui_font(self, 34, "bold"),
            text_color=UI_PALETTE["text"],
            anchor="w",
        )
        self.word_day_word_lbl.pack(anchor="w", padx=18)

        self.word_day_meta_lbl = ctk.CTkLabel(
            self.word_day_frame,
            text="",
            font=ui_font(self, 14, slant="italic"),
            text_color="#8f9db8",
            anchor="w",
        )
        self.word_day_meta_lbl.pack(anchor="w", padx=18, pady=(2, 0))

        self.word_day_meaning_lbl = ctk.CTkLabel(
            self.word_day_frame,
            text="",
            font=self.FONT_BODY,
            text_color="#e2e8f0",
            anchor="w",
            justify="left",
            wraplength=360,
        )
        self.word_day_meaning_lbl.pack(anchor="w", padx=18, pady=(10, 0))

        self.word_day_cta = ctk.CTkButton(
            self.word_day_frame,
            text="Open In Dictionary",
            width=170,
            height=40,
            font=ui_font(self, 13, "bold"),
            command=self.open_word_of_day,
        )
        self._apply_glass_button(self.word_day_cta)
        self.word_day_cta.pack(anchor="w", padx=18, pady=(14, 18))
        self.refresh_word_of_day()

        self.daily_challenge_frame = ctk.CTkFrame(cards_grid, **glass_frame_style())
        self.daily_challenge_frame.grid(row=0, column=1, padx=(10, 0), pady=(0, 12), sticky="nsew")

        self.daily_title_lbl = ctk.CTkLabel(
            self.daily_challenge_frame,
            text="DAILY CHALLENGE",
            font=ui_font(self, 11, "bold"),
            text_color="#b6a4ff",
        )
        self.daily_title_lbl.pack(anchor="w", padx=18, pady=(16, 8))

        self.daily_desc_lbl = ctk.CTkLabel(
            self.daily_challenge_frame,
            text="",
            font=self.FONT_BODY,
            text_color="#d2dcf0",
            anchor="w",
            justify="left",
            wraplength=360,
        )
        self.daily_desc_lbl.pack(anchor="w", padx=18)

        self.daily_status_lbl = ctk.CTkLabel(
            self.daily_challenge_frame,
            text="",
            font=ui_font(self, 13, "bold"),
            text_color="#f8d48a",
            anchor="w",
        )
        self.daily_status_lbl.pack(anchor="w", padx=18, pady=(8, 0))

        self.daily_btn = ctk.CTkButton(
            self.daily_challenge_frame,
            text="Start Challenge",
            width=180,
            height=40,
            font=ui_font(self, 13, "bold"),
            command=self.start_daily_challenge,
        )
        self._apply_primary_button(self.daily_btn)
        self.daily_btn.pack(anchor="w", padx=18, pady=(16, 18))

        self.recent_frame = ctk.CTkFrame(cards_grid, **glass_frame_style())
        self.recent_frame.grid(row=1, column=0, columnspan=2, pady=(0, 8), sticky="nsew")
        self.recent_frame.configure(height=118)
        self.recent_frame.pack_propagate(False)
        self.recent_frame.grid_propagate(False)

        recent_header = ctk.CTkFrame(self.recent_frame, fg_color="transparent")
        recent_header.pack(fill="x", padx=18, pady=(14, 6))
        ctk.CTkLabel(
            recent_header,
            text="RECENT SEARCHES",
            font=ui_font(self, 11, "bold"),
            text_color="#8fd8ff",
        ).pack(side="left")

        self.recent_buttons_frame = ctk.CTkFrame(self.recent_frame, fg_color="transparent")
        self.recent_buttons_frame.pack(fill="x", padx=18, pady=(0, 12))
        self.refresh_recent_searches()
        self.refresh_daily_challenge_panel()

        self.home_ac_frame = ctk.CTkFrame(
            self.home_frame,
            fg_color=UI_PALETTE["glass"],
            corner_radius=18,
            border_width=1,
            border_color=UI_PALETTE["accent_cyan"],
        )
        self.home_search_entry.bind("<Escape>", lambda e: self.home_ac_frame.place_forget())
        self.home_search_entry.bind("<FocusOut>", lambda e: self.after(200, self.home_ac_frame.place_forget()))
        
    def open_dict_all(self):
        self.showing_favorites = False
        self.show_screen(self.dict_frame)
        self.update_list()
        
    def open_dict_fav(self):
        self.showing_favorites = True
        self.show_screen(self.dict_frame)
        self.update_list()

    def refresh_word_of_day(self):
        if not hasattr(self, "word_day_word_lbl"):
            return

        selected = pick_word_of_day(self.words)
        if not selected:
            self.word_day_word_lbl.configure(text="Notebook is empty")
            self.word_day_meta_lbl.configure(text="Add a few words to unlock Word of the Day")
            self.word_day_meaning_lbl.configure(text="Each day the app will highlight one word for quick review.")
            self.word_day_level_lbl.configure(text="")
            self.word_day_cta.configure(state="disabled")
            self.current_word_of_day = ""
            return

        word, entry = selected
        phonetic = repair_text(entry.get("phonetic", ""))
        pos = repair_text(entry.get("pos", ""))
        level = entry.get("level", "")
        meaning = repair_text(entry.get("meaning", "")) or repair_text(entry.get("eng_meaning", ""))
        meta_parts = [part for part in (pos, phonetic) if part]

        self.current_word_of_day = word
        self.word_day_word_lbl.configure(text=word)
        self.word_day_meta_lbl.configure(text=" / ".join(meta_parts) if meta_parts else "Suggested word for today")
        self.word_day_meaning_lbl.configure(text=meaning or "No meaning available for this entry yet.")
        self.word_day_level_lbl.configure(text=f"CEFR {level}" if level else "")
        self.word_day_cta.configure(state="normal")

    def open_word_of_day(self):
        if not getattr(self, "current_word_of_day", ""):
            return
        self.record_recent_search(self.current_word_of_day)
        self.showing_favorites = False
        self.show_screen(self.dict_frame)
        self.search_var.set(self.current_word_of_day)
        self.update_list()

    def refresh_recent_searches(self):
        if not hasattr(self, "recent_buttons_frame"):
            return

        for child in self.recent_buttons_frame.winfo_children():
            child.destroy()

        if not self.recent_searches:
            ctk.CTkLabel(
                self.recent_buttons_frame,
                text="No recent lookups yet.",
                font=ui_font(self, 13),
                text_color="#64748B",
            ).pack(anchor="w")
            return

        for word in self.recent_searches[:5]:
            btn = ctk.CTkButton(
                self.recent_buttons_frame,
                text=word,
                width=132,
                height=34,
                font=ui_font(self, 12, "bold"),
                command=lambda kw=word: self.open_recent_search(kw),
            )
            self._apply_glass_button(btn)
            btn.pack(side="left", padx=(0, 8))

    def open_recent_search(self, word):
        self.record_recent_search(word)
        self.showing_favorites = False
        self.show_screen(self.dict_frame)
        self.search_var.set(word)
        self.update_list()

    def refresh_daily_challenge_panel(self):
        if not hasattr(self, "daily_desc_lbl"):
            return

        streak = int(self.daily_state.get("streak", 0))
        completed_today = self.daily_state.get("last_completed") == today_key()
        self.daily_completed_today = completed_today
        self.daily_desc_lbl.configure(
            text="Complete 3 daily questions to keep your learning streak alive."
        )
        if completed_today:
            self.daily_status_lbl.configure(text=f"Completed today / {streak}-day streak")
            self.daily_btn.configure(text="Retry Challenge", fg_color="#334155", hover_color="#475569")
        else:
            self.daily_status_lbl.configure(text=f"Not completed today / Current streak {streak} days")
            self.daily_btn.configure(text="Start Challenge", fg_color="#7C3AED", hover_color="#6D28D9")

    def _mark_daily_challenge_complete(self):
        today = today_key()
        if self.daily_state.get("last_completed") == today:
            return

        last_completed = self.daily_state.get("last_completed", "")
        if last_completed:
            try:
                last_date = date.fromisoformat(last_completed)
                today_date = date.fromisoformat(today)
                if (today_date - last_date).days == 1:
                    self.daily_state["streak"] = int(self.daily_state.get("streak", 0)) + 1
                else:
                    self.daily_state["streak"] = 1
            except ValueError:
                self.daily_state["streak"] = 1
        else:
            self.daily_state["streak"] = 1

        self.daily_state["last_completed"] = today
        self.daily_completed_today = True
        self.save_state()
        self.refresh_daily_challenge_panel()

    def return_to_game_menu(self):
        if getattr(self, "cw_timer", None):
            try:
                self.after_cancel(self.cw_timer)
            except Exception:
                pass
            self.cw_timer = None
        self.show_screen(self.game_frame)
        self.show_mode_selector()

    def create_tile(self, parent, icon, title, desc, r, c, command, hover_color):
        card = ctk.CTkFrame(parent, width=210, height=170, corner_radius=20, fg_color="#1E293B", border_width=2, border_color="#334155")
        card.grid(row=r, column=c, padx=12, pady=12)
        card.grid_propagate(False)
        card.pack_propagate(False)
        
        lbl_icon = ctk.CTkLabel(card, text=icon, font=("Segoe UI", 60))
        lbl_icon.pack(pady=(25, 5))
        lbl_title = ctk.CTkLabel(card, text=title, font=("Segoe UI", 22, "bold"), text_color="#F8FAFC")
        lbl_title.pack(pady=0)
        lbl_desc = ctk.CTkLabel(card, text=desc, font=("Segoe UI", 14), text_color="#94A3B8")
        lbl_desc.pack(pady=0)
        
        def on_enter(e): card.configure(border_color=hover_color)
        def on_leave(e): card.configure(border_color="#334155")
        def on_click(e): command()
        
        for w in (card, lbl_icon, lbl_title, lbl_desc):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)
            
    def _next_quiz_question(self):
        words_list = list(self.words.items())
        answer_word, answer_data = random.choice(words_list)
        
        # Chọn 3 nghĩa sai ngẫu nhiên
        wrong_opts = []
        while len(wrong_opts) < 3:
            w, d = random.choice(words_list)
            if w != answer_word and d["meaning"] not in wrong_opts:
                wrong_opts.append(d["meaning"])
                
        opts = wrong_opts + [answer_data["meaning"]]
        random.shuffle(opts)
        
        self.current_q = {"word": answer_word, "answer": answer_data["meaning"]}
        
        self.q_word_lbl.configure(text=answer_word)
        self.q_phonetic_lbl.configure(text=answer_data.get("phonetic", ""))
        self.q_card.configure(border_color="#3B82F6")
        
        for i, btn in enumerate(self.opt_btns):
            btn.configure(text=opts[i], fg_color="#334155", state="normal")

    def _check_quiz_answer(self, idx):
        selected_text = self.opt_btns[idx].cget("text")
        correct = (selected_text == self.current_q["answer"])
        
        if correct:
            self.quiz_score += 10
            self.quiz_score_lbl.configure(text=f"🏆 Điểm: {self.quiz_score}")
            self.opt_btns[idx].configure(fg_color="#10B981") # Xanh lá
            self.q_card.configure(border_color="#10B981")
            self.after(800, self._next_quiz_question)
        else:
            self.opt_btns[idx].configure(fg_color="#EF4444") # Đỏ
            self.q_card.configure(border_color="#EF4444")
            # Highlight câu đúng
            for btn in self.opt_btns:
                if btn.cget("text") == self.current_q["answer"]:
                    btn.configure(fg_color="#10B981")
            self.after(1500, self._next_quiz_question)
            
        for btn in self.opt_btns: btn.configure(state="disabled")

    def exit_crossword(self):
        if hasattr(self, 'cw_timer') and self.cw_timer:
            try:
                self.after_cancel(self.cw_timer)
            except Exception: pass
            self.cw_timer = None
        self.return_to_game_menu()

    def start_crossword(self):
        if len(self.words) < 10:
            self.show_toast("⚠ Bạn cần có ít nhất 10 từ vựng có sẵn nghĩa để chơi Crossword!", is_error=True)
            return
            
        if not hasattr(self, 'cw_frame'):
            self.cw_frame = ctk.CTkFrame(self.container, fg_color="#0F172A", corner_radius=0)
            top_bar = ctk.CTkFrame(self.cw_frame, fg_color="transparent")
            top_bar.pack(fill="x", padx=25, pady=(25, 5))
            
            btn_back = ctk.CTkButton(top_bar, text="⬅ Thoát Game", width=120, height=45, font=("Segoe UI", 16, "bold"), 
                                     corner_radius=15, fg_color="#334155", hover_color="#475569", 
                                     command=self.exit_crossword)
            btn_back.pack(side="left")
            
            self.cw_time_lbl = ctk.CTkLabel(top_bar, text="⏱️ Đang tạo Grid...", font=("Segoe UI", 20, "bold"), text_color="#F8FAFC")
            self.cw_time_lbl.pack(side="left", padx=30)
            
            ctk.CTkButton(top_bar, text="💡 Xin Gợi ý (+30s Penalty)", fg_color="#F59E0B", hover_color="#D97706", text_color="#1E293B",
                          font=("Segoe UI", 16, "bold"), command=self.use_cw_hint).pack(side="right", padx=10)
            
            ctk.CTkButton(top_bar, text="✅ Nộp Bài Test", fg_color="#10B981", hover_color="#059669", text_color="white",
                          font=("Segoe UI", 16, "bold"), command=self.submit_crossword).pack(side="right")

            self.cw_placeholder = ctk.CTkLabel(
                self.cw_frame,
                text="Đang chuẩn bị crossword...",
                font=("Segoe UI", 20, "bold"),
                text_color="#94A3B8",
            )
            self.cw_placeholder.pack(expand=True, pady=40)
                          
        self.show_screen(self.cw_frame)
        if hasattr(self, "cw_inner"):
            self.cw_inner.destroy()
            del self.cw_inner
        if hasattr(self, "cw_placeholder"):
            self.cw_placeholder.configure(text="Đang sinh ma trận crossword, chờ chút nhé...")
            self.cw_placeholder.pack(expand=True, pady=40)
        self.cw_time_lbl.configure(text="⏳ Đang sinh Ma Trận 2D (Crossword AI)...")
        self.after(100, lambda: self.generate_crossword(12))

    def _render_crossword(self, placed_words, size):
        if hasattr(self, 'cw_inner'): self.cw_inner.destroy()
        if hasattr(self, 'cw_timer') and self.cw_timer: self.after_cancel(self.cw_timer)
        if hasattr(self, "cw_placeholder"):
            self.cw_placeholder.pack_forget()
        
        self.cw_inner = ctk.CTkFrame(self.cw_frame, fg_color="transparent")
        self.cw_inner.pack(fill="both", expand=True)
        
        grid_container = ctk.CTkFrame(self.cw_inner, fg_color="#1E293B", corner_radius=10)
        grid_container.pack(side="left", padx=20, pady=20, expand=True)
        
        clues_container = ctk.CTkScrollableFrame(self.cw_inner, fg_color="#1E293B", corner_radius=10, width=500)
        clues_container.pack(side="right", padx=20, pady=20, fill="y")
        
        min_r = min(p["r"] for p in placed_words)
        min_c = min(p["c"] for p in placed_words)
        
        self.cw_cells = {}
        self.cw_hints_used = 0
        self.cw_time = 0
        
        cell_size = 40
        for p_idx, p in enumerate(placed_words):
            for i, char in enumerate(p["word"]):
                r = p["r"] + (i if p["d"] == 'V' else 0)
                c = p["c"] + (i if p["d"] == 'H' else 0)
                if (r, c) not in self.cw_cells:
                    e = ctk.CTkEntry(grid_container, width=cell_size, height=cell_size, 
                                     font=("Segoe UI", 20, "bold"), justify="center",
                                     border_width=2, border_color="#475569", text_color="#F8FAFC", fg_color="#0F172A")
                    e.grid(row=r-min_r, column=c-min_c, padx=1, pady=1)
                    
                    def cap(var, ev=e):
                        val = ev.get().upper()
                        if len(val) > 1: ev.delete(0, 'end'); ev.insert(0, val[-1])
                        elif len(val) == 1: ev.delete(0, 'end'); ev.insert(0, val)
                    e.bind("<KeyRelease>", lambda ev: cap(None))
                    self.cw_cells[(r, c)] = {"entry": e, "char": char.upper()}

                if i == 0:
                    lbl = ctk.CTkLabel(grid_container, text=str(p_idx+1), font=("Segoe UI", 10, "bold"), text_color="#FCD34D")
                    lbl.grid(row=r-min_r, column=c-min_c, sticky="nw", padx=3, pady=1)

        lbl_acc = ctk.CTkLabel(clues_container, text="➡ NGANG (ACROSS)", font=("Segoe UI", 18, "bold"), text_color="#60A5FA")
        lbl_acc.pack(anchor="w", pady=(10, 5), padx=10)
        for i, p in enumerate(placed_words):
            if p["d"] == 'H':
                ctk.CTkLabel(clues_container, text=f"{i+1}. {p['meaning']}", font=("Segoe UI", 15), justify="left", wraplength=450).pack(anchor="w", padx=15, pady=4)
                
        lbl_dn = ctk.CTkLabel(clues_container, text="⬇ DỌC (DOWN)", font=("Segoe UI", 18, "bold"), text_color="#10B981")
        lbl_dn.pack(anchor="w", pady=(20, 5), padx=10)
        for i, p in enumerate(placed_words):
            if p["d"] == 'V':
                ctk.CTkLabel(clues_container, text=f"{i+1}. {p['meaning']}", font=("Segoe UI", 15), justify="left", wraplength=450).pack(anchor="w", padx=15, pady=4)

        self._update_cw_timer()
        
    def _update_cw_timer(self):
        self.cw_time += 1
        mins = self.cw_time // 60
        secs = self.cw_time % 60
        self.cw_time_lbl.configure(text=f"⏱️ Thời gian: {mins:02d}:{secs:02d}")
        self.cw_timer = self.after(1000, self._update_cw_timer)
        
    def use_cw_hint(self):
        wrongs = [d for d in self.cw_cells.values() if d["entry"].get().upper() != d["char"]]
        if wrongs:
            cell = random.choice(wrongs)
            cell["entry"].delete(0, 'end')
            cell["entry"].insert(0, cell["char"])
            cell["entry"].configure(fg_color="#3B82F6", text_color="white") 
            self.cw_hints_used += 1
            self.cw_time += 30
            self.show_toast(f"💡 Đã dùng gợi ý (Phạt +30s). Tổng dùng: {self.cw_hints_used}")
            # Evaluate instantly incase they hint the last word
            self.submit_crossword(hint_mode=True)
            
    def submit_crossword(self, hint_mode=False):
        correct = 0
        total = len(self.cw_cells)
        for data in self.cw_cells.values():
            if data["entry"].get().upper() == data["char"]:
                correct += 1
                if not hint_mode: data["entry"].configure(fg_color="#10B981", text_color="white")
            elif not hint_mode:
                data["entry"].configure(fg_color="#EF4444", text_color="white")
                
        if correct == total:
            self.after_cancel(self.cw_timer)
            score = 1000 - self.cw_time - (self.cw_hints_used * 50)
            if score > 800: level = "C1 (IELTS 7.5+)"
            elif score > 600: level = "B2 (IELTS 6.0)"
            elif score > 400: level = "B1 (IELTS 4.5)"
            else: level = "A2 (Cơ Bản)"
            
            self.show_toast(f"🎉 HOÀN THÀNH CHÚC MỪNG! Trình độ Tiếng Anh: {level}", duration=5000)
            self.cw_time_lbl.configure(text=f"✅ KẾT QUẢ ĐÁNH GIÁ TRÌNH ĐỘ CEFR: {level}", text_color="#10B981")

    # ================= WORD SCRAMBLE (XÁO CHỮ) =================
    def start_scramble(self):
        valid = [(w, d["meaning"]) for w, d in self.words.items() if " " not in w and len(w) >= 4 and d.get("meaning") and "(Chưa rõ nghĩa)" not in d["meaning"]]
        if len(valid) < 5:
            self.show_toast("⚠ Bạn cần ít nhất 5 từ vựng đơn (≥4 ký tự) để chơi Xáo Chữ!", is_error=True)
            return

        if not hasattr(self, 'scramble_frame'):
            self.scramble_frame = ctk.CTkFrame(self.container, fg_color="#0F172A", corner_radius=0)
            top = ctk.CTkFrame(self.scramble_frame, fg_color="transparent")
            top.pack(fill="x", padx=25, pady=(25, 5))
            ctk.CTkButton(top, text="⬅ Thoát", width=100, height=45, font=("Segoe UI", 16, "bold"),
                          corner_radius=15, fg_color="#334155", hover_color="#475569",
                          command=self.return_to_game_menu).pack(side="left")
            self.scr_score_lbl = ctk.CTkLabel(top, text="🏆 0 điểm | Streak: 0", font=("Segoe UI", 20, "bold"), text_color="#F59E0B")
            self.scr_score_lbl.pack(side="right")
            self.scr_timer_lbl = ctk.CTkLabel(top, text="⏱️ 00:00", font=("Segoe UI", 20, "bold"), text_color="#F8FAFC")
            self.scr_timer_lbl.pack(side="right", padx=20)

            card = ctk.CTkFrame(self.scramble_frame, fg_color="#1E293B", corner_radius=20, border_color="#3B82F6", border_width=2)
            card.pack(pady=30, padx=60, fill="x")
            self.scr_hint_lbl = ctk.CTkLabel(card, text="", font=("Segoe UI", 18), text_color="#94A3B8")
            self.scr_hint_lbl.pack(pady=(30, 10))
            self.scr_letters_lbl = ctk.CTkLabel(card, text="", font=("Segoe UI", 50, "bold"), text_color="#60A5FA")
            self.scr_letters_lbl.pack(pady=10)
            self.scr_len_lbl = ctk.CTkLabel(card, text="", font=("Segoe UI", 16), text_color="#64748B")
            self.scr_len_lbl.pack(pady=(0, 10))

            input_row = ctk.CTkFrame(card, fg_color="transparent")
            input_row.pack(pady=(10, 30))
            self.scr_entry = ctk.CTkEntry(input_row, width=400, height=55, font=("Segoe UI", 22, "bold"),
                                          placeholder_text="Gõ đáp án...", corner_radius=15, border_color="#475569", fg_color="#0F172A")
            self.scr_entry.pack(side="left", padx=(0, 10))
            self.scr_entry.bind("<Return>", lambda e: self._check_scramble())
            ctk.CTkButton(input_row, text="Gửi", width=100, height=55, font=("Segoe UI", 18, "bold"),
                          fg_color="#10B981", hover_color="#059669", corner_radius=15,
                          command=self._check_scramble).pack(side="left")
            ctk.CTkButton(input_row, text="Bỏ qua", width=100, height=55, font=("Segoe UI", 18, "bold"),
                          fg_color="#EF4444", hover_color="#DC2626", corner_radius=15,
                          command=self._skip_scramble).pack(side="left", padx=(10, 0))

            self.scr_feedback_lbl = ctk.CTkLabel(self.scramble_frame, text="", font=("Segoe UI", 20, "bold"))
            self.scr_feedback_lbl.pack(pady=10)

        self.scr_score = 0
        self.scr_streak = 0
        self.scr_time = 0
        self.show_screen(self.scramble_frame)
        self._next_scramble()
        self._update_scr_timer()

    def _next_scramble(self):
        valid = [(w, d["meaning"]) for w, d in self.words.items() if " " not in w and len(w) >= 4 and d.get("meaning") and "(Chưa rõ nghĩa)" not in d["meaning"]]
        self.scr_current_word, self.scr_current_meaning = random.choice(valid)
        letters = list(self.scr_current_word.upper())
        while "".join(letters) == self.scr_current_word.upper():
            random.shuffle(letters)
        self.scr_letters_lbl.configure(text="  ".join(letters))
        self.scr_hint_lbl.configure(text=f"💡 Gợi ý: {self.scr_current_meaning}")
        self.scr_len_lbl.configure(text=f"({len(self.scr_current_word)} chữ cái)")
        self.scr_entry.delete(0, "end")
        self.scr_entry.focus()
        self.scr_feedback_lbl.configure(text="")

    def _check_scramble(self):
        ans = self.scr_entry.get().strip().lower()
        if ans == self.scr_current_word.lower():
            self.scr_streak += 1
            bonus = 10 * self.scr_streak
            self.scr_score += bonus
            self.scr_score_lbl.configure(text=f"🏆 {self.scr_score} điểm | Streak: {self.scr_streak}🔥")
            self.scr_feedback_lbl.configure(text=f"✅ CHÍNH XÁC! +{bonus} điểm (Combo x{self.scr_streak})", text_color="#10B981")
            self.after(1000, self._next_scramble)
        else:
            self.scr_streak = 0
            self.scr_score_lbl.configure(text=f"🏆 {self.scr_score} điểm | Streak: 0")
            self.scr_feedback_lbl.configure(text=f"❌ Sai rồi! Thử lại nhé.", text_color="#EF4444")

    def _skip_scramble(self):
        self.scr_streak = 0
        self.scr_score_lbl.configure(text=f"🏆 {self.scr_score} điểm | Streak: 0")
        self.scr_feedback_lbl.configure(text=f"⏭️ Đáp án: {self.scr_current_word}", text_color="#F59E0B")
        self.after(1500, self._next_scramble)

    def _update_scr_timer(self):
        self.scr_time += 1
        m, s = self.scr_time // 60, self.scr_time % 60
        self.scr_timer_lbl.configure(text=f"⏱️ {m:02d}:{s:02d}")
        self.scr_timer_id = self.after(1000, self._update_scr_timer)

    # ================= HANGMAN (TREO CỔ) =================
    def start_hangman(self):
        valid = [(w, d["meaning"]) for w, d in self.words.items() if " " not in w and len(w) >= 3 and d.get("meaning") and "(Chưa rõ nghĩa)" not in d["meaning"]]
        if len(valid) < 5:
            self.show_toast("⚠ Bạn cần ít nhất 5 từ vựng đơn để chơi Hangman!", is_error=True)
            return

        if not hasattr(self, 'hm_frame'):
            self.hm_frame = ctk.CTkFrame(self.container, fg_color="#0F172A", corner_radius=0)
            top = ctk.CTkFrame(self.hm_frame, fg_color="transparent")
            top.pack(fill="x", padx=25, pady=(25, 5))
            ctk.CTkButton(top, text="⬅ Thoát", width=100, height=45, font=("Segoe UI", 16, "bold"),
                          corner_radius=15, fg_color="#334155", hover_color="#475569",
                          command=self.return_to_game_menu).pack(side="left")
            self.hm_score_lbl = ctk.CTkLabel(top, text="🏆 0 điểm", font=("Segoe UI", 20, "bold"), text_color="#F59E0B")
            self.hm_score_lbl.pack(side="right")

            card = ctk.CTkFrame(self.hm_frame, fg_color="#1E293B", corner_radius=20, border_color="#EF4444", border_width=2)
            card.pack(pady=20, padx=60, fill="x")
            self.hm_hint_lbl = ctk.CTkLabel(card, text="", font=("Segoe UI", 18), text_color="#94A3B8")
            self.hm_hint_lbl.pack(pady=(25, 5))
            self.hm_hangman_lbl = ctk.CTkLabel(card, text="", font=mono_font(self, 28), text_color="#EF4444")
            self.hm_hangman_lbl.pack(pady=5)
            self.hm_word_lbl = ctk.CTkLabel(card, text="", font=("Segoe UI", 48, "bold"), text_color="#F8FAFC")
            self.hm_word_lbl.pack(pady=10)
            self.hm_wrong_lbl = ctk.CTkLabel(card, text="", font=("Segoe UI", 16), text_color="#EF4444")
            self.hm_wrong_lbl.pack(pady=(0, 5))
            self.hm_lives_lbl = ctk.CTkLabel(card, text="", font=("Segoe UI", 18, "bold"), text_color="#F59E0B")
            self.hm_lives_lbl.pack(pady=(0, 20))

            # Bàn phím A-Z
            self.hm_kb_frame = ctk.CTkFrame(self.hm_frame, fg_color="transparent")
            self.hm_kb_frame.pack(pady=10)

            self.hm_feedback_lbl = ctk.CTkLabel(self.hm_frame, text="", font=("Segoe UI", 22, "bold"))
            self.hm_feedback_lbl.pack(pady=10)

        self.hm_score = 0
        self.show_screen(self.hm_frame)
        self._next_hangman()

    def _update_hangman_display(self):
        display = "  ".join(c.upper() if c in self.hm_guessed else "_" for c in self.hm_word)
        self.hm_word_lbl.configure(text=display)
        wrong_letters = [c.upper() for c in self.hm_guessed if c not in self.hm_word]
        self.hm_wrong_lbl.configure(text=f"Sai: {', '.join(wrong_letters)}" if wrong_letters else "")
        hearts = "❤" * (self.hm_max_wrong - self.hm_wrong_count)
        lost_hearts = "🖤" * self.hm_wrong_count
        self.hm_lives_lbl.configure(text=f"❤ Mạng sống: {hearts}{lost_hearts}")
        stage = min(self.hm_wrong_count, len(self.HANGMAN_STAGES) - 1)
        self.hm_hangman_lbl.configure(text=self.HANGMAN_STAGES[stage])

    def _build_hangman_keyboard(self):
        for child in self.hm_kb_frame.winfo_children(): child.destroy()
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for i, ch in enumerate(letters):
            state = "disabled" if ch.lower() in self.hm_guessed else "normal"
            fg = "#334155" if state == "normal" else "#1E293B"
            btn = ctk.CTkButton(self.hm_kb_frame, text=ch, width=52, height=52, font=("Segoe UI", 18, "bold"),
                                corner_radius=10, fg_color=fg, hover_color="#475569", state=state,
                                command=lambda c=ch: self._guess_hangman(c))
            btn.grid(row=i // 9, column=i % 9, padx=3, pady=3)

    def _guess_hangman(self, letter):
        ch = letter.lower()
        self.hm_guessed.add(ch)
        if ch not in self.hm_word:
            self.hm_wrong_count += 1

        self._update_hangman_display()
        self._build_hangman_keyboard()

        # Kiểm tra thắng
        if all(c in self.hm_guessed for c in self.hm_word):
            self.hm_score += 10 * (self.hm_max_wrong - self.hm_wrong_count)
            self.hm_score_lbl.configure(text=f"🏆 {self.hm_score} điểm")
            self.hm_feedback_lbl.configure(text=f"🎉 Đúng! Từ là: {self.hm_word.upper()}", text_color="#10B981")
            self.after(2000, self._next_hangman)
        elif self.hm_wrong_count >= self.hm_max_wrong:
            self.hm_feedback_lbl.configure(text=f"💀 THUA! Đáp án là: {self.hm_word.upper()}", text_color="#EF4444")
            self.after(2500, self._next_hangman)
            
    def apply_home_suggestion(self, word):
        self.home_search_var.set(word)
        self.home_ac_frame.place_forget()
        self.on_home_search_enter(None)

    def setup_dict_screen(self):
        self.dict_bg_canvas = install_cosmic_background(self.dict_frame)
        top_bar = ctk.CTkFrame(
            self.dict_frame,
            fg_color="#111830",
            border_width=1,
            border_color="#24335B",
            corner_radius=18,
            height=64,
        )
        top_bar.pack(fill="x", padx=25, pady=(25, 15))
        top_bar.pack_propagate(False)

        back_slot = ctk.CTkFrame(top_bar, fg_color="transparent", width=210, height=64)
        back_slot.pack(side="left", padx=(8, 0), pady=0)
        back_slot.pack_propagate(False)

        self.dict_back_btn = self._build_home_screen_pill(
            back_slot,
            lambda: self.show_screen(self.home_frame),
            width=178,
            height=42,
        )
        self.dict_back_btn.pack(anchor="w", padx=0, pady=10)

        ctk.CTkLabel(
            top_bar,
            text="Dictionary Search",
            font=ui_font(self, 15, "bold"),
            text_color="#94A3B8",
            fg_color="transparent",
        ).pack(side="right", padx=16)
        
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.debounce_search())

        search_overlay = ctk.CTkFrame(self.dict_frame, fg_color="transparent", height=55)
        search_overlay.pack(fill="x", padx=25, pady=(0, 10))
        search_overlay.pack_propagate(False)

        self.dict_ghost_var = ctk.StringVar(value="")
        self.dict_ghost_label = ctk.CTkLabel(
            search_overlay,
            textvariable=self.dict_ghost_var,
            font=ui_font(self, 18),
            text_color="#64748B",
            anchor="w",
        )
        self.dict_ghost_label.place(x=20, rely=0.5, anchor="w")

        self.search_entry = ctk.CTkEntry(search_overlay, textvariable=self.search_var,
                                         placeholder_text="Type an English word to filter, then press Enter to fetch from the web...",
                                         height=55, font=ui_font(self, 18), corner_radius=15,
                                         border_width=2, border_color="#3B82F6", fg_color="#1E293B")
        self.search_entry.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.search_entry.bind("<Return>", lambda e: self.trigger_cloud_lookup())
        self.search_entry.bind("<Tab>", self.accept_dict_suggestion)
        
        self.dict_ac_frame = ctk.CTkFrame(self.dict_frame, fg_color="#1E293B", corner_radius=15, border_width=2, border_color="#3B82F6")
        self.search_entry.bind("<Escape>", lambda e: self.dict_ac_frame.place_forget())
        self.search_entry.bind("<FocusOut>", lambda e: self.after(200, self.dict_ac_frame.place_forget))

        controls_row = ctk.CTkFrame(self.dict_frame, fg_color="transparent")
        controls_row.pack(fill="x", padx=25, pady=(0, 10))

        ctk.CTkLabel(
            controls_row,
            text="CEFR:",
            font=("Segoe UI", 14, "bold"),
            text_color="#94A3B8",
        ).pack(side="left")

        self.level_filter_var = tk.StringVar(value="All")
        self.level_filter_menu = ctk.CTkOptionMenu(
            controls_row,
            values=["All", *VALID_CEFR_LEVELS],
            variable=self.level_filter_var,
            width=120,
            height=36,
            corner_radius=10,
            fg_color="#1E293B",
            button_color="#2563EB",
            button_hover_color="#1D4ED8",
            dropdown_fg_color="#1E293B",
            command=lambda _value: self.update_list(),
        )
        self.level_filter_menu.pack(side="left", padx=(8, 14))

        ctk.CTkLabel(
            controls_row,
            text="(estimated when real CEFR data is unavailable)",
            font=("Segoe UI", 12),
            text_color="#64748B",
        ).pack(side="left")

        export_tsv_btn = ctk.CTkButton(
            controls_row,
            text="Export TSV",
            width=100,
            height=36,
            corner_radius=10,
            fg_color="#334155",
            hover_color="#475569",
            command=lambda: self.export_filtered_words("\t", "tsv", "table"),
        )
        export_tsv_btn.pack(side="right")

        export_csv_btn = ctk.CTkButton(
            controls_row,
            text="Export TXT",
            width=100,
            height=36,
            corner_radius=10,
            fg_color="#0F766E",
            hover_color="#115E59",
            command=lambda: self.export_filtered_words("\t", "txt", "txt"),
        )
        export_csv_btn.pack(side="right", padx=(0, 8))

        
        # === THANH HÀNH ĐỘNG HÀNG LOẠT (BULK ACTION BAR) ===
        self.bulk_bar = ctk.CTkFrame(self.dict_frame, fg_color="#1E293B", corner_radius=12, border_width=1, border_color="#334155")
        # Ẩn mặc định, chỉ hiện khi có từ được chọn
        
        self.bulk_select_label = ctk.CTkLabel(self.bulk_bar, text="Đã chọn: 0", font=("Segoe UI", 15, "bold"), text_color="#60A5FA")
        self.bulk_select_label.pack(side="left", padx=15)
        
        btn_delete_bulk = ctk.CTkButton(self.bulk_bar, text="🗑 Xóa hàng loạt", width=150, height=38, font=("Segoe UI", 14, "bold"),
                                        corner_radius=10, fg_color="#EF4444", hover_color="#DC2626", command=self.delete_selected)
        btn_delete_bulk.pack(side="left", padx=5)
        
        btn_fav_bulk = ctk.CTkButton(self.bulk_bar, text="⭐ Yêu thích", width=120, height=38, font=("Segoe UI", 14, "bold"),
                                     corner_radius=10, fg_color="#F59E0B", hover_color="#D97706", command=self.favorite_selected)
        btn_fav_bulk.pack(side="left", padx=5)
        
        btn_cloud_bulk = ctk.CTkButton(self.bulk_bar, text="☁️ Cập nhật API", width=140, height=38, font=("Segoe UI", 14, "bold"),
                                       corner_radius=10, fg_color="#8B5CF6", hover_color="#7C3AED", command=self.cloud_update_selected)
        btn_cloud_bulk.pack(side="left", padx=5)
        
        btn_select_all = ctk.CTkButton(self.bulk_bar, text="☑ Chọn hết", width=110, height=38, font=("Segoe UI", 14, "bold"),
                                       corner_radius=10, fg_color="#334155", hover_color="#475569", command=self.select_all_visible)
        btn_select_all.pack(side="right", padx=5)
        
        btn_deselect = ctk.CTkButton(self.bulk_bar, text="✖ Bỏ chọn", width=100, height=38, font=("Segoe UI", 14, "bold"),
                                     corner_radius=10, fg_color="#334155", hover_color="#475569", command=self.deselect_all)
        btn_deselect.pack(side="right", padx=5)
        
        self.list_header = ctk.CTkLabel(self.dict_frame, text="Dictionary", font=("Segoe UI", 16, "bold"), text_color="#94A3B8")
        self.list_header.pack(anchor="w", padx=25, pady=(5, 5))
        
        # Nút lấy mây (Ẩn mặc định)
        self.cloud_btn = ctk.CTkButton(self.dict_frame, text="Fetch Full Entry From Web", height=45, font=("Segoe UI", 16, "bold"),
                                       corner_radius=12, fg_color="#8B5CF6", hover_color="#7C3AED", command=self.trigger_cloud_lookup)
        
        self.list_frame = ctk.CTkScrollableFrame(self.dict_frame, corner_radius=15, fg_color="#0F172A", border_width=0)
        self.list_frame.pack(fill="both", expand=True, padx=25, pady=(0, 25))

    def debounce_search(self):
        if self.search_timer: self.after_cancel(self.search_timer)
        self.search_timer = self.after(100, self._debounce_search_invoke)
        
    def generate_vibe_profile(self, word):
        """Tạo ra chỉ số cảm xúc và màu sắc bằng thuật toán Hash cố định"""
        random.seed(word.lower())
        colors = ["#EF4444", "#F59E0B", "#10B981", "#3B82F6", "#8B5CF6", "#EC4899", "#14B8A6"]
        theme_color = random.choice(colors)
        random.seed()
        return {"color": theme_color}

    def setup_add_screen(self):
        self.add_bg_canvas = install_cosmic_background(self.add_frame)
        top_bar = ctk.CTkFrame(self.add_frame, fg_color="transparent")
        top_bar.pack(fill="x", padx=25, pady=(25, 20))

        btn_back = self._build_home_screen_pill(
            top_bar,
            lambda: self.show_screen(self.home_frame),
            width=178,
            height=45,
        )
        btn_back.pack(side="left")
        
        title = ctk.CTkLabel(top_bar, text="Import Data", font=("Segoe UI", 26, "bold"), text_color="#F59E0B")
        title.pack(side="right")
        
        self.input_text = ctk.CTkTextbox(self.add_frame, height=350, font=ui_font(self, 18), corner_radius=15,
                                         fg_color="#1E293B", text_color="#ffffff", border_width=2, border_color="#334155", wrap="word")
        self.input_text.pack(fill="x", padx=25, pady=10)
        
        self.placeholder_text = (
            "💡 HƯỚNG DẪN DÁN TỪ HÀNG LOẠT:\n\n"
            "Tính năng này để thêm nhanh hàng trăm từ từ nguồn có sẵn.\n"
            "1. Cấu trúc chuẩn: 'apple - quả táo', 'banana : quả chuối'\n"
            "2. Hoặc Copy toàn tiếng Anh, AI của Google Dịch sẽ hỗ trợ dịch tự động từng nhánh!\n\n"
            "Lưu ý: Để tra 1 từ đầy đủ Phiên âm và Ví dụ, hãy dùng Thanh Tìm Kiếm Đám Mây ở Trang Chủ.\n\n"
            "(Click vào màn hình đen này để xóa mờ và gõ)"
        )
        self.input_text.insert("0.0", self.placeholder_text)
        self.input_text.configure(text_color="#64748B")
        
        self.input_text.bind("<FocusIn>", self.clear_placeholder)
        self.input_text.bind("<FocusOut>", self.restore_placeholder)
        self.placeholder_cleared = False
        
        self.save_btn = ctk.CTkButton(self.add_frame, text="SAVE (Ctrl+Enter)", command=self.start_add_words_thread, 
                                      height=65, font=("Segoe UI", 20, "bold"), corner_radius=15, fg_color="#F59E0B", hover_color="#D97706")
        self.save_btn.pack(fill="x", padx=25, pady=(25, 0))
        self._apply_primary_button(self.save_btn)
        self.bind("<Control-Return>", lambda event: self.start_add_words_thread())

    # ================= 4. HỆ THỐNG MINIGAME ĐA CHẾ ĐỘ =================
    def setup_game_screen(self):
        self.game_bg_canvas = install_cosmic_background(self.game_frame)
        # Top bar (luôn hiện)
        top_bar = ctk.CTkFrame(self.game_frame, fg_color="transparent")
        top_bar.pack(fill="x", padx=25, pady=(20, 10))
        
        btn_back = self._build_home_screen_pill(
            top_bar,
            self.exit_game,
            width=178,
            height=40,
        )
        btn_back.pack(side="left")
        
        self.lbl_score = ctk.CTkLabel(top_bar, text="Score: 0", font=("Segoe UI", 26, "bold"), text_color="#10B981")
        self.lbl_score.pack(side="right")
        
        self.lbl_timer = ctk.CTkLabel(top_bar, text="", font=("Segoe UI", 22, "bold"), text_color="#F59E0B")
        self.lbl_timer.pack(side="right", padx=20)
        
        # === Container chứa nội dung game (swap giữa các mode) ===
        self.game_content = ctk.CTkFrame(self.game_frame, fg_color="transparent")
        self.game_content.pack(fill="both", expand=True)
        self.game_content.bind("<Configure>", self._on_game_content_resize, add="+")
        
        # Biến trạng thái game
        self.game_mode = None
        self.game_timer_id = None
        self.speed_time_left = 0

    def _on_game_content_resize(self, _event=None):
        if self.game_mode in ("quiz", "daily_challenge"):
            self._apply_quiz_responsive_layout()
        elif self.game_mode == "flashcards":
            self._apply_flashcard_responsive_layout()

    def _game_content_available_width(self):
        return max(self.game_content.winfo_width(), self.winfo_width() - 80, 520)

    def _apply_quiz_responsive_layout(self):
        if not hasattr(self, "card_main") or not hasattr(self, "ans_buttons"):
            return

        available_width = self._game_content_available_width()
        card_width = min(max(available_width - 180, 320), 820)
        compact = available_width < 980
        columns = 1 if available_width < 900 else 2
        button_width = min(max(card_width - 40, 260), 620) if columns == 1 else max(int((card_width - 24) / 2), 220)

        self.card_main.configure(width=card_width, height=150 if compact else 180)
        self.lbl_question.configure(
            font=("Segoe UI", 34 if compact else 45, "bold"),
            wraplength=max(card_width - 50, 260),
        )
        self.ans_frame.pack_configure(
            fill="x",
            padx=max(int((available_width - card_width) / 2), 20),
            pady=5,
        )

        for col in range(2):
            self.ans_frame.grid_columnconfigure(col, weight=0)
        for col in range(columns):
            self.ans_frame.grid_columnconfigure(col, weight=1)

        for index, btn in enumerate(self.ans_buttons):
            btn.grid_forget()
            row = index if columns == 1 else index // 2
            column = 0 if columns == 1 else index % 2
            btn.configure(
                width=button_width,
                height=68 if compact else 74,
                font=("Segoe UI", 15 if compact else 17, "bold"),
                anchor="center",
            )
            btn.grid(row=row, column=column, padx=8, pady=8, sticky="ew")

    def _apply_flashcard_responsive_layout(self):
        if not hasattr(self, "flashcard_card") or not hasattr(self, "flashcard_controls"):
            return

        available_width = self._game_content_available_width()
        compact = available_width < 980
        stacked = available_width < 860
        card_width = min(max(available_width - 180, 320), 880)

        self.flashcard_card.configure(width=card_width, height=220 if compact else 260)
        self.flashcard_word_lbl.configure(
            font=("Segoe UI", 28 if compact else 36, "bold"),
            wraplength=max(card_width - 70, 240),
        )
        self.flashcard_meta_lbl.configure(font=("Segoe UI", 13 if compact else 15, "italic"))
        self.flashcard_answer_lbl.configure(
            font=("Segoe UI", 16 if compact else 18),
            wraplength=max(card_width - 70, 240),
        )
        self.flashcard_controls.pack_configure(
            padx=max(int((available_width - card_width) / 2), 20),
            fill="x" if stacked else "none",
        )

        buttons = [self.flashcard_reveal_btn, self.flashcard_known_btn, self.flashcard_review_btn]
        for btn in buttons:
            btn.pack_forget()
            btn.configure(
                width=max(card_width - 30, 260) if stacked else 180,
                height=44 if compact else 46,
                font=("Segoe UI", 15 if compact else 16, "bold"),
            )

        if stacked:
            for btn in buttons:
                btn.pack(fill="x", pady=6)
        else:
            for btn in buttons:
                btn.pack(side="left", padx=8)

    def exit_game(self):
        if self.game_timer_id:
            self.after_cancel(self.game_timer_id)
            self.game_timer_id = None
        self.game_mode = None
        self.show_screen(self.home_frame)

    def start_game(self):
        if len(self.words) < 4:
            self.show_toast("⚠ Kho cần ít nhất 4 từ vựng!", is_error=True)
            return
        self.show_screen(self.game_frame)
        self.show_mode_selector()

    def show_mode_selector(self):
        """Hiện màn hình chọn chế độ chơi"""
        if self.game_timer_id:
            self.after_cancel(self.game_timer_id)
            self.game_timer_id = None
            
        self.game_mode = None
        self.score = 0
        self.lbl_score.configure(text="Score: 0")
        self.lbl_timer.configure(text="")
        
        for w in self.game_content.winfo_children(): w.destroy()

        self.update_idletasks()
        container_width = max(self.winfo_width(), self.game_content.winfo_width(), 720)
        title_font_size = 36 if container_width >= 1100 else 32 if container_width >= 900 else 28
        card_width = min(max(container_width - 180, 320), 540)
        
        title = ctk.CTkLabel(
            self.game_content,
            text="Choose Game Mode",
            font=("Segoe UI", title_font_size, "bold"),
            text_color="#A78BFA",
            wraplength=card_width + 120,
            justify="center",
        )
        title.pack(pady=(30, 30))
        
        modes_frame = ctk.CTkFrame(self.game_content, fg_color="transparent")
        modes_frame.pack(expand=True, fill="x", padx=max((container_width - card_width) // 2, 28))
        
        modes = [
            ("\U0001F3AF", "Trắc Nghiệm", "30 giây, chọn đúng càng nhiều càng tốt", "#8B5CF6", self.play_quiz),
            ("\U0001F0CF", "Flashcards", "Lật thẻ và tự đánh giá mức nhớ", "#14B8A6", self.play_flashcards),
            ("\U0001F9E9", "Xáo Chữ", "Sắp xếp lại chữ cái bị xáo", "#06B6D4", self.play_scramble),
            ("\U0001F9E0", "Nối Từ", "Ghép nghĩa với từ tương ứng", "#EC4899", self.play_matching),
            ("\U0001F9F1", "Crossword", "Giải ô chữ từ các gợi ý nghĩa", "#F43F5E", self.start_crossword),
            ("\U0001F504", "Dịch Ngược", "Nhìn Việt để gõ tiếng Anh", "#EF4444", self.play_reverse),
            ("\U0001F480", "Sinh Tồn", "Đoán từ từng chữ cái", "#DC2626", self.start_hangman),
            ("\U0001F3C1", "Daily Challenge", "3 câu hỏi cố định mỗi ngày", "#F97316", self.start_daily_challenge),
        ]
        
        for i, (icon, name, desc, color, cmd) in enumerate(modes):
            card = ctk.CTkFrame(
                modes_frame,
                width=card_width,
                height=90,
                corner_radius=20,
                fg_color="#1E293B",
                border_width=2,
                border_color="#334155",
                cursor="hand2",
            )
            card.pack(pady=8, fill="x")
            card.pack_propagate(False)
            
            icon_lbl = ctk.CTkLabel(card, text=icon, font=("Segoe UI Emoji", 30), width=60)
            icon_lbl.pack(side="left", padx=(20, 10))
            
            txt_frame = ctk.CTkFrame(card, fg_color="transparent")
            txt_frame.pack(side="left", fill="both", expand=True, pady=10)
            
            name_lbl = ctk.CTkLabel(txt_frame, text=name, font=("Segoe UI", 20, "bold"), text_color="#F8FAFC", anchor="w")
            name_lbl.pack(anchor="w")
            desc_lbl = ctk.CTkLabel(txt_frame, text=desc, font=("Segoe UI", 14), text_color="#94A3B8", anchor="w")
            desc_lbl.pack(anchor="w")
            
            for w in (card, icon_lbl, name_lbl, desc_lbl, txt_frame):
                w.bind("<Button-1>", lambda e, c=cmd: c())
                w.bind("<Enter>", lambda e, cl=color, cd=card: cd.configure(border_color=cl))
                w.bind("<Leave>", lambda e, cd=card: cd.configure(border_color="#334155"))

    # --- GAME UI HELPERS ---
    def build_quiz_ui(self):
        for w in self.game_content.winfo_children(): w.destroy()
        
        self.card_main = ctk.CTkFrame(self.game_content, width=650, height=180, corner_radius=25, fg_color="#1E293B", border_width=3, border_color="#8B5CF6")
        self.card_main.pack(pady=(25, 25))
        self.card_main.pack_propagate(False)
        self.lbl_question = ctk.CTkLabel(self.card_main, text="...", font=("Segoe UI", 45, "bold"), text_color="#A78BFA")
        self.lbl_question.pack(expand=True)
        
        self.ans_frame = ctk.CTkFrame(self.game_content, fg_color="transparent")
        self.ans_frame.pack(pady=5)
        self.ans_buttons = []
        for r in range(2):
            for c in range(2):
                btn = ctk.CTkButton(self.ans_frame, text="...", width=310, height=70, font=("Segoe UI", 17, "bold"),
                                    corner_radius=18, fg_color="#334155", hover_color="#475569")
                btn.grid(row=r, column=c, padx=10, pady=10)
                self.ans_buttons.append(btn)
        self._apply_quiz_responsive_layout()

    def build_typing_ui(self, hint_text=""):
        for w in self.game_content.winfo_children(): w.destroy()
        
        self.card_main = ctk.CTkFrame(self.game_content, width=650, height=180, corner_radius=25, fg_color="#1E293B", border_width=3, border_color="#06B6D4")
        self.card_main.pack(pady=(25, 20))
        self.card_main.pack_propagate(False)
        self.lbl_question = ctk.CTkLabel(self.card_main, text="...", font=("Segoe UI", 42, "bold"), text_color="#22D3EE")
        self.lbl_question.pack(expand=True)
        
        if hint_text:
            self.lbl_hint = ctk.CTkLabel(self.game_content, text=hint_text, font=("Segoe UI", 16), text_color="#64748B")
            self.lbl_hint.pack(pady=(0, 10))
        
        self.type_entry = ctk.CTkEntry(self.game_content, placeholder_text="Gõ đáp án rồi ấn Enter...",
                                       height=60, width=450, font=("Segoe UI", 22), corner_radius=15,
                                       border_width=2, border_color="#06B6D4", fg_color="#1E293B", justify="center")
        self.type_entry.pack(pady=10)
        self.type_entry.focus()
        
        self.lbl_feedback = ctk.CTkLabel(self.game_content, text="", font=("Segoe UI", 20, "bold"), text_color="#94A3B8")
        self.lbl_feedback.pack(pady=10)

    def build_flashcard_ui(self):
        for w in self.game_content.winfo_children():
            w.destroy()

        self.flashcard_card = ctk.CTkFrame(
            self.game_content,
            width=680,
            height=260,
            corner_radius=25,
            fg_color="#1E293B",
            border_width=3,
            border_color="#14B8A6",
        )
        self.flashcard_card.pack(pady=(25, 20))
        self.flashcard_card.pack_propagate(False)

        self.flashcard_word_lbl = ctk.CTkLabel(
            self.flashcard_card,
            text="",
            font=("Segoe UI", 36, "bold"),
            text_color="#F8FAFC",
            wraplength=600,
        )
        self.flashcard_word_lbl.pack(pady=(35, 10))

        self.flashcard_meta_lbl = ctk.CTkLabel(
            self.flashcard_card,
            text="",
            font=("Segoe UI", 15, "italic"),
            text_color="#94A3B8",
        )
        self.flashcard_meta_lbl.pack()

        self.flashcard_answer_lbl = ctk.CTkLabel(
            self.flashcard_card,
            text="",
            font=("Segoe UI", 18),
            text_color="#CBD5E1",
            wraplength=610,
            justify="center",
        )
        self.flashcard_answer_lbl.pack(pady=(18, 0))

        controls = ctk.CTkFrame(self.game_content, fg_color="transparent")
        controls.pack(pady=10)
        self.flashcard_controls = controls

        self.flashcard_reveal_btn = ctk.CTkButton(
            controls,
            text="Lật thẻ",
            width=160,
            height=46,
            corner_radius=14,
            fg_color="#14B8A6",
            hover_color="#0F766E",
            command=self.reveal_flashcard,
        )
        self.flashcard_reveal_btn.pack(side="left", padx=8)

        self.flashcard_known_btn = ctk.CTkButton(
            controls,
            text="Biết rồi",
            width=160,
            height=46,
            corner_radius=14,
            fg_color="#10B981",
            hover_color="#059669",
            command=lambda: self.grade_flashcard(True),
            state="disabled",
        )
        self.flashcard_known_btn.pack(side="left", padx=8)

        self.flashcard_review_btn = ctk.CTkButton(
            controls,
            text="Ôn lại",
            width=160,
            height=46,
            corner_radius=14,
            fg_color="#F59E0B",
            hover_color="#D97706",
            command=lambda: self.grade_flashcard(False),
            state="disabled",
        )
        self.flashcard_review_btn.pack(side="left", padx=8)
        self._apply_flashcard_responsive_layout()

    def build_matching_ui(self):
        for w in self.game_content.winfo_children():
            w.destroy()

        self.matching_status_lbl = ctk.CTkLabel(
            self.game_content,
            text="Chọn một nghĩa ở cột trái rồi chọn từ đúng ở cột phải.",
            font=("Segoe UI", 18, "bold"),
            text_color="#F8FAFC",
        )
        self.matching_status_lbl.pack(pady=(18, 12))

        board = ctk.CTkFrame(self.game_content, fg_color="transparent")
        board.pack(fill="both", expand=True, padx=25, pady=(0, 20))
        board.grid_columnconfigure(0, weight=1)
        board.grid_columnconfigure(1, weight=1)

        self.matching_left_frame = ctk.CTkFrame(board, fg_color="#111827", corner_radius=20)
        self.matching_left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.matching_right_frame = ctk.CTkFrame(board, fg_color="#111827", corner_radius=20)
        self.matching_right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

    def play_flashcards(self):
        self.game_mode = "flashcards"
        self.score = 0
        self.lbl_score.configure(text="Score: 0")
        self.lbl_timer.configure(text="Flashcards")
        self.build_flashcard_ui()
        self.next_flashcard()

    def next_flashcard(self):
        round_data = build_flashcard_round(self.words)
        if not round_data:
            self.show_toast("Kho chưa đủ dữ liệu để tạo flashcard.", is_error=True)
            self.show_mode_selector()
            return

        self.current_flashcard = round_data
        self.flashcard_word_lbl.configure(text=round_data["word"])
        meta_parts = [part for part in (round_data.get("phonetic", ""), f"CEFR {round_data['level']}" if round_data.get("level") else "") if part]
        self.flashcard_meta_lbl.configure(text=" • ".join(meta_parts))
        self.flashcard_answer_lbl.configure(text="Tự đoán nghĩa trước khi lật thẻ.")
        self.flashcard_card.configure(border_color="#14B8A6")
        self.flashcard_reveal_btn.configure(state="normal")
        self.flashcard_known_btn.configure(state="disabled")
        self.flashcard_review_btn.configure(state="disabled")

    def reveal_flashcard(self):
        if not getattr(self, "current_flashcard", None):
            return
        example = self.current_flashcard.get("example", "")
        meaning = self.current_flashcard.get("meaning", "")
        answer_text = meaning
        if example:
            answer_text += f"\n\nVí dụ: {example}"
        self.flashcard_answer_lbl.configure(text=answer_text)
        self.flashcard_reveal_btn.configure(state="disabled")
        self.flashcard_known_btn.configure(state="normal")
        self.flashcard_review_btn.configure(state="normal")

    def grade_flashcard(self, known: bool):
        if known:
            self.score += 10
            self.flashcard_card.configure(border_color="#10B981")
            self.flashcard_answer_lbl.configure(text=self.flashcard_answer_lbl.cget("text") + "\n\n✅ Đã đánh dấu: Biết rồi")
        else:
            self.score = max(0, self.score - 2)
            self.flashcard_card.configure(border_color="#F59E0B")
            self.flashcard_answer_lbl.configure(text=self.flashcard_answer_lbl.cget("text") + "\n\n📝 Đã đưa vào diện ôn lại")
        self.lbl_score.configure(text=f"Score: {self.score}")
        self.after(900, self.next_flashcard)

    def play_matching(self):
        self.game_mode = "matching"
        self.score = 0
        self.lbl_score.configure(text="Score: 0")
        self.lbl_timer.configure(text="Nối Từ")
        self.build_matching_ui()
        self.next_matching_round()

    def next_matching_round(self):
        round_data = build_matching_round(self.words)
        if not round_data:
            self.show_toast("Kho cần ít nhất 4 từ có nghĩa để chơi matching.", is_error=True)
            self.show_mode_selector()
            return

        self.current_matching = round_data
        self.matching_selected_left = None
        self.matching_selected_right = None
        self.matching_matched_ids = set()
        self.matching_status_lbl.configure(text="Chọn một nghĩa và ghép với từ đúng.")

        for frame in (self.matching_left_frame, self.matching_right_frame):
            for child in frame.winfo_children():
                child.destroy()

        ctk.CTkLabel(self.matching_left_frame, text="Nghĩa", font=("Segoe UI", 18, "bold"), text_color="#93C5FD").pack(pady=(16, 10))
        ctk.CTkLabel(self.matching_right_frame, text="Từ", font=("Segoe UI", 18, "bold"), text_color="#F9A8D4").pack(pady=(16, 10))

        self.matching_left_buttons = {}
        self.matching_right_buttons = {}

        for pair in round_data["left"]:
            meaning_text = pair["meaning"]
            if len(meaning_text) > 56:
                meaning_text = meaning_text[:53] + "..."
            btn = ctk.CTkButton(
                self.matching_left_frame,
                text=meaning_text,
                height=56,
                corner_radius=14,
                fg_color="#1E293B",
                hover_color="#334155",
                anchor="w",
                command=lambda p=pair: self._select_matching_side("left", p["id"]),
            )
            btn.pack(fill="x", padx=14, pady=6)
            self.matching_left_buttons[pair["id"]] = btn

        for pair in round_data["right"]:
            btn = ctk.CTkButton(
                self.matching_right_frame,
                text=pair["word"],
                height=56,
                corner_radius=14,
                fg_color="#1E293B",
                hover_color="#334155",
                command=lambda p=pair: self._select_matching_side("right", p["id"]),
            )
            btn.pack(fill="x", padx=14, pady=6)
            self.matching_right_buttons[pair["id"]] = btn

    def _select_matching_side(self, side: str, pair_id: int):
        if pair_id in getattr(self, "matching_matched_ids", set()):
            return

        if side == "left":
            self.matching_selected_left = pair_id
        else:
            self.matching_selected_right = pair_id

        self._refresh_matching_button_styles()
        if self.matching_selected_left and self.matching_selected_right:
            self._evaluate_matching_pair()

    def _refresh_matching_button_styles(self):
        for pair_id, btn in getattr(self, "matching_left_buttons", {}).items():
            color = "#10B981" if pair_id in self.matching_matched_ids else "#3B82F6" if pair_id == self.matching_selected_left else "#1E293B"
            btn.configure(fg_color=color)
        for pair_id, btn in getattr(self, "matching_right_buttons", {}).items():
            color = "#10B981" if pair_id in self.matching_matched_ids else "#EC4899" if pair_id == self.matching_selected_right else "#1E293B"
            btn.configure(fg_color=color)

    def _evaluate_matching_pair(self):
        if self.matching_selected_left == self.matching_selected_right:
            pair_id = self.matching_selected_left
            self.matching_matched_ids.add(pair_id)
            self.score += 10
            self.matching_status_lbl.configure(text="Ghép đúng! 🎉")
            self.lbl_score.configure(text=f"Score: {self.score}")
            self.matching_selected_left = None
            self.matching_selected_right = None
            self._refresh_matching_button_styles()
            if len(self.matching_matched_ids) == len(self.current_matching["pairs"]):
                self.matching_status_lbl.configure(text="Bạn đã ghép xong 1 bộ mới. Chuẩn bị vòng tiếp theo...")
                self.after(1000, self.next_matching_round)
        else:
            self.score = max(0, self.score - 2)
            self.lbl_score.configure(text=f"Score: {self.score}")
            self.matching_status_lbl.configure(text="Chưa đúng, thử lại nhé.")
            self.after(500, self._reset_matching_selection)

    def _reset_matching_selection(self):
        self.matching_selected_left = None
        self.matching_selected_right = None
        self._refresh_matching_button_styles()

    def start_daily_challenge(self):
        self.daily_questions = build_daily_challenge(self.words, size=3)
        if not self.daily_questions:
            self.show_toast("Kho cần ít nhất 4 từ có nghĩa để mở daily challenge.", is_error=True)
            return

        self.game_mode = "daily_challenge"
        self.daily_question_index = 0
        self.score = 0
        self.show_screen(self.game_frame)
        self.lbl_score.configure(text="Score: 0")
        self.lbl_timer.configure(text="Daily Challenge")
        self.build_quiz_ui()
        self.next_daily_challenge_question()

    def next_daily_challenge_question(self):
        if self.daily_question_index >= len(self.daily_questions):
            self._mark_daily_challenge_complete()
            for w in self.game_content.winfo_children():
                w.destroy()
            ctk.CTkLabel(
                self.game_content,
                text="🏁 Daily Challenge Hoàn Thành!",
                font=("Segoe UI", 34, "bold"),
                text_color="#F59E0B",
            ).pack(pady=(50, 10))
            ctk.CTkLabel(
                self.game_content,
                text=f"Điểm hôm nay: {self.score}\nStreak hiện tại: {self.daily_state.get('streak', 0)} ngày",
                font=("Segoe UI", 22),
                text_color="#F8FAFC",
                justify="center",
            ).pack(pady=10)
            ctk.CTkButton(
                self.game_content,
                text="Quay lại menu game",
                width=220,
                height=52,
                corner_radius=14,
                fg_color="#8B5CF6",
                hover_color="#7C3AED",
                command=self.show_mode_selector,
            ).pack(pady=25)
            return

        question = self.daily_questions[self.daily_question_index]
        self.current_answer = question["answer"]
        self.lbl_question.configure(text=question["word"], text_color="#F97316")
        self.card_main.configure(border_color="#F97316")
        self.lbl_timer.configure(text=f"Daily Challenge {self.daily_question_index + 1}/{len(self.daily_questions)}")

        for index, btn in enumerate(self.ans_buttons):
            btn.configure(
                text=question["options"][index],
                fg_color="#334155",
                state="normal",
                command=lambda ans=question["options"][index], b=btn: self.check_daily_challenge(ans, b),
            )

    def check_daily_challenge(self, user_ans, btn):
        for b in self.ans_buttons:
            b.configure(state="disabled")

        if user_ans == self.current_answer:
            self.score += 12
            btn.configure(fg_color="#10B981")
            self.lbl_question.configure(text="Đúng! ✅", text_color="#10B981")
            self.card_main.configure(border_color="#10B981")
        else:
            self.score = max(0, self.score - 3)
            btn.configure(fg_color="#EF4444")
            self.lbl_question.configure(text="Sai! ❌", text_color="#EF4444")
            self.card_main.configure(border_color="#EF4444")
            for b in self.ans_buttons:
                if b.cget("text") == self.current_answer:
                    b.configure(fg_color="#10B981")

        self.lbl_score.configure(text=f"Score: {self.score}")
        self.daily_question_index += 1
        self.after(900, self.next_daily_challenge_question)

    # --- MODE 1: TRẮC NGHIỆM (Quiz) ---
    def play_quiz(self):
        self.game_mode = "quiz"
        self.score = 0
        self.speed_time_left = 30
        self.lbl_score.configure(text="Score: 0")
        self.lbl_timer.configure(text=f"⏱️ {self.speed_time_left}s", text_color="#10B981")
        self.build_quiz_ui()
        self.next_quiz()

        if self.game_timer_id:
            self.after_cancel(self.game_timer_id)
        self.game_timer_id = self.after(1000, self.quiz_tick)

    def quiz_tick(self):
        if self.game_mode != "quiz":
            return

        self.speed_time_left -= 1
        self.lbl_timer.configure(text=f"⏱️ {self.speed_time_left}s")

        if self.speed_time_left <= 5:
            self.lbl_timer.configure(text_color="#EF4444")
        elif self.speed_time_left <= 10:
            self.lbl_timer.configure(text_color="#F59E0B")
        else:
            self.lbl_timer.configure(text_color="#10B981")

        if self.speed_time_left <= 0:
            self.finish_quiz_mode()
            return

        self.game_timer_id = self.after(1000, self.quiz_tick)

    def finish_quiz_mode(self):
        self.game_mode = None
        self.game_timer_id = None
        for w in self.game_content.winfo_children():
            w.destroy()

        result = ctk.CTkLabel(self.game_content, text="⏱️ Hết Giờ!", font=("Segoe UI", 48, "bold"), text_color="#F59E0B")
        result.pack(pady=(60, 20))

        score_lbl = ctk.CTkLabel(self.game_content, text=f"Điểm số: {self.score}", font=("Segoe UI", 36, "bold"), text_color="#10B981")
        score_lbl.pack(pady=10)

        btn_retry = ctk.CTkButton(self.game_content, text="🔄 Chơi Lại", width=200, height=55, font=("Segoe UI", 20, "bold"),
                                  corner_radius=15, fg_color="#8B5CF6", hover_color="#7C3AED", command=self.show_mode_selector)
        btn_retry.pack(pady=30)

    def check_quiz(self, user_ans, btn):
        if self.game_mode != "quiz":
            return
        for b in self.ans_buttons: b.configure(state="disabled")
        if user_ans == self.current_answer:
            self.score += 10
            btn.configure(fg_color="#10B981")
            self.lbl_question.configure(text="Đúng! ✅", text_color="#10B981")
            self.card_main.configure(border_color="#10B981")
            self.after(800, self.next_quiz)
        else:
            self.score = max(0, self.score - 5)
            btn.configure(fg_color="#EF4444")
            self.lbl_question.configure(text="Sai! ❌", text_color="#EF4444")
            self.card_main.configure(border_color="#EF4444")
            for b in self.ans_buttons:
                if b.cget("text") == self.current_answer: b.configure(fg_color="#10B981")
            self.after(1500, self.next_quiz)
        self.lbl_score.configure(text=f"Score: {self.score}")

    # --- MODE 2: XÁO CHỮ (Scramble) ---
    def play_scramble(self):
        self.game_mode = "scramble"
        self.score = 0
        self.lbl_score.configure(text="Score: 0")
        self.lbl_timer.configure(text="Xáo Chữ")
        self.build_typing_ui("Sắp xếp lại các chữ cái bị xáo trộn thành từ tiếng Anh đúng!")
        self.next_scramble()

    def check_scramble(self):
        answer = self.type_entry.get().strip().lower()
        if answer == self.scramble_word.lower():
            self.score += 15
            self.lbl_feedback.configure(text=f"Tuyệt vời! 🎉 ({self.scramble_word})", text_color="#10B981")
            self.card_main.configure(border_color="#10B981")
            self.after(1000, self.next_scramble)
        else:
            self.score = max(0, self.score - 5)
            self.lbl_feedback.configure(text=f"Sai rồi! Đáp án: {self.scramble_word} 💔", text_color="#EF4444")
            self.card_main.configure(border_color="#EF4444")
            self.after(1800, self.next_scramble)
        self.lbl_score.configure(text=f"Score: {self.score}")

    def play_speed(self):
        self.play_quiz()

    def speed_tick(self):
        self.quiz_tick()

    # --- MODE 4: DỊCH NGƯỢC (Reverse) ---
    def play_reverse(self):
        self.game_mode = "reverse"
        self.score = 0
        self.lbl_score.configure(text="Score: 0")
        self.lbl_timer.configure(text="Dịch Ngược")
        self.build_typing_ui("Nhìn nghĩa tiếng Việt → gõ đúng từ tiếng Anh!")
        self.next_reverse()

    def check_reverse(self):
        answer = self.type_entry.get().strip().lower()
        if answer == self.reverse_word.lower():
            self.score += 15
            self.lbl_feedback.configure(text=f"Hoàn hảo! 🎉 ({self.reverse_word})", text_color="#10B981")
            self.card_main.configure(border_color="#10B981")
            self.after(1000, self.next_reverse)
        else:
            self.score = max(0, self.score - 5)
            self.lbl_feedback.configure(text=f"Sai! Đáp án đúng: {self.reverse_word} 💔", text_color="#EF4444")
            self.card_main.configure(border_color="#EF4444")
            self.after(1800, self.next_reverse)
        self.lbl_score.configure(text=f"Score: {self.score}")

    # ================= 5. MÀN HÌNH ĐỌC BÁO (NEWS ARTICLES) =================
    def setup_news_screen(self):
        self.news_bg_canvas = install_cosmic_background(self.news_frame)
        top_bar = ctk.CTkFrame(self.news_frame, fg_color="transparent")
        top_bar.pack(fill="x", padx=25, pady=(25, 15))

        btn_back = self._build_home_screen_pill(
            top_bar,
            lambda: self.show_screen(self.home_frame),
            width=178,
            height=45,
        )
        btn_back.pack(side="left")
        
        title = ctk.CTkLabel(top_bar, text="News Reader", font=("Segoe UI", 26, "bold"), text_color="#06B6D4")
        title.pack(side="right")
        
        # Thanh tìm kiếm keyword
        search_bar = ctk.CTkFrame(self.news_frame, fg_color="transparent")
        search_bar.pack(fill="x", padx=25, pady=(0, 15))
        
        self.news_search_var = ctk.StringVar()
        self.news_search_entry = ctk.CTkEntry(search_bar, textvariable=self.news_search_var,
                                              placeholder_text="Enter an English keyword, for example technology, climate, or AI...",
                                              height=50, font=("Segoe UI", 17), corner_radius=15,
                                              border_width=2, border_color="#06B6D4", fg_color="#1E293B")
        self.news_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.news_search_entry.bind("<Return>", lambda e: self.search_news())
        
        btn_search = ctk.CTkButton(search_bar, text="Search", width=130, height=50, font=("Segoe UI", 16, "bold"),
                                   corner_radius=15, fg_color="#06B6D4", hover_color="#0891B2", command=self.search_news)
        btn_search.pack(side="left")
        
        # Nút lấy keyword random từ kho
        btn_random = ctk.CTkButton(search_bar, text="Random Word", width=160, height=50, font=("Segoe UI", 16, "bold"),
                                   corner_radius=15, fg_color="#8B5CF6", hover_color="#7C3AED", command=self.search_news_random)
        btn_random.pack(side="left", padx=(10, 0))
        
        self.news_status = ctk.CTkLabel(self.news_frame, text="Enter a keyword or use a random word from your notebook.", 
                                        font=("Segoe UI", 15), text_color="#94A3B8")
        self.news_status.pack(anchor="w", padx=25, pady=(0, 10))
        
        # Khung hiển thị bài viết
        self.news_panel = NewsPanel(self.news_frame)
        self.news_panel.pack(fill="both", expand=True, padx=25, pady=(0, 25))

    def setup_youtube_screen(self):
        self.youtube_bg_canvas = install_cosmic_background(self.youtube_frame)
        top_bar = ctk.CTkFrame(self.youtube_frame, fg_color="transparent")
        top_bar.pack(fill="x", padx=25, pady=(18, 10))

        btn_back = self._build_home_screen_pill(
            top_bar,
            lambda: self.show_screen(self.home_frame),
            width=178,
            height=45,
        )
        btn_back.pack(side="left")

        title = ctk.CTkLabel(
            top_bar,
            text="Related Videos",
            font=("Segoe UI", 26, "bold"),
            text_color="#06B6D4",
        )
        title.pack(side="right")

        search_bar = ctk.CTkFrame(self.youtube_frame, fg_color="transparent")
        search_bar.pack(fill="x", padx=25, pady=(0, 8))

        self.youtube_search_var = ctk.StringVar()
        self.youtube_search_entry = ctk.CTkEntry(
            search_bar,
            textvariable=self.youtube_search_var,
            placeholder_text="Search videos for a vocabulary word...",
            height=50,
            font=("Segoe UI", 17),
            corner_radius=15,
            border_width=2,
            border_color="#06B6D4",
            fg_color="#1E293B",
        )
        self.youtube_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.youtube_search_entry.bind("<Return>", lambda e: self.trigger_youtube_search())

        btn_search = ctk.CTkButton(
            search_bar,
            text="Search Videos",
            width=150,
            height=50,
            font=("Segoe UI", 16, "bold"),
            corner_radius=15,
            fg_color="#06B6D4",
            hover_color="#0891B2",
            command=self.trigger_youtube_search,
        )
        btn_search.pack(side="left")

        self.youtube_query_lbl = ctk.CTkLabel(
            self.youtube_frame,
            text="Search a word first to see related videos.",
            font=ui_font(self, 14),
            text_color="#94A3B8",
            fg_color="transparent",
            anchor="w",
        )
        self.youtube_query_lbl.pack(fill="x", padx=25, pady=(0, 10))
        self.youtube_query_lbl.pack_configure(pady=(0, 6))

        self.youtube_panel = YouTubePanel(self.youtube_frame, api_key=self.youtube_api_key)
        self.youtube_panel.pack(fill="both", expand=True, padx=25, pady=(0, 18))

    def search_news_random(self):
        if not self.words:
            self.show_toast("Kho từ vựng rỗng, hãy thêm từ trước!", is_error=True)
            return
        keyword = random.choice(list(self.words.keys()))
        self.news_search_var.set(keyword)
        self.search_news()

    def search_news(self):
        keyword = self.news_search_var.get().strip()
        if not keyword:
            if hasattr(self, "news_panel"):
                self.news_panel.clear()
            self.news_status.configure(text="Enter a keyword or use a random word from your notebook.")
            return

        self.news_status.configure(text=f"Showing Google News results for '{keyword}'.")
        if hasattr(self, "news_panel"):
            self.news_panel.search(keyword)
            return

        threading.Thread(target=self._fetch_news_worker, args=(keyword,), daemon=True).start()

    def _fetch_news_worker(self, keyword):
        try:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(keyword)}&hl=en-US&gl=US&ceid=US:en"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=5)
            xml_data = response.read().decode('utf-8')
            
            root = ET.fromstring(xml_data)
            articles = []
            for item in root.findall('.//item'):
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')
                source = item.find('source')
                
                if title is not None and link is not None:
                    articles.append({
                        "title": title.text or "",
                        "link": link.text or "",
                        "date": (pub_date.text[:22] if pub_date is not None and pub_date.text else ""),
                        "source": (source.text if source is not None and source.text else "Unknown")
                    })
                if len(articles) >= 15:
                    break
            
            self.after(0, lambda: self._render_news(keyword, articles))
        except Exception as e:
            self.after(0, lambda: self.news_status.configure(text=f"Connection error: {e}"))

    def _render_news(self, keyword, articles):
        for widget in self.news_list_frame.winfo_children():
            widget.destroy()
            
        if not articles:
            self.news_status.configure(text=f"No articles found for '{keyword}'.")
            return
            
        self.news_status.configure(text=f"Found {len(articles)} articles for '{keyword}' (click to open in browser)")
        
        for i, art in enumerate(articles):
            card = ctk.CTkFrame(self.news_list_frame, fg_color="#1E293B", corner_radius=12, border_width=1, border_color="#334155", cursor="hand2")
            card.pack(fill="x", pady=6, padx=5)
            
            # Số thứ tự
            num_lbl = ctk.CTkLabel(card, text=f"{i+1}", font=("Segoe UI", 18, "bold"), text_color="#06B6D4", width=35)
            num_lbl.pack(side="left", padx=(15, 10), pady=12)
            
            # Nội dung
            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(side="left", fill="both", expand=True, padx=(0, 15), pady=12)
            
            title_lbl = ctk.CTkLabel(content, text=art["title"], font=("Segoe UI", 17, "bold"), text_color="#F8FAFC", 
                                     anchor="w", justify="left", wraplength=600)
            title_lbl.pack(anchor="w")
            
            meta_text = f"📌 {art['source']}  •  🕐 {art['date']}"
            meta_lbl = ctk.CTkLabel(content, text=meta_text, font=("Segoe UI", 13), text_color="#64748B", anchor="w")
            meta_lbl.pack(anchor="w", pady=(3, 0))
            
            # Click để mở trình duyệt
            link = art["link"]
            for widget in (card, num_lbl, title_lbl, meta_lbl, content):
                widget.bind("<Button-1>", lambda e, u=link: webbrowser.open(u))
            
            # Hover effect
            def on_enter(e, c=card): c.configure(border_color="#06B6D4")
            def on_leave(e, c=card): c.configure(border_color="#334155")
            for widget in (card, num_lbl, title_lbl, meta_lbl, content):
                widget.bind("<Enter>", on_enter)
                widget.bind("<Leave>", on_leave)



    # ================= 5. HỆ THỐNG GỐC VÀ RENDER POOL ĐỐI TƯỢNG (OBJECTS) =================
    def create_toast(self):
        self.toast_frame = ctk.CTkFrame(self.container, fg_color="#333333", corner_radius=15, border_width=1, border_color="#555555")
        self.toast_label = ctk.CTkLabel(self.toast_frame, text="", font=("Segoe UI", 16, "bold"), text_color="#ffffff")
        self.toast_label.pack(padx=30, pady=15)
        self.toast_timer = None
        
    def show_toast(self, message, is_error=False, duration=3500):
        if is_error:
            self.toast_frame.configure(fg_color="#7F1D1D", border_color="#DC2626")
            self.toast_label.configure(text_color="#FECACA")
        else:
            self.toast_frame.configure(fg_color="#1E3A8A", border_color="#3B82F6")
            self.toast_label.configure(text_color="#ffffff")
            
        self.toast_label.configure(text=repair_text(message))
        self.toast_frame.lift()
        self.toast_frame.place(relx=0.5, rely=0.96, anchor="s") 
        if self.toast_timer: self.after_cancel(self.toast_timer)
        if duration > 0: self.toast_timer = self.after(duration, lambda: self.toast_frame.place_forget())

    def init_card_pool(self):
        """Pool giao diện hỗ trợ Cấu trúc Object (Từ loại, Phiên âm, Ví dụ, Bookmark, Checkbox)"""
        self.card_pool = []
        for _ in range(30):
            card = ctk.CTkFrame(self.list_frame, fg_color="#1E293B", corner_radius=15, border_width=1, border_color="#334155")
            
            # CHECKBOX ở cạnh trái cùng
            chk_var = ctk.BooleanVar(value=False)
            chk_box = ctk.CTkCheckBox(card, text="", variable=chk_var, width=30, checkbox_width=24, checkbox_height=24,
                                      corner_radius=6, fg_color="#3B82F6", hover_color="#2563EB", border_color="#475569")
            chk_box.pack(side="left", padx=(15, 5), pady=15)
            
            # Cột trái cho Từ/Phiên Âm
            left_frame = ctk.CTkFrame(card, fg_color="transparent")
            left_frame.pack(side="left", padx=(5, 20), pady=15, fill="y")
            
            word_top = ctk.CTkFrame(left_frame, fg_color="transparent")
            word_top.pack(anchor="w")

            speak_btn = ctk.CTkButton(
                word_top,
                text="🔊",
                width=34,
                height=34,
                font=("Segoe UI", 15),
                corner_radius=10,
                fg_color="#0F172A",
                hover_color="#1D4ED8",
                text_color="#BFDBFE",
                border_width=1,
                border_color="#334155",
            )
            speak_btn.pack(side="left", padx=(0, 10))
            
            word_lbl = ctk.CTkLabel(word_top, text="", font=("Segoe UI", 24, "bold"), text_color="#60A5FA")
            word_lbl.pack(side="left")
            
            star_btn = ctk.CTkLabel(word_top, text="☆", font=("Segoe UI", 22), cursor="hand2", text_color="#64748B")
            star_btn.pack(side="left", padx=(10, 0))
            
            phonetic_lbl = ctk.CTkLabel(left_frame, text="", font=("Segoe UI", 15, "italic"), text_color="#94A3B8")
            phonetic_lbl.pack(anchor="w", pady=(2, 0))
            
            # Cột phải cho Nghĩa, Ví dụ
            right_frame = ctk.CTkFrame(card, fg_color="transparent")
            right_frame.pack(side="left", padx=(10, 20), pady=15, fill="both", expand=True)
            
            mean_lbl = ctk.CTkLabel(right_frame, text="", font=("Segoe UI", 18, "bold"), text_color="#F8FAFC", justify="left", wraplength=400)
            mean_lbl.pack(anchor="w")
            
            example_lbl = ctk.CTkLabel(right_frame, text="", font=("Segoe UI", 14), text_color="#A0AEC0", justify="left", wraplength=400)
            example_lbl.pack(anchor="w", pady=(4, 0))

            # Khu vực Hành vi
            vibe_frame = ctk.CTkFrame(right_frame, fg_color="#0F172A", corner_radius=8)
            vibe_frame.pack(fill="x", pady=(10, 5), padx=(0, 20))
            
            pragmatics_lbl = ctk.CTkLabel(vibe_frame, text="", font=("Segoe UI", 13, "italic"), text_color="#FCD34D")
            pragmatics_lbl.pack(anchor="w", padx=10, pady=(5, 5))

            # Bindings
            def on_double_click(e, lbl=word_lbl): self.play_audio(lbl.cget("text"))
            def on_right_click(e, w_lbl=word_lbl): self.show_context_menu(e, w_lbl.cget("text"))

            for widget in (left_frame, word_lbl, phonetic_lbl, right_frame, mean_lbl, example_lbl):
                widget.bind("<Double-Button-1>", on_double_click)
                widget.bind("<Button-3>", on_right_click)

            self.card_pool.append({
                "card": card, "word_lbl": word_lbl, "phonetic_lbl": phonetic_lbl, 
                "mean_lbl": mean_lbl, "example_lbl": example_lbl, "star_btn": star_btn, 
                "speak_btn": speak_btn,
                "chk_var": chk_var, "chk_box": chk_box, "is_packed": False,
                "vibe_frame": vibe_frame, "pragmatics_lbl": pragmatics_lbl,
                "left_frame": left_frame
            })

    def start_add_words_thread(self): threading.Thread(target=self.add_words, daemon=True).start()

    def show_context_menu(self, event, word):
        menu = tk.Menu(self, tearoff=0, bg="#1E293B", fg="#F8FAFC", activebackground="#3B82F6", activeforeground="white", 
                       font=("Segoe UI", 13), relief="flat", bd=2)
        
        # Nếu đang có từ được chọn hàng loạt, hiện menu hàng loạt
        if self.selected_words:
            n = len(self.selected_words)
            menu.add_command(label=f"☁️ Cập nhật API cho {n} từ đã chọn", command=self.cloud_update_selected)
            menu.add_command(label=f"⭐ Yêu thích {n} từ đã chọn", command=self.favorite_selected)
            menu.add_command(label=f"🗑 Xóa {n} từ đã chọn", command=self.delete_selected)
            menu.add_separator()
            menu.add_command(label="✖ Bỏ chọn tất cả", command=self.deselect_all)
        else:
            # Menu đơn lẻ cho 1 từ
            menu.add_command(label=f"🔊 Nghe phát âm: {word}", command=lambda: self.play_audio(word))
            menu.add_command(label=f"☁️ Cập nhật dữ liệu từ Internet", command=lambda: self.cloud_update_single(word))
            menu.add_separator()
            
            is_fav = self.words.get(word, {}).get("is_favorite", False)
            fav_text = "💔 Bỏ Yêu thích" if is_fav else "⭐ Đánh dấu Yêu thích"
            menu.add_command(label=fav_text, command=lambda: self.toggle_favorite(word))
            menu.add_command(label=f"✏️ Sửa nghĩa tiếng Việt", command=lambda: self.edit_word(word))
            menu.add_command(label=f"📝 Sửa câu ví dụ", command=lambda: self.edit_example(word))
            menu.add_command(label=f"🏷️ Sửa mức CEFR", command=lambda: self.edit_level(word))
            menu.add_separator()
            
            menu.add_command(label=f"🕸 Mạng nhện 3D (Spider-Web)", command=lambda: self.generate_3d_graph(word))
            menu.add_separator()
            
            menu.add_command(label=f"☑ Chọn từ này (Multi-select)", command=lambda: self.toggle_select(word, True))
            menu.add_command(label="❌ XÓA từ này vĩnh viễn", command=lambda: self.delete_word(word))
        
        try: menu.tk_popup(event.x_root, event.y_root)
        finally: menu.grab_release()

    def generate_3d_graph(self, word):
        """Tạo file HTML chứa đồ họa 3D-Force-Graph và mở bằng trình duyệt"""
        self.show_toast(f"🕸 Đang đan mạng nhện 3D cho '{word}'...", duration=2000)
        
        def _worker():
            try:
                # 1. Liên kết bằng Datamuse API (rel_syn và rel_trg)
                url = f"https://api.datamuse.com/words?rel_syn={urllib.parse.quote(word)}&max=15"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                res = urllib.request.urlopen(req, timeout=3)
                synonyms = [d["word"] for d in json.loads(res.read().decode('utf-8'))]

                url2 = f"https://api.datamuse.com/words?rel_trg={urllib.parse.quote(word)}&max=20"
                req2 = urllib.request.Request(url2, headers={'User-Agent': 'Mozilla/5.0'})
                res2 = urllib.request.urlopen(req2, timeout=3)
                triggers = [d["word"] for d in json.loads(res2.read().decode('utf-8'))]

                nodes = [{"id": word, "group": 1, "size": 30}]
                links = []

                # Nút cho Đồng nghĩa
                for s in synonyms:
                    if s != word:
                        nodes.append({"id": s, "group": 2, "size": 15})
                        links.append({"source": word, "target": s, "value": 2})

                # Nút cho Ngữ cảnh (Triggers)
                for t in triggers:
                    if t != word and t not in synonyms:
                        nodes.append({"id": t, "group": 3, "size": 10})
                        links.append({"source": word, "target": t, "value": 1})
                        
                # Link chéo cho mạng lưới thêm sinh động
                for i in range(len(synonyms)-1):
                    links.append({"source": synonyms[i], "target": synonyms[i+1], "value": 1})

                graph_data = {"nodes": nodes, "links": links}
                
                # 2. Xây dựng trang HTML 3D-Force-Graph
                html = f'''<!DOCTYPE html>
<html><head>
  <style> body {{ margin: 0; background-color: #0F172A; font-family: sans-serif; overflow: hidden; }}
  #title {{ position: absolute; top: 10px; left: 10px; color: white; opacity: 0.8; padding: 10px; background: rgba(0,0,0,0.5); border-radius: 8px; }}</style>
  <script src="https://unpkg.com/3d-force-graph"></script>
</head><body>
  <div id="title"><h2>Adam Dictionary 3D: {word}</h2><span style="color:#EF4444">■ Tâm</span> | <span style="color:#3B82F6">■ Đồng nghĩa</span> | <span style="color:#10B981">■ Ngữ cảnh/hành vi</span></div>
  <div id="3d-graph"></div>
  <script>
    const gData = {json.dumps(graph_data)};
    const Graph = ForceGraph3D()(document.getElementById('3d-graph'))
      .graphData(gData)
      .nodeColor(n => n.group === 1 ? '#EF4444' : n.group === 2 ? '#3B82F6' : '#10B981')
      .nodeVal(n => n.size)
      .nodeLabel('id')
      .linkWidth(2)
      .linkColor(() => 'rgba(255,255,255,0.15)');
      
    // Cinematic camera sweep
    let angle = 0;
    setInterval(() => {{
      angle += Math.PI / 300;
      Graph.cameraPosition({{ x: 150 * Math.sin(angle), z: 150 * Math.cos(angle) }});
    }}, 20);
  </script>
</body></html>'''
                path = os.path.join(os.getcwd(), 'graph.html')
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(html)
                    
                import webbrowser
                webbrowser.open(f"file:///{path.replace(os.sep, '/')}")
                self.after(0, lambda: self.show_toast(f"🎉 Mạng nhện 3D '{word}' đã được mở trên trình duyệt!"))
                
            except Exception as e:
                self.after(0, lambda e=e: self.show_toast(f"❌ Lỗi đan lưới 3D: {str(e)}", is_error=True))
        
        threading.Thread(target=_worker, daemon=True).start()

    def cloud_update_single(self, word):
        """Cập nhật lại dữ liệu đầy đủ cho 1 từ đã có trong kho"""
        self.show_toast(f"☁️ Đang kéo lại dữ liệu cho '{word}'...", duration=0)
        threading.Thread(target=self._cloud_lookup_worker, args=(word,), daemon=True).start()

    def cloud_update_selected(self):
        """Cập nhật dữ liệu API cho TẤT CẢ từ được chọn"""
        words_to_update = list(self.selected_words)
        if not words_to_update: return
        self.show_toast(f"☁️ Đang cập nhật API cho {len(words_to_update)} từ...", duration=0)
        threading.Thread(target=self._cloud_bulk_worker, args=(words_to_update,), daemon=True).start()

    def _fetch_single_word_data(self, word):
        return lookup_remote_word(
            word,
            fetch_entry=self.fetch_remote_entry,
            fetch_suggestions=fetch_datamuse_suggestions,
            fetch_collocations=self.fetch_datamuse_collocations,
        )

    def _cloud_bulk_worker(self, words):
        """ThreadPool: Chạy 4 luồng song song, nhanh gấp 4 lần"""
        count = 0
        failed = 0
        total = len(words)
        
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(self._fetch_single_word_data, w): w for w in words}
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=8)
                    if result.get("found"):
                        cache_lookup_result(self.words, result)
                        count += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                
                self.after(0, lambda c=count, f=failed, t=total: 
                           self.show_toast(f"☁️ Song song x4: {c+f}/{t} (✅{c} ❌{f})", duration=0))
        
        self.save_data()
        self.after(0, lambda: self.selected_words.clear())
        self.after(0, self.update_list)
        msg = f"🎉 Hoàn tất! Cập nhật {count}/{total} từ trong {round(total*0.5, 1)}s."
        if failed: msg += f" ({failed} lỗi)"
        self.after(0, lambda: self.show_toast(msg, is_error=(failed > 0)))

    def edit_word(self, word):
        dialog = ctk.CTkInputDialog(text=f"Nhập tiếng Việt mới cho '{word}':", title="Sửa nghĩa từ vựng")
        new_mean = dialog.get_input()
        if update_entry_field(self.words, word, "meaning", new_mean or ""):
            self.save_data(refresh_ui=False)
            self.update_list()
            self.show_toast(f"Đã cập nhật Database cho '{word}'!")

    def edit_example(self, word):
        dialog = ctk.CTkInputDialog(text=f"Nhập câu ví dụ mới cho '{word}':", title="Sửa Ví dụ")
        new_ex = dialog.get_input()
        if update_entry_field(self.words, word, "example", new_ex or ""):
            self.save_data()
            self.update_list()
            self.show_toast(f"Đã cập nhật Ví dụ cho '{word}'!")

    def edit_level(self, word):
        current_level = self.words.get(word, {}).get("level", "")
        dialog = ctk.CTkInputDialog(
            text=f"Nhập mức CEFR cho '{word}' ({', '.join(VALID_CEFR_LEVELS)}):",
            title=f"Sửa CEFR{f' - hiện tại {current_level}' if current_level else ''}",
        )
        new_level = (dialog.get_input() or "").strip().upper()
        if new_level in VALID_CEFR_LEVELS and update_entry_field(self.words, word, "level", new_level):
            self.save_data()
            self.update_list()
            self.show_toast(f"Đã cập nhật CEFR của '{word}' thành {new_level}.")
        elif new_level:
            self.show_toast("CEFR không hợp lệ. Hãy dùng A1, A2, B1, B2, C1 hoặc C2.", is_error=True)

    def on_checkbox_toggle(self, word, chk_var):
        if chk_var.get():
            self.selected_words.add(word)
        else:
            self.selected_words.discard(word)
        self.update_bulk_bar()

    def toggle_select(self, word, state):
        if state: self.selected_words.add(word)
        else: self.selected_words.discard(word)
        self.update_list()

    def deselect_all(self):
        self.selected_words.clear()
        self.update_list()

    def update_bulk_bar(self):
        if self.selected_words:
            self.bulk_select_label.configure(text=f"Đã chọn: {len(self.selected_words)} từ")
            self.bulk_bar.pack(fill="x", padx=25, pady=(0, 8), before=self.list_header)
        else:
            self.bulk_bar.pack_forget()

    def cleanup_temp_audio(self):
        for f in glob.glob("temp_audio_*.mp3"):
            try: os.remove(f)
            except: pass

    def clear_placeholder(self, event):
        if not self.placeholder_cleared:
            self.input_text.delete("0.0", "end")
            self.input_text.configure(text_color="#ffffff")
            self.placeholder_cleared = True

    def restore_placeholder(self, event):
        raw_text = self.input_text.get("0.0", "end").strip()
        if not raw_text:
            self.placeholder_cleared = False
            self.input_text.configure(text_color="#64748B")
            self.input_text.insert("0.0", self.placeholder_text)
            
    def play_audio(self, word):
        if not AUDIO_ENABLED or not word:
            return
        self.show_toast(f"🔊 Đang phát âm: {word}", duration=1500)
        threading.Thread(target=self.speak, args=(word,), daemon=True).start()

    def speak(self, text):
        global AUDIO_ENABLED
        if not AUDIO_ENABLED or not text:
            return
        try:
            if os.name == "nt":
                safe_text = str(text).replace("'", "''")
                script = (
                    "Add-Type -AssemblyName System.Speech;"
                    "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                    "$speaker.Volume = 100;"
                    "$speaker.Rate = 0;"
                    f"$speaker.Speak('{safe_text}');"
                )
                encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                    check=True,
                    capture_output=True,
                    text=True,
                    creationflags=creationflags,
                )
                return
        except Exception as e:
            print(f"[DEBUG] Windows speech warning: {e}")

        try:
            from gtts import gTTS
            from playsound import playsound

            tts = gTTS(text=text, lang='en')
            audio_file = f"temp_audio_{int(time.time()*100)}.mp3"
            tts.save(audio_file)
            playsound(audio_file)
            time.sleep(1)
            if os.path.exists(audio_file):
                try:
                    os.remove(audio_file)
                except Exception:
                    pass
        except Exception as e:
            print(f"[DEBUG] Audio fallback warning: {e}")

    def load_data(self):
        return load_dictionary(DATA_FILE)

    def save_data(self, refresh_ui=True):
        with self.save_lock:
            try:
                self.words = save_dictionary(DATA_FILE, self.words)
                self._sync_search_engine()
            except Exception as e:
                print(f"[DEBUG] Save failed: {e}")
                return
        if refresh_ui:
            self.refresh_word_of_day()

    def _sync_search_engine(self):
        if hasattr(self, "engine"):
            self.engine.set_words(self.words)
        else:
            self.engine = SearchEngine(self.words)

    def run_on_ui_thread(self, callback, *args, **kwargs):
        self.ui_queue.put((callback, args, kwargs))

    def _process_ui_queue(self):
        try:
            while not self.ui_queue.empty():
                callback, args, kwargs = self.ui_queue.get_nowait()
                try:
                    callback(*args, **kwargs)
                except Exception as exc:
                    print(f"[DEBUG] UI callback failed: {exc}")
        finally:
            if self.winfo_exists():
                self.after(50, self._process_ui_queue)

    def _filtered_word_keys(self, query=None, limit=30):
        if query is None:
            query = self.search_var.get() if hasattr(self, "search_var") else ""

        normalized_query = normalize_text(query)
        active_level = self.level_filter_var.get() if hasattr(self, "level_filter_var") else "All"
        inactive_levels = ("", "Tất cả", "All")
        requires_full_scan = self.showing_favorites or active_level not in inactive_levels

        if normalized_query:
            keys = self.engine.search(normalized_query, limit=None if requires_full_scan else limit)
        else:
            keys = self.engine.all_words(limit=None if requires_full_scan else limit)

        if active_level not in inactive_levels:
            keys = [
                word for word in keys
                if self.words.get(word, {}).get("level", "") == active_level
            ]

        if self.showing_favorites:
            keys = [
                word for word in keys if self.words.get(word, {}).get("is_favorite")
            ]

        normalized_lookup = {normalize_text(word): word for word in self.words}
        mapped_keys = []
        for word in keys:
            actual_key = normalized_lookup.get(normalize_text(word))
            if actual_key:
                mapped_keys.append(actual_key)
        keys = mapped_keys
        if limit is not None:
            keys = keys[:limit]
        return keys

    def _visible_word_keys(self, query=None, limit=30):
        return self._filtered_word_keys(query=query, limit=limit)

    def export_filtered_words(self, delimiter: str, extension: str, format_name: str = "table"):
        filtered_words = self._filtered_word_keys(limit=None)
        if not filtered_words:
            self.show_toast("Không có từ nào để xuất theo bộ lọc hiện tại.", is_error=True)
            return

        export_path = filedialog.asksaveasfilename(
            title=f"Xuất dữ liệu {extension.upper()}",
            defaultextension=f".{extension}",
            filetypes=[(f"{extension.upper()} files", f"*.{extension}"), ("All files", "*.*")],
            initialfile=f"adam-dictionary-export.{extension}",
        )
        if not export_path:
            return

        export_dictionary(
            export_path,
            {word: self.words[word] for word in filtered_words},
            delimiter=delimiter,
            format_name=format_name,
        )
        self.show_toast(f"Đã xuất {len(filtered_words)} từ sang {extension.upper()}.")

    def debounce_home_search(self):
        if self.home_search_timer:
            self.after_cancel(self.home_search_timer)
        self.home_search_timer = self.after(100, self._debounce_home_search_invoke)

    def _debounce_home_search_invoke(self):
        val = normalize_text(self.home_search_var.get())
        self.render_ac_frame(val, self.home_search_entry, self.home_ac_frame, self.apply_home_suggestion)

    def _debounce_search_invoke(self):
        val = normalize_text(self.search_var.get())
        self.render_ac_frame(val, self.search_entry, self.dict_ac_frame, self.apply_dict_suggestion)
        self.update_list()

    def update_list(self):
        search_term = normalize_text(self.search_var.get())
        self.cloud_btn.pack_forget()
        self.dict_ac_frame.place_forget()

        self.visible_words = self._visible_word_keys(search_term, limit=30)
        results = [(word, self.words[word]) for word in self.visible_words]

        if not results and search_term and " " not in search_term and not self.showing_favorites:
            self.list_header.configure(
                text=f"⚠ '{search_term}' không có trong kho nội bộ. Ấn Enter hoặc bấm nút ☁️ để tải từ Internet!"
            )
            self.cloud_btn.pack(pady=10)
        else:
            total_current = (
                len([key for key, value in self.words.items() if value.get("is_favorite")])
                if self.showing_favorites
                else len(self.words)
            )
            active_level = self.level_filter_var.get() if hasattr(self, "level_filter_var") else "All"
            title = "⭐ YÊU THÍCH" if self.showing_favorites else "📚 KHO TỔNG"
            if active_level not in ("", "Tất cả", "All"):
                title = f"{title} • CEFR {active_level}"
            if search_term:
                self.list_header.configure(text=f"{title} ({total_current} từ) - Tìm thấy {len(results)} kết quả")
            else:
                self.list_header.configure(text=f"{title} ({total_current} từ) - Đúp chuột để nghe, Chuột phải để xóa/sửa")

        for index, pool_item in enumerate(self.card_pool):
            if index < len(results):
                word, data = results[index]
                pool_item['word_lbl'].configure(text=word)

                pos_text = f"[{data['pos']}] " if data.get("pos") else ""
                phon_text = repair_text(data.get("phonetic", ""))
                level_text = data.get("level", "")
                phonetic_parts = [f"{pos_text}{phon_text}".strip()]
                if level_text:
                    phonetic_parts.append(f"CEFR {level_text}")
                full_phonetic = " • ".join([part for part in phonetic_parts if part])
                pool_item['phonetic_lbl'].configure(text=full_phonetic if full_phonetic else "Chưa có phát âm quốc tế")
                pool_item['mean_lbl'].configure(text=repair_text(data.get("meaning", "")))

                example = repair_text(data.get("example", ""))
                eng_meaning = repair_text(data.get("eng_meaning", ""))
                if example:
                    example_text = f"Vd: {example}"
                elif eng_meaning:
                    example_text = f"EN: {eng_meaning}"
                else:
                    example_text = "Chữ này mới nên trí não AI chưa liên kết được ví dụ."
                pool_item['example_lbl'].configure(text=example_text)

                star_icon = "⭐" if data.get("is_favorite") else "☆"
                star_color = "#FCD34D" if data.get("is_favorite") else "#64748B"
                pool_item['star_btn'].configure(text=star_icon, text_color=star_color)
                pool_item['star_btn'].unbind("<Button-1>")
                pool_item['star_btn'].bind("<Button-1>", lambda e, kw=word: self.toggle_favorite(kw))
                pool_item['speak_btn'].configure(command=lambda kw=word: self.play_audio(kw))

                pool_item['chk_var'].set(word in self.selected_words)
                pool_item['chk_box'].configure(command=lambda kw=word, cv=pool_item['chk_var']: self.on_checkbox_toggle(kw, cv))

                vibe = data.get("vibe") or self.generate_vibe_profile(word)
                pragmatics = repair_text(data.get("pragmatics", "")) or "Bấm 'Cập nhật API' để phân tích hành vi của từ"
                pool_item['pragmatics_lbl'].configure(text=f"🧠 {pragmatics}")

                pc = vibe["color"]
                pool_item['word_lbl'].configure(text_color=pc)
                pool_item['left_frame'].configure(border_color=pc, border_width=2, corner_radius=10)

                if not pool_item['is_packed']:
                    pool_item['card'].pack(fill="x", pady=8, padx=2)
                    pool_item['is_packed'] = True
            else:
                if pool_item['is_packed']:
                    pool_item['card'].pack_forget()
                    pool_item['is_packed'] = False

        self.update_bulk_bar()

    def _ghost_suffix(self, typed_text, suggestion):
        if not typed_text or not suggestion:
            return ""
        if suggestion.startswith(typed_text) and len(suggestion) > len(typed_text):
            return suggestion[len(typed_text) :]
        return ""

    def _set_active_suggestion(self, entry_widget, suggestion):
        typed_text = normalize_text(entry_widget.get())
        suffix = self._ghost_suffix(typed_text, suggestion)

        if entry_widget == getattr(self, "home_search_entry", None):
            self.current_home_suggestion = suggestion
            if hasattr(self, "home_search_bar"):
                self.home_search_bar._suggestion = suggestion
            if hasattr(self, "home_ghost_var"):
                self.home_ghost_var.set(suffix)
        elif entry_widget == getattr(self, "search_entry", None):
            self.current_dict_suggestion = suggestion
            if hasattr(self, "dict_ghost_var"):
                self.dict_ghost_var.set(suffix)

    def _clear_suggestion_state(self, entry_widget=None):
        if entry_widget is None or entry_widget == getattr(self, "home_search_entry", None):
            self.current_home_suggestion = ""
            if hasattr(self, "home_search_bar"):
                self.home_search_bar._suggestion = ""
            if hasattr(self, "home_ghost_var"):
                self.home_ghost_var.set("")
        if entry_widget is None or entry_widget == getattr(self, "search_entry", None):
            self.current_dict_suggestion = ""
            if hasattr(self, "dict_ghost_var"):
                self.dict_ghost_var.set("")

    def accept_home_suggestion(self, event=None):
        if self.current_home_suggestion:
            self.apply_home_suggestion(self.current_home_suggestion)
            self._clear_suggestion_state(self.home_search_entry)
            return "break"
        return None

    def accept_dict_suggestion(self, event=None):
        if self.current_dict_suggestion:
            self.apply_dict_suggestion(self.current_dict_suggestion)
            self._clear_suggestion_state(self.search_entry)
            return "break"
        return None

    def fetch_datamuse_collocations(self, word):
        return api_fetch_datamuse_collocations(word)

    def fetch_remote_entry(self, word):
        return fetch_dictionary_entry(word)

    def _search_youtube_videos(self, query):
        if not hasattr(self, "youtube_panel"):
            return
        normalized = normalize_text(query)
        self.current_video_query = normalized
        if hasattr(self, "youtube_search_var"):
            self.youtube_search_var.set(normalized)
        if hasattr(self, "youtube_query_lbl"):
            if normalized:
                self.youtube_query_lbl.configure(text=f"Videos for: {normalized}")
            else:
                self.youtube_query_lbl.configure(text="Search a word first to see related videos.")
        self.youtube_panel.search(normalized)

    def trigger_youtube_search(self):
        query = normalize_text(getattr(self, "youtube_search_var", ctk.StringVar(value="")).get())
        if not query:
            self._search_youtube_videos("")
            self.show_toast("Enter a word to search YouTube videos.", is_error=True)
            return
        self._search_youtube_videos(query)

    def open_youtube_videos(self):
        query = (
            normalize_text(getattr(self, "search_var", tk.StringVar(value="")).get())
            or normalize_text(getattr(self, "home_search_var", tk.StringVar(value="")).get())
            or normalize_text(getattr(self, "current_video_query", ""))
        )
        self.showing_favorites = False
        self.show_screen(self.youtube_frame)
        if query:
            self._search_youtube_videos(query)
        else:
            self._search_youtube_videos("")
            self.show_toast("Search a word first, or type one here to see related YouTube videos.", is_error=True)

    def resolve_import_entry(self, word):
        result = lookup_remote_word(
            word,
            fetch_entry=fetch_dictionary_entry,
            fetch_suggestions=lambda _word, max_results=1: [],
            fetch_collocations=self.fetch_datamuse_collocations,
        )
        entry = result.get("entry")
        if entry and result.get("pragmatics"):
            payload = dict(entry)
            payload.setdefault("pragmatics", result["pragmatics"])
            return payload
        return entry

    def fetch_cambridge_data(self, word):
        return self.fetch_remote_entry(word)

    def _cloud_lookup_worker(self, word):
        result = fetch_and_cache_word(
            self.words,
            word,
            fetch_entry=self.fetch_remote_entry,
            fetch_suggestions=fetch_datamuse_suggestions,
            fetch_collocations=self.fetch_datamuse_collocations,
        )

        if result.get("found"):
            self.save_data(refresh_ui=False)

            corrected_word = result["word"]
            self.run_on_ui_thread(self.record_recent_search, corrected_word)
            self.run_on_ui_thread(self.refresh_word_of_day)
            if result.get("source") == "translate_fallback":
                message = f"🎉 Đã thêm '{corrected_word}' bằng bản dịch dự phòng."
            else:
                message = f"🎉 Đã nạp thành công '{corrected_word}' từ API!"
            if result.get("corrected"):
                message = f"🔧 Tự sửa '{word}' → '{corrected_word}'. " + message

            self.run_on_ui_thread(self.show_toast, message)
            self.run_on_ui_thread(self.search_var.set, corrected_word)
            self.run_on_ui_thread(self.update_list)
            self.run_on_ui_thread(self._search_youtube_videos, corrected_word)
        else:
            self.after(0, lambda: self.show_toast(f"❌ Không tìm thấy dữ liệu cho '{word}'!", is_error=True))
            self.after(0, self.update_list)

    def render_ac_frame(self, val, entry_widget, frame_widget, on_select_callback):
        normalized_val = normalize_text(val)
        if not normalized_val:
            frame_widget.place_forget()
            self._clear_suggestion_state(entry_widget)
            return

        for child in frame_widget.winfo_children():
            child.destroy()

        local_matches = self.engine.suggestions(normalized_val, limit=5)
        primary = local_matches[0] if local_matches else ""
        self._set_active_suggestion(entry_widget, primary)

        has_items = False
        for word in local_matches:
            meaning = repair_text(self.words.get(word, {}).get("meaning", ""))
            short_meaning = meaning if len(meaning) < 40 else meaning[:37] + "..."
            btn = ctk.CTkButton(
                frame_widget,
                text=f"{word}  -  {short_meaning}",
                font=ui_font(self, 16, "bold"),
                fg_color="transparent",
                text_color="#F8FAFC",
                anchor="w",
                hover_color="#334155",
                command=lambda kw=word: on_select_callback(kw),
            )
            btn.pack(fill="x", padx=10, pady=2)
            has_items = True

        if has_items:
            frame_widget.place(in_=entry_widget, rely=1.0, relx=0.0, relwidth=1.0, y=5)
            frame_widget.lift()
        else:
            frame_widget.place_forget()

        def _fetch_sug():
            try:
                online_words = fetch_datamuse_suggestions(normalized_val, max_results=3)
                if normalize_text(entry_widget.get()) != normalized_val:
                    return

                existing = set(local_matches)
                online_words = [item for item in online_words if item not in existing]
                if not online_words:
                    return

                def _add_online():
                    if normalize_text(entry_widget.get()) != normalized_val:
                        return
                    if not local_matches:
                        self._set_active_suggestion(entry_widget, online_words[0])
                    div = ctk.CTkFrame(frame_widget, height=1, fg_color="#475569")
                    div.pack(fill="x", padx=10, pady=5)
                    for online_word in online_words:
                        btn = ctk.CTkButton(
                            frame_widget,
                            text=f"Gợi ý mạng: {online_word}",
                            font=ui_font(self, 15),
                            fg_color="transparent",
                            text_color="#3B82F6",
                            anchor="w",
                            hover_color="#334155",
                            command=lambda kw=online_word: on_select_callback(kw),
                        )
                        btn.pack(fill="x", padx=10, pady=2)
                    frame_widget.place(in_=entry_widget, rely=1.0, relx=0.0, relwidth=1.0, y=5)
                    frame_widget.lift()

                self.after(0, _add_online)
            except Exception:
                pass

        threading.Thread(target=_fetch_sug, daemon=True).start()

    def on_home_search_enter(self, event):
        val = normalize_text(self.home_search_var.get())
        if val:
            self.record_recent_search(val)
            self.showing_favorites = False
            self.show_screen(self.dict_frame)
            self.search_var.set(val)
            self.update_list()
            self.home_search_var.set("")
            self.home_ac_frame.place_forget()
            self._clear_suggestion_state(self.home_search_entry)

            val_no_space = val.split()[0] if " " in val else val
            if not self.engine.contains(val_no_space):
                self.trigger_cloud_lookup()

    def apply_dict_suggestion(self, word):
        self.record_recent_search(word)
        self.search_var.set(word)
        self.dict_ac_frame.place_forget()
        self._clear_suggestion_state(self.search_entry)
        self.update_list()
        self._search_youtube_videos(word)

    def trigger_cloud_lookup(self):
        term = normalize_text(self.search_var.get())
        if not term:
            return
        self.cloud_btn.pack_forget()
        self._search_youtube_videos(term)

        if self.engine.contains(term):
            self.record_recent_search(term)
            self.show_toast(f"Từ '{term}' đã có trong máy của bạn.", is_error=True)
            return

        self.list_header.configure(text=f"☁️ Đang gọi API để lấy dữ liệu cho '{term}'...")
        threading.Thread(target=self._cloud_lookup_worker, args=(term,), daemon=True).start()

    def toggle_favorite(self, word):
        if toggle_favorite_flag(self.words, word):
            self.save_data()
            self.update_list()
            self.show_toast(f"⭐ Đã thêm '{word}' vào yêu thích.", duration=1800)
        elif word in self.words:
            self.save_data()
            self.update_list()
            self.show_toast(f"⭐ Đã bỏ '{word}' khỏi yêu thích.", duration=1800)

    def delete_word(self, word):
        if delete_word_entry(self.words, word):
            self.selected_words.discard(word)
            self.save_data()
            self.update_list()
            self.show_toast(f"🗑 Đã xóa '{word}'.")

    def delete_selected(self):
        count = delete_word_entries(self.words, self.selected_words)
        self.selected_words.clear()
        self.save_data()
        self.update_list()
        self.show_toast(f"🗑 Đã xóa {count} từ vựng.")

    def favorite_selected(self):
        count = favorite_word_entries(self.words, self.selected_words)
        self.selected_words.clear()
        self.save_data()
        self.update_list()
        self.show_toast(f"⭐ Đã đánh dấu yêu thích cho {count} từ.")

    def add_words(self):
        raw_text = self.input_text.get("0.0", "end").strip()
        if not raw_text or not self.placeholder_cleared:
            return

        self.save_btn.configure(state="disabled", text="⏳ Đang import...")
        parsed_lines = parse_import_lines(raw_text)
        added_count, failed_lines = import_parsed_entries(
            self.words,
            parsed_lines,
            resolver=self.resolve_import_entry,
        )

        if added_count:
            self.save_data()
            self.after(0, self.update_list)

        def update_ui_after_add():
            self.input_text.delete("0.0", "end")
            if failed_lines:
                self.input_text.insert("0.0", "\n".join(failed_lines))
                self.show_toast(f"Đã lưu {added_count} từ. Còn {len(failed_lines)} dòng chưa parse được.", is_error=True)
                self.input_text.configure(text_color="#EF4444")
            else:
                self.show_toast(f"🎉 Đã nạp thành công {added_count} mục từ.")
                self.restore_placeholder(None)
                self.open_dict_all()
            self.save_btn.configure(state="normal", text="SAVE (Ctrl+Enter)")

        self.after(0, update_ui_after_add)

    def next_quiz(self):
        if self.game_mode != "quiz":
            return
        question = build_multiple_choice_question(self.words)
        if not question:
            return

        self.current_answer = question["answer"]
        self.lbl_question.configure(text=question["word"], text_color="#A78BFA")
        self.card_main.configure(border_color="#8B5CF6")

        for index, btn in enumerate(self.ans_buttons):
            btn.configure(
                text=question["options"][index],
                fg_color="#334155",
                state="normal",
                command=lambda ans=question["options"][index], b=btn: self.check_quiz(ans, b),
            )

    def next_scramble(self):
        round_data = build_scramble_round(self.words)
        if not round_data:
            return

        self.scramble_word = round_data["word"]
        self.scramble_meaning = round_data["meaning"]
        self.lbl_question.configure(text=round_data["scrambled"].upper(), text_color="#22D3EE")
        self.card_main.configure(border_color="#06B6D4")

        if hasattr(self, "lbl_hint"):
            self.lbl_hint.configure(text=f"💡 Gợi ý: {self.scramble_meaning}")
        self.lbl_feedback.configure(text="")
        self.type_entry.delete(0, "end")
        self.type_entry.focus()
        self.type_entry.unbind("<Return>")
        self.type_entry.bind("<Return>", lambda e: self.check_scramble())

    def next_reverse(self):
        round_data = build_reverse_round(self.words)
        if not round_data:
            return

        self.current_answer = round_data["answer"]
        self.lbl_question.configure(text=round_data["meaning"], text_color="#F59E0B")
        self.card_main.configure(border_color="#F59E0B")

        for index, btn in enumerate(self.ans_buttons):
            btn.configure(
                text=round_data["options"][index],
                fg_color="#334155",
                state="normal",
                command=lambda ans=round_data["options"][index], b=btn: self.check_reverse(ans),
            )

    def _next_hangman(self):
        round_data = build_hangman_round(self.words)
        if not round_data:
            return

        self.hm_word = round_data["word"]
        self.hm_meaning = round_data["meaning"]
        self.hm_guessed = set()
        self.hm_wrong_count = 0

        self.hm_hint_lbl.configure(text=f"💡 Gợi ý: {self.hm_meaning}")
        self.hm_feedback_lbl.configure(text="")
        self._build_hangman_keyboard()
        self._update_hangman_display()

    def generate_crossword(self, attempts_remaining=12):
        pool = crossword_candidates(self.words)
        if not pool:
            if hasattr(self, "cw_placeholder"):
                self.cw_placeholder.configure(text="Kho hiện tại chưa đủ từ đơn để tạo crossword.")
                self.cw_placeholder.pack(expand=True, pady=40)
            self.show_toast("⚠ Kho không đủ từ đơn để tạo crossword!", is_error=True)
            return

        size = 22
        grid = [["" for _ in range(size)] for _ in range(size)]
        placed = []

        def can_place(word, row, col, direction):
            if direction == "H":
                if row < 0 or row >= size or col < 0 or col + len(word) > size:
                    return False
                for index in range(len(word)):
                    if grid[row][col + index] not in ("", word[index]):
                        return False
                return True

            if col < 0 or col >= size or row < 0 or row + len(word) > size:
                return False
            for index in range(len(word)):
                if grid[row + index][col] not in ("", word[index]):
                    return False
            return True

        def try_place(word, meaning):
            if not placed:
                start_col = (size - len(word)) // 2
                if can_place(word, size // 2, start_col, "H"):
                    for index, char in enumerate(word):
                        grid[size // 2][start_col + index] = char
                    placed.append({"word": word, "r": size // 2, "c": start_col, "d": "H", "meaning": meaning})
                    return True
                return False

            for existing in placed:
                for i, char_1 in enumerate(word):
                    for j, char_2 in enumerate(existing["word"]):
                        if char_1 != char_2:
                            continue
                        new_direction = "V" if existing["d"] == "H" else "H"
                        new_row = existing["r"] - i if new_direction == "V" else existing["r"] + j
                        new_col = existing["c"] + j if new_direction == "V" else existing["c"] - i
                        if can_place(word, new_row, new_col, new_direction):
                            if new_direction == "H":
                                for index, char in enumerate(word):
                                    grid[new_row][new_col + index] = char
                            else:
                                for index, char in enumerate(word):
                                    grid[new_row + index][new_col] = char
                            placed.append({"word": word, "r": new_row, "c": new_col, "d": new_direction, "meaning": meaning})
                            return True
            return False

        for word, meaning in pool:
            if len(placed) >= 8:
                break
            try_place(word, meaning)

        if len(placed) < 4:
            if attempts_remaining > 1:
                self.after(50, lambda: self.generate_crossword(attempts_remaining - 1))
                return
            if hasattr(self, "cw_placeholder"):
                self.cw_placeholder.configure(text="Chưa tạo được crossword phù hợp. Hãy thử lại hoặc thêm vài từ đơn nữa.")
                self.cw_placeholder.pack(expand=True, pady=40)
            self.show_toast("⚠ Chưa tạo được crossword phù hợp từ kho hiện tại.", is_error=True)
            return

        self._render_crossword(placed, size)

    def select_all_visible(self):
        for word in self.visible_words:
            self.selected_words.add(word)
        self.update_list()

    # PATCH MARKER: home dashboard override
    def setup_home_screen(self):
        for child in self.home_frame.winfo_children():
            child.destroy()

        self.home_bg_canvas = DotGrid(self.home_frame)
        self.home_bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.home_main = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        self.home_main.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._build_home_dashboard_header()
        self._build_home_dashboard_search()
        self._build_home_dashboard_nav()
        self._build_home_dashboard_body()

        self.refresh_word_of_day()
        self.refresh_recent_searches()
        self.refresh_daily_challenge_panel()

    def _build_home_dashboard_header(self):
        header = ctk.CTkFrame(self.home_main, fg_color="transparent", height=74)
        header.pack(fill="x", padx=32, pady=(18, 0))
        header.pack_propagate(False)

        logo = ctk.CTkFrame(header, fg_color="transparent")
        logo.pack(side="left")
        title_font = ctk.CTkFont(
            family=getattr(self, "ui_font_family", "Segoe UI"),
            size=42,
            weight="bold",
        )
        build_gradient_text_row(
            logo,
            "Adam Dictionary",
            title_font,
            start_color="#22d3ee",
            end_color="#8b5cf6",
            space_color=DASHBOARD_COLORS["text"],
        )

        self.home_stat_lbl = ctk.CTkLabel(
            header,
            text=f"{len(self.words)} words in your notebook",
            font=ctk.CTkFont(family=getattr(self, "ui_font_family", "Segoe UI"), size=13),
            text_color=DASHBOARD_COLORS["text3"],
            fg_color="transparent",
        )
        self.home_stat_lbl.pack(side="left", padx=16)

        ctk.CTkButton(
            header,
            text="⚙",
            font=getattr(self, "FONT_ICON_LARGE", ctk.CTkFont(size=22)),
            width=44,
            height=44,
            corner_radius=22,
            fg_color=DASHBOARD_COLORS["card"],
            hover_color=DASHBOARD_COLORS["card_border"],
            border_color=DASHBOARD_COLORS["card_border"],
            border_width=1,
            text_color=DASHBOARD_COLORS["text2"],
            command=self._launch_standalone_game,
        ).pack(side="right")

    def _launch_standalone_game(self):
        existing_window = getattr(self, "_game_dodge_window", None)
        if existing_window is not None and existing_window.winfo_exists():
            try:
                existing_window.deiconify()
                existing_window.lift()
                existing_window.focus_force()
                self.show_toast("Game dang mo san.", duration=1500)
                return
            except Exception:
                self._game_dodge_window = None

        try:
            self.show_toast("Launching game...", duration=1800)
            from game_dodge import DodgeGameApp

            self._game_dodge_window = DodgeGameApp(self)
            self._game_dodge_window.transient(self)
            self._game_dodge_window.after(80, self._game_dodge_window.lift)
            self._game_dodge_window.after(120, self._game_dodge_window.focus_force)
        except Exception as exc:
            self.show_toast(f"Khong mo duoc game: {exc}", is_error=True)

    def _build_home_dashboard_search(self):
        wrapper = ctk.CTkFrame(self.home_main, fg_color="transparent")
        wrapper.pack(fill="x", padx=32, pady=(14, 0))

        self.home_search_var = tk.StringVar()
        self.home_search_bar = SearchBar(
            wrapper,
            on_search=self._home_dashboard_search,
            on_key=self._home_dashboard_on_key,
            textvariable=self.home_search_var,
            placeholder_text="Search a word...",
        )
        self.home_search_bar.pack(fill="x")
        self.home_search_entry = self.home_search_bar.entry
        self.home_ghost_var = self.home_search_bar._ghost_var
        self.home_ac_frame = ctk.CTkFrame(
            self.home_main,
            fg_color=UI_PALETTE["glass"],
            corner_radius=18,
            border_width=1,
            border_color=UI_PALETTE["accent_cyan"],
        )
        self.home_search_entry.bind("<Escape>", lambda e: self.home_ac_frame.place_forget())
        self.home_search_entry.bind("<FocusOut>", lambda e: self.after(200, self.home_ac_frame.place_forget()))

    def _build_home_dashboard_nav(self):
        self.home_nav_frame = None

    def _build_home_dashboard_body(self):
        self.home_result_panel = None
        self.home_shortcuts_card = dashboard_glass_frame(self.home_main)
        self.home_shortcuts_card.pack(fill="x", padx=32, pady=(16, 0))
        self._build_home_shortcuts_card(self.home_shortcuts_card)

        columns = ctk.CTkFrame(self.home_main, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=32, pady=(16, 0))
        columns.columnconfigure(0, weight=3)
        columns.columnconfigure(1, weight=2, minsize=360)

        left = ctk.CTkFrame(columns, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        right = ctk.CTkFrame(columns, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        self.word_day_card = WordOfDayCard(left, None, on_open=self.open_word_of_day)
        self.word_day_card.pack(fill="x", pady=(0, 14))

        self.recent_host = ctk.CTkFrame(left, fg_color="transparent")
        self.recent_host.pack(fill="x")

        self.daily_challenge_card = DailyChallengeCard(
            right,
            streak=int(self.daily_state.get("streak", 0)),
            completed=self.daily_state.get("last_completed") == today_key(),
            on_start=self.start_daily_challenge,
        )
        self.daily_challenge_card.pack(fill="x")

    def _build_home_shortcuts_card(self, parent):
        shell = ctk.CTkFrame(parent, fg_color="transparent")
        shell.pack(fill="both", expand=True, padx=16, pady=16)
        for col in range(5):
            shell.grid_columnconfigure(col, weight=1)

        buttons = [
            ("\U0001F4DA", "Notebook", self.open_dict_all),
            ("\u2795", "Add Word", lambda: self.show_screen(self.add_frame)),
            ("\U0001F3AE", "Game", self.start_game),
            ("\U0001F4FA", "Videos", self.open_youtube_videos),
            ("\U0001F4F0", "News", lambda: self.show_screen(self.news_frame)),
        ]

        def invoke_command(callback):
            callback()

        for index, (icon, label, command) in enumerate(buttons):
            tile = ctk.CTkFrame(
                shell,
                fg_color=DASHBOARD_COLORS["card"],
                border_color=DASHBOARD_COLORS["card_border"],
                border_width=1,
                corner_radius=18,
            )
            tile.grid(row=0, column=index, sticky="ew", padx=6, pady=6)
            tile.grid_propagate(False)
            tile.configure(height=112)

            stack = ctk.CTkFrame(tile, fg_color="transparent")
            stack.place(relx=0.5, rely=0.5, anchor="center")

            icon_badge = ctk.CTkFrame(
                stack,
                fg_color="#17203f",
                border_color=DASHBOARD_COLORS["card_border"],
                border_width=1,
                corner_radius=999,
                width=66,
                height=66,
            )
            icon_badge.pack(anchor="center", pady=(0, 6))
            icon_badge.pack_propagate(False)

            icon_label = ctk.CTkLabel(
                icon_badge,
                text=icon,
                font=ctk.CTkFont(
                    family=getattr(self, "icon_font_family", "Segoe UI Emoji"),
                    size=40,
                    weight="bold",
                ),
                text_color=DASHBOARD_COLORS["text"],
                fg_color="transparent",
            )
            icon_label.place(relx=0.5, rely=0.5, anchor="center")

            text_label = ctk.CTkLabel(
                stack,
                text=label,
                font=ctk.CTkFont(family=getattr(self, "ui_font_family", "Segoe UI"), size=17, weight="bold"),
                text_color=DASHBOARD_COLORS["text2"],
                fg_color="transparent",
            )
            text_label.pack(anchor="center")

            hover_accent = DASHBOARD_COLORS.get("cyan", DASHBOARD_COLORS["text"])
            bind_glow_hover(tile, DASHBOARD_COLORS["card_border"], hover_accent)
            bind_glow_hover(icon_badge, DASHBOARD_COLORS["card_border"], hover_accent)

            for widget in (tile, stack, icon_badge, icon_label, text_label):
                widget.bind("<Button-1>", lambda _event, callback=command: invoke_command(callback))

    def _home_dashboard_payload(self, word, entry):
        payload = dict(entry or {})
        tags = list(payload.get("tags") or [])
        level = repair_text(payload.get("level", "")).strip()
        if level and level not in tags:
            tags.insert(0, level)
        return {
            "word": word,
            "pronunciation": repair_text(
                payload.get("pronunciation")
                or payload.get("phonetic")
                or payload.get("ipa_uk")
                or payload.get("ipa_us")
                or ""
            ),
            "pos": repair_text(payload.get("pos") or payload.get("part_of_speech") or ""),
            "definition": repair_text(payload.get("meaning") or payload.get("eng_meaning") or ""),
            "example": repair_text(payload.get("example") or payload.get("eng_meaning") or payload.get("pragmatics") or ""),
            "tags": tags,
        }

    def _home_resolve_local_entry(self, query):
        normalized = normalize_text(query)
        if not normalized:
            return "", None
        for word, entry in self.words.items():
            if normalize_text(word) == normalized:
                return word, entry
        entry = self.engine.exact_lookup(normalized)
        if entry is None:
            return normalized, None
        for word, candidate in self.words.items():
            if candidate is entry:
                return word, candidate
        return normalized, entry

    def _show_home_result(self, word, entry):
        if getattr(self, "home_result_panel", None):
            self.home_result_panel.show(self._home_dashboard_payload(word, entry))

    def refresh_word_of_day(self):
        if not hasattr(self, "word_day_card"):
            return
        selected = pick_word_of_day(self.words)
        if not selected:
            self.current_word_of_day = ""
            self.word_day_card.refresh(None)
            return
        word, entry = selected
        self.current_word_of_day = word
        self.word_day_card.refresh(self._home_dashboard_payload(word, entry))

    def open_word_of_day(self):
        if not getattr(self, "current_word_of_day", ""):
            return
        self.record_recent_search(self.current_word_of_day)
        self.showing_favorites = False
        self.show_screen(self.dict_frame)
        self.search_var.set(self.current_word_of_day)
        self.update_list()
        self._search_youtube_videos(self.current_word_of_day)

    def refresh_recent_searches(self):
        if not hasattr(self, "recent_host"):
            return
        for child in self.recent_host.winfo_children():
            child.destroy()
        widget = RecentSearches(self.recent_host, self.recent_searches[:6], on_click=self.open_recent_search)
        widget.pack(fill="x")
        if not self.recent_searches:
            ctk.CTkLabel(
                self.recent_host,
                text="No recent lookups yet.",
                font=ctk.CTkFont(family=getattr(self, "ui_font_family", "Segoe UI"), size=12),
                text_color=DASHBOARD_COLORS["text3"],
                fg_color="transparent",
            ).pack(anchor="w", pady=(6, 0))

    def open_recent_search(self, word):
        self.home_search_var.set(word)
        self.home_search_bar.focus()
        self._route_home_query_to_dictionary(word)

    def refresh_daily_challenge_panel(self):
        if not hasattr(self, "daily_challenge_card"):
            return
        streak = int(self.daily_state.get("streak", 0))
        completed_today = self.daily_state.get("last_completed") == today_key()
        self.daily_completed_today = completed_today
        self.daily_challenge_card.refresh(streak, completed_today, self.start_daily_challenge)

    def debounce_home_search(self):
        if self.home_search_timer:
            self.after_cancel(self.home_search_timer)
        self.home_search_timer = self.after(120, self._debounce_home_search_invoke)

    def _home_dashboard_on_key(self, event=None):
        self.debounce_home_search()

    def _home_fetch_ghost_suggestion(self, typed):
        entry = self.fetch_remote_entry(typed)
        if not entry:
            return
        suggestion = normalize_text(entry.get("word") or typed)

        def _apply():
            if normalize_text(self.home_search_var.get()) != typed:
                return
            if suggestion:
                self._set_active_suggestion(self.home_search_entry, suggestion)

        self.after(0, _apply)

    def _debounce_home_search_invoke(self):
        typed = normalize_text(self.home_search_var.get())
        if not typed:
            self._clear_suggestion_state(self.home_search_entry)
            if hasattr(self, "home_search_bar"):
                self.home_search_bar.clear_ghost()
            if getattr(self, "home_ac_frame", None):
                self.home_ac_frame.place_forget()
            return

        if getattr(self, "home_ac_frame", None):
            self.render_ac_frame(typed, self.home_search_entry, self.home_ac_frame, self.select_home_suggestion)

    def apply_home_suggestion(self, word):
        self.home_search_var.set(word)
        self.home_search_entry.icursor(tk.END)
        if hasattr(self, "home_search_bar"):
            self.home_search_bar.clear_ghost()
        self._clear_suggestion_state(self.home_search_entry)

    def select_home_suggestion(self, word):
        self.apply_home_suggestion(word)
        if getattr(self, "home_ac_frame", None):
            self.home_ac_frame.place_forget()
        self._route_home_query_to_dictionary(word)

    def _home_dashboard_search(self, query):
        self._route_home_query_to_dictionary(query)

    def _route_home_query_to_dictionary(self, query):
        query = normalize_text(query)
        if not query:
            return

        if hasattr(self, "home_search_bar"):
            self.home_search_bar.clear_ghost()
        self._clear_suggestion_state(self.home_search_entry)
        if getattr(self, "home_ac_frame", None):
            self.home_ac_frame.place_forget()
        if getattr(self, "home_result_panel", None):
            self.home_result_panel.hide()

        self.record_recent_search(query)
        self.showing_favorites = False
        self.show_screen(self.dict_frame)
        self.search_var.set(query)
        self.update_list()
        self._search_youtube_videos(query)
        self.home_search_var.set("")

        query_head = query.split()[0] if " " in query else query
        if not self.engine.contains(query_head):
            self.trigger_cloud_lookup()

    def _home_lookup_worker(self, word):
        result = fetch_and_cache_word(
            self.words,
            word,
            fetch_entry=self.fetch_remote_entry,
            fetch_suggestions=fetch_datamuse_suggestions,
            fetch_collocations=self.fetch_datamuse_collocations,
        )
        self.after(0, lambda: self._finish_home_lookup(word, result))

    def _finish_home_lookup(self, original_word, result):
        if not result.get("found"):
            if getattr(self, "home_result_panel", None):
                self.home_result_panel.show_not_found(original_word)
            self.show_toast(f"Không tìm thấy dữ liệu cho '{original_word}'!", is_error=True)
            return

        self.save_data()
        resolved_word = result.get("word", original_word)
        word, entry = self._home_resolve_local_entry(resolved_word)
        self.home_search_var.set(word or resolved_word)
        self.record_recent_search(word or resolved_word)
        if entry:
            self._show_home_result(word, entry)
        else:
            if getattr(self, "home_result_panel", None):
                self.home_result_panel.show_not_found(resolved_word)
        if hasattr(self, "home_stat_lbl"):
            self.home_stat_lbl.configure(text=f"{len(self.words)} words in your notebook")

    def on_home_search_enter(self, event=None):
        self._route_home_query_to_dictionary(self.home_search_var.get())
