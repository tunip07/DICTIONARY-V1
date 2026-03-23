from __future__ import annotations

import io
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

import customtkinter as ctk
try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency fallback
    Image = None


CARD_BG = "#0d1235"
BORDER = "#1e2a5e"
BORDER_HOVER = "#06b6d4"
TITLE_TEXT = "#f1f5f9"
CHANNEL_TEXT = "#94a3b8"
WATCH_RED = "#ef4444"
LOADING_TEXT = "#0e7490"
MUTED_TEXT = "#64748b"
PANEL_BG = "#10172b"


class YouTubeApiError(Exception):
    pass


class YouTubeQuotaError(YouTubeApiError):
    pass


class YouTubeInvalidKeyError(YouTubeApiError):
    pass


class YouTubeNetworkError(YouTubeApiError):
    pass


class YouTubeTimeoutError(YouTubeApiError):
    pass


def _parse_iso8601_duration(value: str) -> str:
    if not value:
        return ""
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return ""
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def load_thumbnail(url: str) -> Image.Image | None:
    if Image is None:
        return None
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return Image.open(io.BytesIO(response.read())).resize((240, 135))
    except Exception:
        return None


def fetch_youtube(word: str, api_key: str, max_results: int = 6) -> list[dict]:
    """
    Search YouTube for videos related to query.
    Returns list of video dicts.
    ALWAYS call from background thread.
    """
    search_query = f'"{word}" meaning in english'
    params = urllib.parse.urlencode(
        {
            "part": "snippet",
            "q": search_query,
            "type": "video",
            "maxResults": max_results,
            "key": api_key,
            "relevanceLanguage": "en",
            "videoEmbeddable": "true",
        }
    )
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"

    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        if exc.code == 403:
            raise YouTubeQuotaError("YouTube quota reached for today") from exc
        if exc.code == 400:
            raise YouTubeInvalidKeyError("Invalid API key in config.json") from exc
        raise YouTubeApiError(body or "Could not connect to YouTube") from exc
    except TimeoutError as exc:
        raise YouTubeTimeoutError("YouTube is taking too long, try again") from exc
    except Exception as exc:
        raise YouTubeNetworkError("Could not connect to YouTube") from exc

    items = data.get("items", [])
    videos = []
    video_ids = []
    for item in items:
        snippet = item.get("snippet", {})
        video_id = item.get("id", {}).get("videoId", "")
        if not video_id:
            continue
        video_ids.append(video_id)
        videos.append(
            {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "description": snippet.get("description", "")[:80],
                "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "duration": "",
            }
        )

    if not video_ids:
        return []

    details_params = urllib.parse.urlencode(
        {
            "part": "contentDetails",
            "id": ",".join(video_ids),
            "key": api_key,
        }
    )
    details_url = f"https://www.googleapis.com/youtube/v3/videos?{details_params}"
    try:
        with urllib.request.urlopen(details_url, timeout=5) as response:
            details = json.loads(response.read())
    except Exception:
        details = {"items": []}

    durations = {}
    for item in details.get("items", []):
        durations[item.get("id", "")] = _parse_iso8601_duration(item.get("contentDetails", {}).get("duration", ""))

    for video in videos:
        video["duration"] = durations.get(video["video_id"], "")
    return videos


class YouTubePanel(ctk.CTkFrame):
    def __init__(self, parent, api_key: str):
        super().__init__(
            parent,
            fg_color=CARD_BG,
            border_color=BORDER,
            border_width=1,
            corner_radius=16,
        )
        self.api_key = api_key or ""
        self._thumbnail_cache: dict[str, ctk.CTkImage] = {}
        self._last_query = ""
        self._title_font = ctk.CTkFont(size=10, weight="bold")
        self._body_font = ctk.CTkFont(size=13, weight="bold")
        self._small_font = ctk.CTkFont(size=11)
        self._action_font = ctk.CTkFont(size=12, weight="bold")

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(
            header,
            text="▶  RELATED VIDEOS ON YOUTUBE",
            font=self._title_font,
            text_color=CHANNEL_TEXT,
            fg_color="transparent",
        ).pack(side="left")

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self._render_setup_if_needed()

    def clear(self) -> None:
        self._last_query = ""
        self._render_message("Search a word to load related videos.")

    def search(self, query: str) -> None:
        query = (query or "").strip()
        if not query:
            self.clear()
            return
        if query == self._last_query:
            return
        self._last_query = query
        if not self.api_key:
            self._render_setup_if_needed()
            return
        self._render_message("Loading YouTube results...", color=LOADING_TEXT)
        threading.Thread(target=self._fetch_async, args=(query,), daemon=True).start()

    def _fetch_async(self, query: str) -> None:
        try:
            videos = fetch_youtube(query, self.api_key, max_results=6)
            self.after(0, self._render_results, videos)
        except YouTubeQuotaError:
            self.after(0, self._render_message, "YouTube quota reached for today", WATCH_RED)
        except YouTubeInvalidKeyError:
            self.after(0, self._render_message, "Invalid API key in config.json", WATCH_RED)
        except YouTubeTimeoutError:
            self.after(0, self._render_message, "YouTube is taking too long, try again", WATCH_RED)
        except YouTubeNetworkError:
            self.after(0, self._render_message, "Could not connect to YouTube", WATCH_RED)
        except Exception:
            self.after(0, self._render_message, "No videos found", MUTED_TEXT)

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def _render_setup_if_needed(self) -> None:
        if self.api_key:
            self._render_message("Search a word to load related videos.")
            return
        self._clear_content()
        card = ctk.CTkFrame(
            self.content,
            fg_color=PANEL_BG,
            border_color=BORDER,
            border_width=1,
            corner_radius=12,
        )
        card.pack(fill="x")
        ctk.CTkLabel(
            card,
            text="Add your free YouTube API key to config.json\nto see related vocabulary videos here.",
            font=self._body_font,
            text_color=TITLE_TEXT,
            justify="left",
            anchor="w",
            fg_color="transparent",
        ).pack(fill="x", padx=18, pady=(18, 10))
        ctk.CTkButton(
            card,
            text="Get Free API Key →",
            height=38,
            corner_radius=10,
            fg_color=WATCH_RED,
            hover_color="#dc2626",
            text_color=TITLE_TEXT,
            font=self._action_font,
            command=lambda: webbrowser.open("https://console.cloud.google.com"),
        ).pack(anchor="w", padx=18, pady=(0, 18))

    def _render_message(self, message: str, color: str = MUTED_TEXT) -> None:
        self._clear_content()
        ctk.CTkLabel(
            self.content,
            text=message,
            font=self._body_font,
            text_color=color,
            fg_color="transparent",
            anchor="w",
            justify="left",
        ).pack(anchor="w", pady=12)

    def _render_results(self, videos: list[dict]) -> None:
        self._clear_content()
        if not videos:
            self._render_message("No videos found")
            return

        scroll = ctk.CTkScrollableFrame(
            self.content,
            fg_color="transparent",
            corner_radius=0,
            height=420,
        )
        scroll.pack(fill="both", expand=True, anchor="n")

        limited_videos = videos[:6]
        for start in range(0, len(limited_videos), 2):
            row_wrap = ctk.CTkFrame(scroll, fg_color="transparent")
            row_wrap.pack(fill="x", pady=(0, 10), anchor="n")
            row_wrap.grid_columnconfigure(0, weight=1)
            row_wrap.grid_columnconfigure(1, weight=1)

            row_videos = limited_videos[start:start + 2]
            for column, video in enumerate(row_videos):
                card = self._create_video_card(row_wrap, video)
                card.grid(row=0, column=column, sticky="new", padx=8)

        try:
            scroll._parent_canvas.yview_moveto(0)
        except Exception:
            pass

    def _create_video_card(self, parent, video: dict):
        card = ctk.CTkFrame(
            parent,
            fg_color=CARD_BG,
            border_color=BORDER,
            border_width=1,
            corner_radius=12,
        )
        card.grid_columnconfigure(1, weight=1)

        thumb_holder = ctk.CTkFrame(
            card,
            width=240,
            height=135,
            fg_color="#2b334f",
            corner_radius=10,
        )
        thumb_holder.grid(row=0, column=0, rowspan=4, padx=12, pady=12, sticky="n")
        thumb_holder.grid_propagate(False)
        thumb_label = ctk.CTkLabel(thumb_holder, text="Thumbnail", text_color=MUTED_TEXT, fg_color="transparent")
        thumb_label.place(relx=0.5, rely=0.5, anchor="center")

        title_label = ctk.CTkLabel(
            card,
            text=video.get("title", ""),
            font=self._body_font,
            text_color=TITLE_TEXT,
            justify="left",
            wraplength=240,
            anchor="w",
            fg_color="transparent",
        )
        title_label.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(12, 4))

        meta_text = video.get("channel", "")
        if video.get("duration"):
            meta_text = f"{meta_text}  •  {video['duration']}"
        meta_label = ctk.CTkLabel(
            card,
            text=meta_text,
            font=self._small_font,
            text_color=CHANNEL_TEXT,
            anchor="w",
            fg_color="transparent",
        )
        meta_label.grid(row=1, column=1, sticky="ew", padx=(0, 12))

        desc_label = ctk.CTkLabel(
            card,
            text=video.get("description", ""),
            font=self._small_font,
            text_color=CHANNEL_TEXT,
            justify="left",
            wraplength=240,
            anchor="w",
            fg_color="transparent",
        )
        desc_label.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=(6, 8))

        watch_label = ctk.CTkLabel(
            card,
            text="▶ Watch on YouTube",
            font=self._action_font,
            text_color=WATCH_RED,
            anchor="w",
            fg_color="transparent",
        )
        watch_label.grid(row=3, column=1, sticky="w", padx=(0, 12), pady=(0, 12))

        self._bind_video_card(card, video["url"], thumb_holder, thumb_label, title_label, meta_label, desc_label, watch_label)

        cached = self._thumbnail_cache.get(video["video_id"])
        if cached:
            thumb_label.configure(image=cached, text="")
            thumb_label.image = cached
        else:
            threading.Thread(
                target=self._load_thumbnail_async,
                args=(video["video_id"], video.get("thumbnail", ""), thumb_label),
                daemon=True,
            ).start()
        return card

    def _bind_video_card(self, card, url: str, *widgets) -> None:
        def _enter(_event=None):
            card.configure(border_color=BORDER_HOVER)

        def _leave(_event=None):
            card.configure(border_color=BORDER)

        def _open(_event=None):
            webbrowser.open(url)

        for widget in (card, *widgets):
            widget.bind("<Enter>", _enter)
            widget.bind("<Leave>", _leave)
            widget.bind("<Button-1>", _open)

    def _load_thumbnail_async(self, video_id: str, url: str, thumb_label) -> None:
        image = load_thumbnail(url)
        if image is None:
            return
        ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(240, 135))
        self._thumbnail_cache[video_id] = ctk_image

        def _apply():
            try:
                thumb_label.configure(image=ctk_image, text="")
                thumb_label.image = ctk_image
            except Exception:
                pass

        self.after(0, _apply)

    def _open_video(self, video_id: str) -> None:
        if video_id:
            webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")
