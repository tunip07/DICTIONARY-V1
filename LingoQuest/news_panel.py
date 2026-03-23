from __future__ import annotations

import html
import io
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET

import customtkinter as ctk
from ui import build_gradient_text_row

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except Exception:  # pragma: no cover - optional dependency fallback
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageOps = None

try:
    from googlenewsdecoder import gnewsdecoder
except Exception:  # pragma: no cover - optional dependency fallback
    gnewsdecoder = None


CARD_BG = "#0d1235"
BORDER = "#1e2a5e"
BORDER_HOVER = "#06b6d4"
TITLE_TEXT = "#f1f5f9"
CHANNEL_TEXT = "#94a3b8"
WATCH_RED = "#ef4444"
LOADING_TEXT = "#0e7490"
MUTED_TEXT = "#64748b"
PANEL_BG = "#10172b"
PLACEHOLDER_A = "#12214d"
PLACEHOLDER_B = "#1f2a69"
PLACEHOLDER_C = "#0ea5e9"


class NewsPanelError(Exception):
    pass


class NewsTimeoutError(NewsPanelError):
    pass


class NewsNetworkError(NewsPanelError):
    pass


def _clean_html_text(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _strip_source_from_title(title: str, source: str) -> str:
    title = (title or "").strip()
    if source and title.endswith(f" - {source}"):
        return title[: -(len(source) + 3)].strip()
    return title


def fetch_google_news(query: str, max_results: int = 6) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "hl": "en-US",
            "gl": "US",
            "ceid": "US:en",
        }
    )
    url = f"https://news.google.com/rss/search?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            xml_data = response.read().decode("utf-8", errors="ignore")
    except TimeoutError as exc:
        raise NewsTimeoutError("Google News is taking too long, try again") from exc
    except urllib.error.URLError as exc:
        raise NewsNetworkError("Could not connect to Google News") from exc
    except Exception as exc:
        raise NewsNetworkError("Could not connect to Google News") from exc

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        raise NewsPanelError("Could not read Google News results") from exc

    articles: list[dict] = []
    for item in root.findall(".//item"):
        title_text = (item.findtext("title") or "").strip()
        link_text = (item.findtext("link") or "").strip()
        source_text = (item.findtext("source") or "Google News").strip()
        date_text = (item.findtext("pubDate") or "").strip()
        description_text = _clean_html_text(item.findtext("description") or "")
        clean_title = _strip_source_from_title(title_text, source_text)
        if description_text.startswith(clean_title):
            description_text = description_text[len(clean_title) :].strip(" -:•")
        if description_text.startswith(source_text):
            description_text = description_text[len(source_text) :].strip(" -:•")
        if not description_text:
            description_text = f"Read coverage from {source_text} about {query}."

        if not link_text or not clean_title:
            continue

        domain_match = re.search(r'https?://([^/]+)', link_text)
        domain = domain_match.group(1) if domain_match else ""

        image = None
        media = item.find(".//{http://search.yahoo.com/mrss/}content")
        if media is not None and media.get("url"):
            image = media.get("url")
        else:
            enclosure = item.find("enclosure")
            if enclosure is not None and enclosure.get("url"):
                image = enclosure.get("url")
            else:
                thumbnail = item.find(".//{http://search.yahoo.com/mrss/}thumbnail")
                if thumbnail is not None and thumbnail.get("url"):
                     image = thumbnail.get("url")

        articles.append(
            {
                "title": clean_title,
                "link": link_text,
                "resolved_link": "",
                "date": date_text[:22],
                "source": source_text,
                "description": description_text[:110],
                "image": image,
                "domain": domain,
                "favicon": f"https://www.google.com/s2/favicons?domain={domain}&sz=64",
            }
        )
        if len(articles) >= max_results:
            break

    return articles


def decode_google_news_article_url(url: str) -> str:
    if not url:
        return ""
    if gnewsdecoder is None:
        return url
    try:
        result = gnewsdecoder(url)
        if isinstance(result, dict) and result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception:
        pass
    return url


def _extract_google_news_image_url(article_url: str) -> str:
    request = urllib.request.Request(
        article_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://news.google.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        html_text = response.read().decode("utf-8", errors="ignore")

    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            candidate = html.unescape(match.group(1))
            if not _is_generic_google_news_image(candidate):
                return candidate

    candidates = re.findall(r"https://lh3\.googleusercontent\.com/[^\"'\s<]+", html_text)
    cleaned = []
    for candidate in candidates:
        fixed = (
            candidate.replace("\\u0026", "&")
            .replace("\\u003d", "=")
            .replace("&amp;", "&")
        )
        if any(token in fixed for token in ("w16", "w24", "w32", "w48")):
            continue
        if _is_generic_google_news_image(fixed):
            continue
        cleaned.append(fixed)
    if cleaned:
        return cleaned[-1]

    generic = re.findall(r"https?://[^\"'\s<]+\.(?:jpg|jpeg|png|webp)(?:\?[^\"'\s<]*)?", html_text, re.IGNORECASE)
    if generic:
        candidate = html.unescape(generic[0])
        if not _is_generic_google_news_image(candidate):
            return candidate
    return ""


def _is_generic_google_news_image(url: str) -> bool:
    lowered = (url or "").lower()
    return any(
        token in lowered
        for token in (
            "lh3.googleusercontent.com/j6_cof",
            "google news",
            "news.google.com/images",
        )
    )


def _resize_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if ImageOps is not None:
        return ImageOps.fit(image.convert("RGB"), size, method=getattr(Image, "LANCZOS", Image.BICUBIC))
    return image.convert("RGB").resize(size, getattr(Image, "LANCZOS", Image.BICUBIC))


def _build_placeholder_thumbnail(title: str, source: str) -> Image.Image | None:
    if Image is None or ImageDraw is None:
        return None

    seed = abs(hash(f"{source}|{title}"))
    palette = [
        ("#12214d", "#1f2a69", "#22d3ee", "#818cf8", "#f59e0b"),
        ("#1a183f", "#2a245b", "#06b6d4", "#8b5cf6", "#f97316"),
        ("#10223f", "#18345e", "#14b8a6", "#6366f1", "#eab308"),
        ("#1a163a", "#2e1f68", "#38bdf8", "#a855f7", "#fb7185"),
    ]
    bg_a, bg_b, accent_a, accent_b, accent_c = palette[seed % len(palette)]

    image = Image.new("RGB", (240, 135), bg_a)
    draw = ImageDraw.Draw(image)

    for y in range(135):
        t = y / 134 if 134 else 0
        start_rgb = tuple(int(bg_a[i : i + 2], 16) for i in (1, 3, 5))
        end_rgb = tuple(int(bg_b[i : i + 2], 16) for i in (1, 3, 5))
        r = int((1 - t) * start_rgb[0] + t * end_rgb[0])
        g = int((1 - t) * start_rgb[1] + t * end_rgb[1])
        b = int((1 - t) * start_rgb[2] + t * end_rgb[2])
        draw.line((0, y, 240, y), fill=(r, g, b))

    draw.rounded_rectangle((10, 10, 230, 125), radius=16, outline=accent_a, width=2)
    draw.rounded_rectangle((18, 18, 222, 52), radius=10, fill=bg_b)
    draw.text((28, 26), source[:24], fill=(241, 245, 249), font=ImageFont.load_default())

    accent = [(36, 82, 78, 92), (90, 70, 122, 92), (134, 62, 154, 92), (166, 74, 184, 92)]
    accent_colors = [accent_a, accent_b, accent_a, accent_c]
    for box, color in zip(accent, accent_colors):
        draw.rounded_rectangle(box, radius=4, fill=color)

    draw.text((28, 102), "News article preview", fill=(148, 163, 184), font=ImageFont.load_default())
    return image


def load_article_thumbnail(article_url: str, title: str, source: str) -> Image.Image | None:
    if Image is None:
        return None

    try:
        image_url = _extract_google_news_image_url(article_url)
        if image_url:
            with urllib.request.urlopen(image_url, timeout=5) as response:
                image = Image.open(io.BytesIO(response.read()))
            return _resize_image(image, (240, 135))
    except Exception:
        pass

    return _build_placeholder_thumbnail(title, source)


class NewsPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(
            parent,
            fg_color=CARD_BG,
            border_color=BORDER,
            border_width=1,
            corner_radius=16,
        )
        self._thumbnail_cache: dict[str, ctk.CTkImage] = {}
        self._resolved_link_cache: dict[str, str] = {}
        self._last_query = ""
        self._title_font = ctk.CTkFont(size=10, weight="bold")
        self._body_font = ctk.CTkFont(size=13, weight="bold")
        self._small_font = ctk.CTkFont(size=11)
        self._action_font = ctk.CTkFont(size=16, weight="bold")

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(
            header,
            text="▶  RELATED NEWS ON GOOGLE NEWS",
            font=self._title_font,
            text_color=CHANNEL_TEXT,
            fg_color="transparent",
        ).pack(side="left")

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.clear()

    def clear(self) -> None:
        self._last_query = ""
        self._render_message("Search a keyword to load related news articles.")

    def search(self, query: str) -> None:
        query = (query or "").strip()
        if not query:
            self.clear()
            return
        if query == self._last_query:
            return
        self._last_query = query
        self._render_message("Loading Google News results...", color=LOADING_TEXT)
        threading.Thread(target=self._fetch_async, args=(query,), daemon=True).start()

    def _fetch_async(self, query: str) -> None:
        try:
            articles = fetch_google_news(query, max_results=6)
            self.after(0, self._render_results, articles)
        except NewsTimeoutError:
            self.after(0, self._render_message, "Google News is taking too long, try again", WATCH_RED)
        except NewsNetworkError:
            self.after(0, self._render_message, "Could not connect to Google News", WATCH_RED)
        except Exception:
            self.after(0, self._render_message, "No news articles found", MUTED_TEXT)

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

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

    def _render_results(self, articles: list[dict]) -> None:
        self._clear_content()
        if not articles:
            self._render_message("No news articles found")
            return

        scroll = ctk.CTkScrollableFrame(
            self.content,
            fg_color="transparent",
            corner_radius=0,
            height=420,
        )
        scroll.pack(fill="both", expand=True, anchor="n")

        limited_articles = articles[:8]
        for article in limited_articles:
            card = self._create_article_card(scroll, article)
            card.pack(fill="x", pady=(0, 10), padx=8)

        try:
            scroll._parent_canvas.yview_moveto(0)
        except Exception:
            pass

    def _create_article_card(self, parent, article: dict):
        card = ctk.CTkFrame(
            parent,
            fg_color=CARD_BG,
            border_color=BORDER,
            border_width=1,
            corner_radius=12,
        )
        card.grid_columnconfigure(0, weight=0)
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure(0, weight=1)

        thumb_holder = ctk.CTkFrame(
            card,
            width=240,
            height=135,
            fg_color="#2b334f",
            corner_radius=10,
        )
        thumb_holder.grid(row=0, column=0, rowspan=3, padx=12, pady=12, sticky="nw")
        thumb_holder.grid_propagate(False)
        thumb_label = ctk.CTkLabel(thumb_holder, text="Loading image", text_color=MUTED_TEXT, fg_color="transparent")
        thumb_label.place(relx=0.5, rely=0.5, anchor="center")

        title_label = ctk.CTkLabel(
            card,
            text=article.get("title", ""),
            font=self._body_font,
            text_color=TITLE_TEXT,
            justify="left",
            wraplength=620,
            anchor="w",
            fg_color="transparent",
        )
        title_label.grid(row=0, column=1, sticky="new", padx=(0, 12), pady=(14, 6))

        meta_bits = [article.get("source", "Google News")]
        if article.get("date"):
            meta_bits.append(article["date"])
        meta_label = ctk.CTkLabel(
            card,
            text="  |  ".join(meta_bits),
            font=self._small_font,
            text_color=CHANNEL_TEXT,
            anchor="w",
            fg_color="transparent",
        )
        meta_label.grid(row=1, column=1, sticky="nw", padx=(0, 12), pady=(0, 10))

        action_host = ctk.CTkFrame(card, fg_color="transparent")
        action_host.grid(row=2, column=1, sticky="sw", padx=(0, 12), pady=(0, 12))
        build_gradient_text_row(
            action_host,
            "READ ARTICLE",
            self._action_font,
            start_color="#fb7185",
            end_color="#ef4444",
            space_color="#ef4444",
        )
        action_widgets = [action_host, *action_host.winfo_children()]

        self._bind_article_card(
            card,
            article,
            thumb_holder,
            thumb_label,
            title_label,
            meta_label,
            *action_widgets,
        )

        cache_key = article.get("resolved_link") or article.get("link", "")
        cached = self._thumbnail_cache.get(cache_key)
        if cached:
            thumb_label.configure(image=cached, text="")
            thumb_label.image = cached
        else:
            threading.Thread(
                target=self._hydrate_article_async,
                args=(article, thumb_label),
                daemon=True,
            ).start()
        return card

    def _bind_article_card(self, card, article: dict, *widgets) -> None:
        def _enter(_event=None):
            card.configure(border_color=BORDER_HOVER)

        def _leave(_event=None):
            card.configure(border_color=BORDER)

        def _open(_event=None):
            url = article.get("resolved_link") or article.get("link", "")
            if url:
                webbrowser.open(url)

        for widget in (card, *widgets):
            widget.bind("<Enter>", _enter)
            widget.bind("<Leave>", _leave)
            widget.bind("<Button-1>", _open)

    def _hydrate_article_async(self, article: dict, thumb_label) -> None:
        source_link = article.get("link", "")
        resolved_link = article.get("resolved_link", "") or self._resolved_link_cache.get(source_link, "")
        if not resolved_link:
            resolved_link = decode_google_news_article_url(source_link)
            if resolved_link:
                self._resolved_link_cache[source_link] = resolved_link
                article["resolved_link"] = resolved_link

        cache_key = resolved_link or source_link
        cached = self._thumbnail_cache.get(cache_key)
        if cached:
            def _apply_cached():
                try:
                    thumb_label.configure(image=cached, text="")
                    thumb_label.image = cached
                except Exception:
                    pass
            self.after(0, _apply_cached)
            return

        image = load_article_thumbnail(
            resolved_link or source_link,
            article.get("title", ""),
            article.get("source", "Google News"),
        )
        if image is None:
            return
        ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(240, 135))
        self._thumbnail_cache[cache_key] = ctk_image

        def _apply():
            try:
                thumb_label.configure(image=ctk_image, text="")
                thumb_label.image = ctk_image
            except Exception:
                pass

        self.after(0, _apply)

