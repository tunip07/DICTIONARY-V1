from __future__ import annotations

import tkinter as tk

import customtkinter as ctk


C = {
    "bg": "#04051a",
    "bg2": "#080c24",
    "card": "#0d1235",
    "card_border": "#1e2a5e",
    "cyan": "#06b6d4",
    "cyan_dim": "#0e7490",
    "purple": "#7c3aed",
    "amber": "#f59e0b",
    "green": "#22c55e",
    "red": "#ef4444",
    "text": "#f1f5f9",
    "text2": "#94a3b8",
    "text3": "#475569",
    "dot": "#1e2a4a",
    "input_bg": "#0a0f2e",
    "input_border": "#1e3a5f",
    "ghost": "#334155",
}


def _font(size: int, weight: str = "normal", family: str | None = None) -> ctk.CTkFont:
    candidates = [family] if family else []
    candidates += ["Space Grotesk", "Inter", "Segoe UI", "Helvetica Neue", "Arial"]
    if size <= 12:
        size += 2
    elif size <= 18:
        size += 3
    else:
        size += 4
    return ctk.CTkFont(family=candidates[0], size=size, weight=weight)


class DotGrid(tk.Canvas):
    def __init__(self, parent: tk.Widget, **kwargs):
        super().__init__(parent, bg=C["bg"], highlightthickness=0, **kwargs)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, event: tk.Event | None = None) -> None:
        self.delete("bg")
        width = self.winfo_width()
        height = self.winfo_height()
        if width < 2 or height < 2:
            return

        self.create_rectangle(0, 0, width, height, fill=C["bg"], outline="", tags="bg")
        center_x = width // 2
        center_y = max(0, height // 3)
        for radius, color, border in (
            (520, "#101847", 34),
            (390, "#15124a", 26),
            (280, "#18153f", 18),
        ):
            self.create_oval(
                center_x - radius,
                center_y - radius * 0.8,
                center_x + radius,
                center_y + radius * 0.8,
                fill="",
                outline=color,
                width=border,
                tags="bg",
            )

        for x in range(0, width, 40):
            for y in range(0, height, 40):
                self.create_rectangle(x, y, x + 2, y + 2, fill=C["dot"], outline="", tags="bg")


def glass_frame(parent: tk.Widget, border_color: str = C["card_border"], fg_color: str = C["card"]) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        fg_color=fg_color,
        border_color=border_color,
        border_width=1,
        corner_radius=16,
    )


class SearchBar(ctk.CTkFrame):
    def __init__(
        self,
        parent: tk.Widget,
        on_search,
        on_key,
        textvariable: tk.StringVar | None = None,
        placeholder_text: str = "Search a word...",
        **kwargs,
    ):
        super().__init__(
            parent,
            fg_color=C["input_bg"],
            border_color=C["input_border"],
            border_width=1,
            corner_radius=14,
            **kwargs,
        )
        self._suggestion = ""
        self._ghost_var = tk.StringVar(value="")

        ctk.CTkLabel(
            self,
            text="⌕",
            font=_font(22, "bold"),
            text_color=C["text2"],
            fg_color="transparent",
            width=36,
        ).pack(side="left", padx=(14, 0))

        self._ghost = ctk.CTkLabel(
            self,
            textvariable=self._ghost_var,
            font=_font(16),
            text_color=C["ghost"],
            fg_color="transparent",
            anchor="w",
        )
        self._ghost.pack(side="left", fill="x", expand=True)

        self.entry = ctk.CTkEntry(
            self,
            textvariable=textvariable,
            font=_font(16),
            fg_color="transparent",
            border_width=0,
            text_color=C["text"],
            placeholder_text=placeholder_text,
            placeholder_text_color=C["text3"],
        )
        self.entry.pack(side="left", fill="x", expand=True, pady=10)
        self.entry.lift()
        self.entry.bind("<KeyRelease>", on_key)
        self.entry.bind("<Return>", lambda e: on_search(self.entry.get()))
        self.entry.bind("<Tab>", self._on_tab)

        self._btn = ctk.CTkButton(
            self,
            text="Search",
            font=_font(13, "bold"),
            width=90,
            height=36,
            corner_radius=10,
            fg_color=C["cyan_dim"],
            hover_color=C["cyan"],
            text_color=C["text"],
            command=lambda: on_search(self.entry.get()),
        )
        self._btn.pack(side="right", padx=10, pady=8)

    def show_ghost(self, typed: str, suggestion: str) -> None:
        self._suggestion = suggestion
        if suggestion and suggestion.lower().startswith(typed.lower()) and typed:
            self._ghost_var.set(" " * len(typed) + suggestion[len(typed):])
        else:
            self._ghost_var.set("")

    def clear_ghost(self) -> None:
        self._ghost_var.set("")
        self._suggestion = ""

    def _on_tab(self, event: tk.Event) -> str:
        if self._suggestion:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self._suggestion)
            self.clear_ghost()
        return "break"

    def focus(self) -> None:
        self.entry.focus_set()


class NavButton(ctk.CTkButton):
    def __init__(self, parent, icon: str, label: str, command=None, **kwargs):
        super().__init__(
            parent,
            text=f"{icon}  {label}",
            font=_font(12, "bold"),
            height=52,
            corner_radius=14,
            fg_color=C["card"],
            hover_color=C["card_border"],
            border_color=C["card_border"],
            border_width=1,
            text_color=C["text2"],
            command=command,
            **kwargs,
        )


class WordOfDayCard(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget, entry: dict | None, on_open=None, **kwargs):
        super().__init__(
            parent,
            fg_color=C["card"],
            border_color=C["card_border"],
            border_width=1,
            corner_radius=16,
            **kwargs,
        )
        self._on_open = on_open
        self.refresh(entry)

    def refresh(self, entry: dict | None) -> None:
        for child in self.winfo_children():
            child.destroy()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 0))

        ctk.CTkLabel(
            header,
            text="★  WORD OF THE DAY",
            font=_font(10, "bold"),
            text_color=C["amber"],
            fg_color="transparent",
        ).pack(side="left")

        if entry:
            tags = entry.get("tags", [])
            if tags:
                ctk.CTkLabel(
                    header,
                    text=tags[0].upper(),
                    font=_font(10, "bold"),
                    text_color=C["cyan"],
                    fg_color=C["input_bg"],
                    corner_radius=6,
                    width=50,
                    height=22,
                ).pack(side="right")

        if not entry:
            ctk.CTkLabel(
                self,
                text="Add words to see Word of the Day",
                font=_font(13),
                text_color=C["text3"],
                fg_color="transparent",
            ).pack(pady=20)
            return

        ctk.CTkLabel(
            self,
            text=entry.get("word", ""),
            font=_font(36, "bold"),
            text_color=C["text"],
            fg_color="transparent",
            anchor="w",
        ).pack(fill="x", padx=20, pady=(10, 0))

        ctk.CTkLabel(
            self,
            text="  •  ".join([part for part in (entry.get("pos", ""), entry.get("pronunciation", "")) if part]),
            font=_font(12),
            text_color=C["text2"],
            fg_color="transparent",
            anchor="w",
        ).pack(fill="x", padx=20)

        ctk.CTkFrame(self, height=1, fg_color=C["card_border"]).pack(fill="x", padx=20, pady=12)
        ctk.CTkLabel(
            self,
            text=entry.get("definition", ""),
            font=_font(14),
            text_color=C["text2"],
            fg_color="transparent",
            wraplength=360,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=20, pady=(0, 16))

        if self._on_open:
            ctk.CTkButton(
                self,
                text="Open in notebook",
                font=_font(12, "bold"),
                height=34,
                corner_radius=10,
                fg_color=C["input_bg"],
                hover_color=C["card_border"],
                border_width=1,
                border_color=C["card_border"],
                text_color=C["text"],
                command=self._on_open,
            ).pack(anchor="w", padx=20, pady=(0, 18))


class DailyChallengeCard(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget, streak: int, completed: bool, on_start, **kwargs):
        super().__init__(
            parent,
            fg_color=C["card"],
            border_color=C["card_border"],
            border_width=1,
            corner_radius=16,
            **kwargs,
        )
        self.refresh(streak, completed, on_start)

    def refresh(self, streak: int, completed: bool, on_start) -> None:
        for child in self.winfo_children():
            child.destroy()

        ctk.CTkLabel(
            self,
            text="⚡  DAILY CHALLENGE",
            font=_font(10, "bold"),
            text_color=C["purple"],
            fg_color="transparent",
            anchor="w",
        ).pack(fill="x", padx=20, pady=(18, 6))

        ctk.CTkLabel(
            self,
            text="Complete 3 quiz questions\nto keep your streak alive.",
            font=_font(13),
            text_color=C["text2"],
            fg_color="transparent",
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=20)

        streak_color = C["green"] if completed else C["amber"]
        streak_text = (
            f"✓ Completed today  •  Streak {streak} days"
            if completed
            else f"Not completed today  •  Streak {streak} days"
        )
        ctk.CTkLabel(
            self,
            text=streak_text,
            font=_font(11, "bold"),
            text_color=streak_color,
            fg_color="transparent",
            anchor="w",
        ).pack(fill="x", padx=20, pady=(8, 0))

        progress = ctk.CTkProgressBar(
            self,
            progress_color=C["cyan"],
            fg_color=C["input_bg"],
            height=6,
            corner_radius=3,
        )
        progress.pack(fill="x", padx=20, pady=(10, 0))
        progress.set(1.0 if completed else 0.0)

        ctk.CTkButton(
            self,
            text="Start Challenge →",
            font=_font(13, "bold"),
            height=38,
            corner_radius=10,
            fg_color=C["purple"],
            hover_color="#6d28d9",
            text_color=C["text"],
            command=on_start,
        ).pack(fill="x", padx=20, pady=(14, 18))


class DailyChallengeCard(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget, streak: int, completed: bool, on_start, **kwargs):
        super().__init__(
            parent,
            fg_color=C["card"],
            border_color=C["card_border"],
            border_width=1,
            corner_radius=16,
            **kwargs,
        )
        self.refresh(streak, completed, on_start)

    def refresh(self, streak: int, completed: bool, on_start) -> None:
        for child in self.winfo_children():
            child.destroy()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 8))

        ctk.CTkLabel(
            header,
            text="DAILY CHALLENGE",
            font=_font(10, "bold"),
            text_color=C["purple"],
            fg_color="transparent",
            anchor="w",
        ).pack(side="left")

        status_chip = ctk.CTkLabel(
            header,
            text="DONE" if completed else "LIVE",
            font=_font(9, "bold"),
            text_color=C["green"] if completed else C["cyan"],
            fg_color=C["input_bg"],
            corner_radius=8,
            width=60,
            height=24,
        )
        status_chip.pack(side="right")

        ctk.CTkLabel(
            self,
            text="Complete 3 quiz questions to keep your learning streak alive.",
            font=_font(11),
            text_color=C["text2"],
            fg_color="transparent",
            justify="left",
            anchor="w",
            wraplength=300,
        ).pack(fill="x", padx=20)

        streak_color = C["green"] if completed else C["amber"]
        streak_text = (
            f"Completed today • {streak}-day streak"
            if completed
            else f"Not completed today • {streak}-day streak"
        )
        ctk.CTkLabel(
            self,
            text=streak_text,
            font=_font(10, "bold"),
            text_color=streak_color,
            fg_color="transparent",
            anchor="w",
            wraplength=300,
        ).pack(fill="x", padx=20, pady=(10, 0))

        progress_wrap = ctk.CTkFrame(self, fg_color="transparent")
        progress_wrap.pack(fill="x", padx=20, pady=(12, 0))

        progress_track = ctk.CTkFrame(
            progress_wrap,
            fg_color=C["input_bg"],
            corner_radius=6,
            height=10,
        )
        progress_track.pack(fill="x")
        progress_track.pack_propagate(False)

        progress_ratio = 1.0 if completed else 0.0
        if progress_ratio > 0:
            progress_fill = ctk.CTkFrame(
                progress_track,
                fg_color=C["cyan"],
                corner_radius=6,
                height=10,
            )
            progress_fill.place(relx=0, rely=0, relheight=1, relwidth=progress_ratio)

        ctk.CTkButton(
            self,
            text="Start Daily Challenge",
            font=_font(11, "bold"),
            height=42,
            corner_radius=12,
            fg_color=C["purple"],
            hover_color="#6d28d9",
            text_color=C["text"],
            command=on_start,
        ).pack(fill="x", padx=20, pady=(16, 18))


class RecentSearches(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget, searches: list[str], on_click, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.refresh(searches, on_click)

    def refresh(self, searches: list[str], on_click) -> None:
        for child in self.winfo_children():
            child.destroy()

        ctk.CTkLabel(
            self,
            text="RECENT SEARCHES",
            font=_font(10, "bold"),
            text_color=C["text3"],
            fg_color="transparent",
        ).pack(anchor="w", pady=(0, 8))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")

        for word in searches[-6:]:
            ctk.CTkButton(
                row,
                text=word,
                font=_font(12),
                height=32,
                corner_radius=20,
                fg_color=C["card"],
                hover_color=C["card_border"],
                border_color=C["card_border"],
                border_width=1,
                text_color=C["text2"],
                command=lambda value=word: on_click(value),
            ).pack(side="left", padx=(0, 8), pady=2)


class ResultPanel(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget, **kwargs):
        super().__init__(
            parent,
            fg_color=C["card"],
            border_color=C["cyan_dim"],
            border_width=1,
            corner_radius=16,
            **kwargs,
        )
        self._empty_label = ctk.CTkLabel(
            self,
            text="",
            font=_font(14),
            text_color=C["text2"],
            fg_color="transparent",
        )
        self._empty_label.pack(pady=20)

    def show(self, entry: dict) -> None:
        for child in self.winfo_children():
            child.destroy()

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(20, 4))

        ctk.CTkLabel(
            top,
            text=entry.get("word", ""),
            font=_font(34, "bold"),
            text_color=C["text"],
            fg_color="transparent",
        ).pack(side="left")

        if entry.get("pronunciation"):
            ctk.CTkLabel(
                top,
                text=entry["pronunciation"],
                font=_font(16),
                text_color=C["cyan"],
                fg_color="transparent",
            ).pack(side="left", padx=14)

        if entry.get("pos"):
            ctk.CTkLabel(
                top,
                text=entry["pos"],
                font=_font(11, "bold"),
                text_color=C["text3"],
                fg_color=C["input_bg"],
                corner_radius=6,
                width=60,
                height=22,
            ).pack(side="right")

        ctk.CTkFrame(self, height=1, fg_color=C["card_border"]).pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(
            self,
            text=entry.get("definition", ""),
            font=_font(16),
            text_color=C["text"],
            fg_color="transparent",
            wraplength=720,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=24, pady=(0, 8))

        if entry.get("example"):
            ctk.CTkLabel(
                self,
                text=f"\"{entry['example']}\"",
                font=_font(13),
                text_color=C["text2"],
                fg_color="transparent",
                wraplength=720,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=24, pady=(0, 18))

    def show_not_found(self, word: str) -> None:
        for child in self.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self,
            text=f"No results for \"{word}\"",
            font=_font(15),
            text_color=C["text3"],
            fg_color="transparent",
        ).pack(pady=24)

    def show_fetching(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self,
            text="Fetching from dictionary...",
            font=_font(14),
            text_color=C["cyan_dim"],
            fg_color="transparent",
        ).pack(pady=24)

    def hide(self) -> None:
        for child in self.winfo_children():
            child.destroy()
