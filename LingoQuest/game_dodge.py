from __future__ import annotations

import json
import math
import queue
import random
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import customtkinter as ctk
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageTk

from quiz import build_multiple_choice_question
from storage import load_dictionary
from ui import blend_hex

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None

try:
    import mediapipe as mp  # type: ignore
except Exception:
    mp = None

try:
    import winsound  # type: ignore
except Exception:
    winsound = None


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "genz_dict.json"
STATE_FILE = APP_DIR / "app_state.json"
MODEL_DIR = APP_DIR / "assets" / "models"
FACE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
GESTURE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task"

COLORS = {
    "bg": "#06091d",
    "bg2": "#0a1030",
    "card": "#0d1235",
    "card_border": "#1e2a5e",
    "cyan": "#06b6d4",
    "cyan_soft": "#67e8f9",
    "purple": "#8b5cf6",
    "amber": "#f59e0b",
    "amber_soft": "#fde68a",
    "green": "#22c55e",
    "red": "#ef4444",
    "text": "#f1f5f9",
    "text2": "#94a3b8",
    "dot": "#1b2750",
}

FONT_HUGE = ("Segoe UI Semibold", 28)
FONT_TITLE = ("Segoe UI Semibold", 22)
FONT_BODY = ("Segoe UI", 14)
FONT_SMALL = ("Segoe UI", 11)
FONT_BUTTON = ("Segoe UI Semibold", 13)


@dataclass
class FallingObject:
    text: str
    is_correct: bool
    x: float
    y: float
    speed: float
    width: int = 180
    height: int = 72


@dataclass
class Particle:
    x: float
    y: float
    dx: float
    dy: float
    radius: float
    color: str
    created_at: float = field(default_factory=time.time)
    ttl: float = 0.3


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def load_words() -> dict[str, dict[str, Any]]:
    try:
        return load_dictionary(DATA_FILE)
    except Exception:
        return {}


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_model(path: Path, url: str) -> Path | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            urllib.request.urlretrieve(url, path)
        return path
    except Exception:
        return None


class Tracker:
    def __init__(self, output_queue: queue.Queue[dict[str, Any]]) -> None:
        self.output_queue = output_queue
        self.running = False
        self.thread: threading.Thread | None = None
        self.motion_thread: threading.Thread | None = None
        self.cap = None
        self.status = "Keyboard fallback active"
        self.face_mesh = None
        self.gesture_recognizer = None
        self.motion_ready = False
        self.motion_supported = cv2 is not None and mp is not None and hasattr(mp, "tasks")
        self.motion_init_started = False
        self.prev_punch_data = {
            "size": 0.0,
            "curl": 0.22,
            "size_history": [],
            "was_fist": False,
        }
        self.canvas_w = 1000
        self.canvas_h = 700

        if cv2 is not None:
            self.status = "Webcam preview ready"

        if cv2 is not None and mp is not None and not hasattr(mp, "tasks"):
            self.status = "Webcam preview active - tracking unavailable"

    def _initialize_motion(self) -> None:
        if not self.motion_supported or self.motion_ready:
            return

        self.motion_init_started = True
        self.status = "Loading webcam tracking..."
        try:
            gesture_model = ensure_model(MODEL_DIR / "gesture_recognizer.task", GESTURE_MODEL_URL)
            face_model = ensure_model(MODEL_DIR / "face_landmarker.task", FACE_MODEL_URL)
            if gesture_model is None or face_model is None:
                raise RuntimeError("Could not download tracking models")

            vision = mp.tasks.vision
            base_options = mp.tasks.BaseOptions

            self.face_mesh = vision.FaceLandmarker.create_from_options(
                vision.FaceLandmarkerOptions(
                    base_options=base_options(model_asset_path=str(face_model)),
                    running_mode=vision.RunningMode.VIDEO,
                    num_faces=1,
                    min_face_detection_confidence=0.5,
                    min_face_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            )
            self.gesture_recognizer = vision.GestureRecognizer.create_from_options(
                vision.GestureRecognizerOptions(
                    base_options=base_options(model_asset_path=str(gesture_model)),
                    running_mode=vision.RunningMode.VIDEO,
                    num_hands=1,
                    min_hand_detection_confidence=0.6,
                    min_hand_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            )
            self.motion_ready = True
            self.status = "Webcam tracking ready"
        except Exception:
            self.face_mesh = None
            self.gesture_recognizer = None
            self.motion_ready = False
            self.status = "Webcam preview active - keyboard control"

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

        if self.motion_supported and not self.motion_init_started:
            self.motion_thread = threading.Thread(target=self._initialize_motion, daemon=True)
            self.motion_thread.start()

    def _open_camera(self):
        if cv2 is None:
            return None
        backend_candidates = [None]
        if hasattr(cv2, "CAP_DSHOW"):
            backend_candidates.insert(0, cv2.CAP_DSHOW)
        if hasattr(cv2, "CAP_MSMF"):
            backend_candidates.insert(1, cv2.CAP_MSMF)

        for backend in backend_candidates:
            try:
                cap = cv2.VideoCapture(0, backend) if backend is not None else cv2.VideoCapture(0)
                if cap and cap.isOpened():
                    for _ in range(5):
                        ok, _frame = cap.read()
                        if ok:
                            self.status = "Webcam tracking ready" if self.motion_ready else "Webcam preview active"
                            return cap
                        time.sleep(0.05)
                    cap.release()
            except Exception:
                continue
        return None

    def stop(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        for detector in (self.face_mesh, self.gesture_recognizer):
            try:
                if detector is not None:
                    detector.close()
            except Exception:
                pass
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass

    def _loop(self) -> None:
        if cv2 is None:
            return

        self.cap = self._open_camera()
        if not self.cap or not self.cap.isOpened():
            self.status = "Camera unavailable - keyboard fallback"
            return

        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)
            nose_pos = None
            punch = None
            if self.motion_ready and self.face_mesh is not None and self.gesture_recognizer is not None:
                timestamp_ms = int(time.time() * 1000)
                nose_pos = self._get_nose_position(frame, timestamp_ms)
                punch, self.prev_punch_data = self._detect_punch(
                    frame, self.prev_punch_data, timestamp_ms
                )
            preview_full = self._build_preview(frame, self.canvas_w, self.canvas_h)
            payload = {
                "nose_pos": nose_pos,
                "punch": punch,
                "preview_full": preview_full,
                "status": self.status,
            }
            try:
                self.output_queue.put_nowait(payload)
            except queue.Full:
                try:
                    self.output_queue.get_nowait()
                except queue.Empty:
                    pass
                self.output_queue.put_nowait(payload)
            time.sleep(0.03)

    def _build_preview(self, frame: Any, canvas_w: int, canvas_h: int) -> Image.Image:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        source = Image.fromarray(rgb)
        target_w = max(1, int(canvas_w))
        target_h = max(1, int(canvas_h))
        src_w, src_h = source.size

        src_ratio = src_w / max(src_h, 1)
        target_ratio = target_w / max(target_h, 1)

        if src_ratio > target_ratio:
            crop_h = src_h
            crop_w = int(crop_h * target_ratio)
            left = max(0, (src_w - crop_w) // 2)
            box = (left, 0, left + crop_w, src_h)
        else:
            crop_w = src_w
            crop_h = int(crop_w / max(target_ratio, 1e-6))
            top = max(0, (src_h - crop_h) // 2)
            box = (0, top, src_w, top + crop_h)

        return source.crop(box).resize((target_w, target_h))

    def _get_nose_position(self, frame: Any, timestamp_ms: int) -> tuple[float, float] | None:
        if self.face_mesh is None:
            return None
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = self.face_mesh.detect_for_video(mp_image, timestamp_ms)
        if not results.face_landmarks:
            self.status = "Face not detected — move to center"
            return None

        face = results.face_landmarks[0]
        nose = face[1]
        self.status = f"Nose x={nose.x:.2f} y={nose.y:.2f}"
        return (nose.x, nose.y)

    def _detect_punch(
        self, frame: Any, prev_data: dict, timestamp_ms: int
    ) -> tuple[tuple[str, float] | None, dict]:
        if self.gesture_recognizer is None:
            return None, {"size": 0.0, "curl": 0.22, "size_history": [], "was_fist": False}

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = self.gesture_recognizer.recognize_for_video(mp_image, timestamp_ms)

        if not results.hand_landmarks:
            prev_data["curl"] = min(prev_data.get("curl", 0.22) + 0.03, 0.26)
            prev_data["size_history"] = []
            prev_data["was_fist"] = False
            return None, prev_data

        lm = results.hand_landmarks[0]
        gesture_name = ""
        if results.gestures and results.gestures[0]:
            gesture_name = results.gestures[0][0].category_name or ""

        palm_x = sum(lm[i].x for i in [0, 5, 9, 13, 17]) / 5
        palm_y = sum(lm[i].y for i in [0, 5, 9, 13, 17]) / 5
        wrist = lm[0]
        middle_tip = lm[12]
        hand_size = math.hypot(middle_tip.x - wrist.x, middle_tip.y - wrist.y)

        def _dist(a_idx: int, b_idx: int | None = None, bx: float | None = None, by: float | None = None) -> float:
            ax = lm[a_idx].x
            ay = lm[a_idx].y
            if b_idx is not None:
                bx = lm[b_idx].x
                by = lm[b_idx].y
            if bx is None or by is None:
                return 0.0
            return math.hypot(ax - bx, ay - by)

        thumb_closed = (
            _dist(4, bx=palm_x, by=palm_y) <= _dist(2, bx=palm_x, by=palm_y) * 0.95
            and _dist(4, 5) <= _dist(2, 5) * 1.05
        )
        index_closed = _dist(8, bx=palm_x, by=palm_y) <= _dist(6, bx=palm_x, by=palm_y) * 1.05
        middle_closed = _dist(12, bx=palm_x, by=palm_y) <= _dist(10, bx=palm_x, by=palm_y) * 1.05
        ring_closed = _dist(16, bx=palm_x, by=palm_y) <= _dist(14, bx=palm_x, by=palm_y) * 1.08
        pinky_closed = _dist(20, bx=palm_x, by=palm_y) <= _dist(18, bx=palm_x, by=palm_y) * 1.12
        closed_count = sum((thumb_closed, index_closed, middle_closed, ring_closed, pinky_closed))

        landmark_fist = closed_count >= 5
        gesture_fist = gesture_name == "Closed_Fist"
        is_fist = landmark_fist or (gesture_fist and closed_count >= 4)

        palm_px = (int(palm_x * frame.shape[1]), int(palm_y * frame.shape[0]))
        vector_color = (11, 158, 245) if is_fist else (212, 182, 6)
        cv2.circle(frame, palm_px, 12, vector_color, 2)

        finger_vectors = [
            (2, 4, thumb_closed),
            (5, 8, index_closed),
            (9, 12, middle_closed),
            (13, 16, ring_closed),
            (17, 20, pinky_closed),
        ]
        for start_idx, tip_idx, closed in finger_vectors:
            start_px = (
                int(lm[start_idx].x * frame.shape[1]),
                int(lm[start_idx].y * frame.shape[0]),
            )
            tip_px = (
                int(lm[tip_idx].x * frame.shape[1]),
                int(lm[tip_idx].y * frame.shape[0]),
            )
            finger_color = (11, 158, 245) if closed else (212, 182, 6)
            cv2.arrowedLine(frame, start_px, tip_px, finger_color, 3, tipLength=0.24)
        cv2.putText(
            frame,
            f"{closed_count}/5",
            (palm_px[0] + 16, max(24, palm_px[1] - 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            vector_color,
            2,
            cv2.LINE_AA,
        )

        if is_fist:
            self.status = f"Fist detected {closed_count}/5"
        else:
            self.status = f"Hand open {closed_count}/5 curled"
            if gesture_name:
                self.status += f" ({gesture_name})"

        was_fist = bool(prev_data.get("was_fist", False))
        punch_result = ("punch", palm_x) if is_fist and not was_fist else None

        updated = {
            "curl": 0.10 if is_fist else 0.26,
            "size": hand_size,
            "size_history": [],
            "was_fist": is_fist,
        }
        return punch_result, updated


class DodgeGameApp(ctk.CTkToplevel):
    def __init__(self, master=None) -> None:
        self._hidden_root = None
        if master is None:
            self._hidden_root = ctk.CTk()
            self._hidden_root.withdraw()
            master = self._hidden_root

        super().__init__(master)
        self.title("Adam Dictionary - Dodge Arena")
        self.geometry("1220x980")
        self.minsize(980, 760)
        self.configure(fg_color=COLORS["bg"])

        self.words = load_words()
        self.app_state = load_state()
        self.high_score = int(self.app_state.get("dodge_high_score", 0))

        self.input_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=2)
        self.tracker = Tracker(self.input_queue)

        self.score = 0
        self.combo = 0
        self.lives = 3
        self.player_x = 640.0
        self.player_y = 610.0
        self.player_punch_until = 0.0
        self.screen_flash_until = 0.0
        self.feedback_text = ""
        self.feedback_color = COLORS["text2"]
        self.feedback_until = 0.0
        self.running = False
        self.round_wrong_count = 0
        self.round_wrong_dodged = 0
        self.round_correct_hit = False
        self.current_question: dict[str, Any] | None = None
        self.objects: list[FallingObject] = []
        self.particles: list[Particle] = []
        self.keys_pressed: set[str] = set()
        self._bg_photo: ImageTk.PhotoImage | None = None
        self._after_ids: set[str] = set()
        self.game_over_overlay: ctk.CTkFrame | None = None

        self._build_ui()
        self.bind("<KeyPress>", self._on_key_press)
        self.bind("<KeyRelease>", self._on_key_release)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule(100, self._start_intro)

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(18, 10))

        self.home_btn = ctk.CTkButton(
            header,
            text="Close",
            font=FONT_BUTTON,
            width=120,
            height=40,
            corner_radius=20,
            fg_color=COLORS["card"],
            border_width=1,
            border_color=COLORS["card_border"],
            command=self._on_close,
        )
        self.home_btn.pack(side="left")

        self.target_icon_lbl = ctk.CTkLabel(
            header,
            text="\u25ce",
            font=("Segoe UI Symbol", 28, "bold"),
            text_color=COLORS["cyan_soft"],
        )
        self.target_icon_lbl.pack(side="left", padx=(18, 8))

        self.target_word_row = ctk.CTkFrame(header, fg_color="transparent")
        self.target_word_row.pack(side="left", padx=(0, 0))

        self.target_hint_lbl = ctk.CTkLabel(
            header,
            text="Hit the correct meaning. Avoid the wrong ones.",
            font=FONT_BODY,
            text_color=COLORS["text2"],
        )
        self.target_hint_lbl.pack(side="left", padx=(16, 0))

        self.score_lbl = ctk.CTkLabel(header, text="★ Score: 0", font=FONT_TITLE, text_color=COLORS["green"])
        self.score_lbl.pack(side="right", padx=(18, 0))

        self.high_lbl = ctk.CTkLabel(header, text=f"\U0001f3c6 High: {self.high_score}", font=FONT_BODY, text_color=COLORS["text2"])
        self.high_lbl.pack(side="right", padx=(18, 0))

        self.combo_lbl = ctk.CTkLabel(header, text="⚡ Combo x0", font=FONT_BODY, text_color=COLORS["amber"])
        self.combo_lbl.pack(side="right", padx=(18, 0))

        self.life_lbl = None

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew")

        self.canvas = tk.Canvas(left, bg=COLORS["bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        self.object_canvas_font = tkfont.Font(self, family="Segoe UI", size=14, weight="normal")
        self.target_canvas_font = tkfont.Font(self, family="Segoe UI Semibold", size=50, weight="bold")
        self.status_lbl = None
        self.prompt_lbl = None
        self.help_lbl = None

    def _start_intro(self) -> None:
        overlay = ctk.CTkFrame(self, fg_color="#050817")
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.intro_overlay = overlay

        card = ctk.CTkFrame(overlay, fg_color=COLORS["card"], corner_radius=22, border_width=1, border_color=COLORS["card_border"])
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(card, text="DODGE ARENA", font=("Segoe UI Semibold", 30), text_color=COLORS["text"]).pack(padx=28, pady=(24, 8))
        ctk.CTkLabel(card, text="Move your face to dodge. Make a fist to hit the correct answer.", font=FONT_BODY, text_color=COLORS["text2"]).pack(padx=28)

        controls = ctk.CTkFrame(card, fg_color=COLORS["bg2"], corner_radius=16)
        controls.pack(fill="x", padx=24, pady=20)
        for line in (
            "MOVE FACE  ->  dodge left / right",
            "MAKE FIST  ->  hit correct answer",
            "avoid wrong answers falling down",
        ):
            ctk.CTkLabel(controls, text=line, font=FONT_BODY, text_color=COLORS["text"], anchor="w").pack(fill="x", padx=18, pady=6)

        ctk.CTkButton(
            card,
            text="Start Test",
            font=FONT_BUTTON,
            height=42,
            corner_radius=21,
            fg_color=COLORS["purple"],
            hover_color="#7c3aed",
            command=lambda: self._begin_game(),
        ).pack(fill="x", padx=24, pady=(0, 24))

    def _begin_game(self) -> None:
        if hasattr(self, "intro_overlay"):
            self.intro_overlay.destroy()
        self.running = True
        self.tracker.start()
        if self.status_lbl is not None:
            self.status_lbl.configure(text=self.tracker.status)
        self._new_round()
        self._schedule(16, self._tick)

    def _new_round(self) -> None:
        question = build_multiple_choice_question(self.words)
        if not question:
            self.feedback_text = "Not enough dictionary data for game"
            self.feedback_color = COLORS["red"]
            self.feedback_until = time.time() + 2.0
            return

        self.current_question = question
        self._update_target_word_label(question["word"])
        if self.prompt_lbl is not None:
            self.prompt_lbl.configure(text=f"Target word\n{question['word']}")
        self.objects = []
        self.round_wrong_count = 0
        self.round_wrong_dodged = 0
        self.round_correct_hit = False

        width = max(self.canvas.winfo_width(), 900)
        lanes = [width * 0.16, width * 0.38, width * 0.62, width * 0.84]
        random.shuffle(lanes)
        for idx, option in enumerate(question["options"]):
            is_correct = option == question["answer"]
            if not is_correct:
                self.round_wrong_count += 1
            self.objects.append(
                FallingObject(
                    text=option,
                    is_correct=is_correct,
                    x=lanes[idx],
                    y=-idx * 120 - 80,
                    speed=random.uniform(2.2, 3.5),
                    width=min(280, max(180, int(width * 0.18))),
                )
            )

    def _on_key_press(self, event: tk.Event) -> None:
        keysym = event.keysym.lower()
        self.keys_pressed.add(keysym)
        if keysym == "space":
            self._handle_punch(None)

    def _on_key_release(self, event: tk.Event) -> None:
        self.keys_pressed.discard(event.keysym.lower())

    def _poll_tracking(self) -> None:
        while True:
            try:
                payload = self.input_queue.get_nowait()
            except queue.Empty:
                break

            nose_pos = payload.get("nose_pos")
            if nose_pos is not None:
                nose_x_ratio, nose_y_ratio = nose_pos
                canvas_w = max(self.canvas.winfo_width(), 900)
                canvas_h = max(self.canvas.winfo_height(), 700)
                target_x = nose_x_ratio * canvas_w
                target_y = nose_y_ratio * canvas_h
                smoothing = 0.25
                self.player_x += (target_x - self.player_x) * smoothing
                self.player_y += (target_y - self.player_y) * smoothing
                self.player_x = clamp(self.player_x, 40, canvas_w - 40)
                self.player_y = clamp(self.player_y, canvas_h * 0.4, canvas_h - 40)
            punch = payload.get("punch")
            if punch:
                self._handle_punch(punch[1])
            preview_full = payload.get("preview_full")
            if isinstance(preview_full, Image.Image):
                self._bg_photo = ImageTk.PhotoImage(preview_full)
            status = payload.get("status")
            if self.status_lbl is not None and isinstance(status, str) and status:
                self.status_lbl.configure(text=status)

    def _tick(self) -> None:
        if not self.running:
            return

        self.tracker.canvas_w = max(1, self.canvas.winfo_width() or 1000)
        self.tracker.canvas_h = max(1, self.canvas.winfo_height() or 700)
        self._poll_tracking()
        self._apply_keyboard_movement()
        self._update_objects()
        self._update_particles()
        self._update_score_labels()
        self._redraw()
        self._schedule(16, self._tick)

    def _apply_keyboard_movement(self) -> None:
        if "left" in self.keys_pressed:
            self.player_x -= 12
        if "right" in self.keys_pressed:
            self.player_x += 12
        width = max(self.canvas.winfo_width(), 900)
        self.player_x = clamp(self.player_x, 50, width - 50)

    def _handle_punch(self, punch_ratio: float | None) -> None:
        now = time.time()
        self.player_punch_until = now + 0.2
        target = None
        target_score = float("inf")
        punch_range_y = 190
        width = max(self.canvas.winfo_width(), 1)
        hit_range_x = 220
        for obj in self.objects:
            if self.player_y - punch_range_y <= obj.y <= self.player_y:
                if abs(obj.x - self.player_x) > hit_range_x:
                    continue
                horizontal_bias = 0.0
                if punch_ratio is not None:
                    horizontal_bias = abs((obj.x / width) - punch_ratio) * 60
                score = abs(obj.x - self.player_x) + horizontal_bias
                if score < target_score:
                    target = obj
                    target_score = score

        if target is None:
            self._show_feedback("WHIFF!", "#9ca3af", 0.45)
            return

        self.objects.remove(target)
        if target.is_correct:
            self.round_correct_hit = True
            self.combo += 1
            gained = 100 + max(0, self.combo - 1) * 20
            self.score += gained
            self._spawn_explosion(target.x, target.y, COLORS["amber_soft"])
            self._show_feedback(f"+{gained} PUNCH!", COLORS["amber"], 0.65)
            if self.combo >= 3:
                self._spawn_explosion(self.player_x, self.player_y, COLORS["amber"])
        else:
            self.combo = 0
            self.lives -= 1
            self.screen_flash_until = time.time() + 0.2
            self._spawn_explosion(target.x, target.y, COLORS["red"])
            self._show_feedback("WRONG PUNCH! -1", COLORS["red"], 0.7)
            if self.lives > 0:
                self._play_sound("lose_life")

        if not self.objects:
            self._finish_round()

    def _finish_round(self) -> None:
        if self.round_wrong_count and self.round_wrong_dodged >= self.round_wrong_count:
            self.score += 50
            self._show_feedback("PERFECT DODGE! +50", COLORS["cyan"], 0.8)
        if self.lives <= 0:
            self._game_over()
            return
        self._schedule(500, self._new_round)

    def _update_objects(self) -> None:
        width = max(self.canvas.winfo_width(), 900)
        height = max(self.canvas.winfo_height(), 700)
        self.player_x = clamp(self.player_x, 50, width - 50)
        remaining: list[FallingObject] = []
        player_hitbox = 56

        for obj in self.objects:
            obj.y += obj.speed
            if obj.y > height + obj.height:
                if obj.is_correct:
                    self.combo = 0
                else:
                    self.round_wrong_dodged += 1
                continue

            if not obj.is_correct and abs(obj.x - self.player_x) < player_hitbox and obj.y >= self.player_y - 35:
                self.lives -= 1
                self.combo = 0
                self.screen_flash_until = time.time() + 0.2
                self._show_feedback("HIT BY WRONG! -1", COLORS["red"], 0.7)
                self._spawn_explosion(obj.x, obj.y, COLORS["red"])
                if self.lives > 0:
                    self._play_sound("lose_life")
                continue

            remaining.append(obj)

        self.objects = remaining
        if self.lives <= 0:
            self._game_over()
        elif not self.objects:
            self._finish_round()

    def _game_over(self) -> None:
        self.running = False
        if self.score > self.high_score:
            self.high_score = self.score
            self.app_state["dodge_high_score"] = self.high_score
            save_state(self.app_state)
        self._play_sound("game_over")
        self._show_feedback("YOU DIED", COLORS["red"], 4.0)
        self._show_game_over_overlay()

    def _show_game_over_overlay(self) -> None:
        if self.game_over_overlay is not None and self.game_over_overlay.winfo_exists():
            self.game_over_overlay.destroy()
        overlay = ctk.CTkFrame(self, fg_color="#030612")
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        card = ctk.CTkFrame(
            overlay,
            fg_color=COLORS["card"],
            corner_radius=24,
            border_width=1,
            border_color=COLORS["card_border"],
        )
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            card,
            text="YOU DIED",
            font=("Segoe UI Semibold", 34),
            text_color=COLORS["red"],
        ).pack(padx=36, pady=(28, 10))
        ctk.CTkLabel(card, text=f"Score: {self.score}", font=FONT_TITLE, text_color=COLORS["text"]).pack()
        ctk.CTkLabel(card, text=f"High score: {self.high_score}", font=FONT_BODY, text_color=COLORS["text2"]).pack(pady=(8, 20))
        ctk.CTkButton(
            card,
            text="Restart",
            font=FONT_BUTTON,
            height=44,
            corner_radius=22,
            fg_color=COLORS["purple"],
            hover_color="#7c3aed",
            command=self._restart_game,
        ).pack(fill="x", padx=28, pady=(0, 28))

        self.game_over_overlay = overlay

    def _restart_game(self) -> None:
        if self.game_over_overlay is not None and self.game_over_overlay.winfo_exists():
            self.game_over_overlay.destroy()
        self.game_over_overlay = None
        self.score = 0
        self.combo = 0
        self.lives = 3
        self.player_x = max(self.canvas.winfo_width(), 900) / 2
        self.player_punch_until = 0.0
        self.objects.clear()
        self.particles.clear()
        self.running = True
        self._new_round()
        self.after(16, self._tick)

    def _spawn_explosion(self, x: float, y: float, color: str) -> None:
        for _ in range(20):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(2.0, 7.0)
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    dx=math.cos(angle) * speed,
                    dy=math.sin(angle) * speed,
                    radius=random.uniform(2, 5),
                    color=color,
                )
            )

    def _update_particles(self) -> None:
        now = time.time()
        updated: list[Particle] = []
        for part in self.particles:
            age = now - part.created_at
            if age >= part.ttl:
                continue
            part.x += part.dx
            part.y += part.dy
            updated.append(part)
        self.particles = updated

    def _show_feedback(self, text: str, color: str, ttl: float) -> None:
        self.feedback_text = text
        self.feedback_color = color
        self.feedback_until = time.time() + ttl

    def _update_score_labels(self) -> None:
        self.score_lbl.configure(text=f"Score: {self.score}")
        self.combo_lbl.configure(text=f"Combo x{self.combo}")
        if self.life_lbl is not None:
            self.life_lbl.configure(text=f"Lives: {self.lives}")
        self.high_lbl.configure(text=f"High: {max(self.high_score, self.score)}")

    def _redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = canvas.winfo_width() or 1000
        height = canvas.winfo_height() or 700

        if self._bg_photo is not None:
            canvas.create_image(0, 0, anchor="nw", image=self._bg_photo)

        for x in range(0, width, 40):
            for y in range(0, height, 40):
                canvas.create_rectangle(x, y, x + 1, y + 1, fill=COLORS["dot"], outline="", stipple="gray50")

        for obj in self.objects:
            wrapped, line_count = self._wrap_canvas_text(obj.text, obj.width - 24, max_lines=3)
            draw_height = max(obj.height, 26 + line_count * 24)
            x1 = obj.x - obj.width / 2
            y1 = obj.y - draw_height / 2
            x2 = obj.x + obj.width / 2
            y2 = obj.y + draw_height / 2
            fill = "#162041" if not obj.is_correct else "#16253d"
            outline = COLORS["card_border"] if not obj.is_correct else COLORS["cyan"]
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=2)
            canvas.create_text(obj.x, obj.y, text=wrapped, fill=COLORS["text"], font=self.object_canvas_font)

        punching = time.time() < self.player_punch_until
        if self.combo >= 3:
            canvas.create_oval(self.player_x - 44, self.player_y - 44, self.player_x + 44, self.player_y + 44, outline=COLORS["amber"], width=3)
        self._draw_player(punching)
        px, py = self.player_x, self.player_y
        canvas.create_line(px - 8, py, px + 8, py, fill=COLORS["cyan_soft"], width=2)
        canvas.create_line(px, py - 8, px, py + 8, fill=COLORS["cyan_soft"], width=2)

        hearts = " ".join("♥" for _ in range(max(self.lives, 0))) or "×"
        canvas.create_text(
            12,
            12,
            anchor="nw",
            text=hearts,
            fill=COLORS["red"],
            font=("Segoe UI Symbol", 28, "bold"),
        )

        for part in self.particles:
            canvas.create_oval(part.x - part.radius, part.y - part.radius, part.x + part.radius, part.y + part.radius, fill=part.color, outline="")

        if time.time() < self.feedback_until and self.feedback_text:
            canvas.create_text(width / 2, height - 34, text=self.feedback_text, fill=self.feedback_color, font=("Segoe UI Semibold", 20))

        if time.time() < self.screen_flash_until:
            canvas.create_rectangle(0, 0, width, height, fill=COLORS["red"], outline="", stipple="gray25")

    def _draw_player(self, punching: bool = False) -> None:
        canvas = self.canvas
        px = self.player_x
        py = self.player_y
        if not punching:
            canvas.create_oval(px - 30, py - 30, px + 30, py + 30, fill=COLORS["cyan"], outline=COLORS["cyan_soft"], width=2)
        else:
            canvas.create_oval(px - 55, py - 55, px + 55, py + 55, outline=COLORS["amber"], width=3)
            canvas.create_line(px, py - 30, px, py - 80, fill=COLORS["amber_soft"], width=4, arrow="last")
            canvas.create_oval(px - 40, py - 20, px + 40, py + 20, fill=COLORS["amber"], outline=COLORS["amber_soft"], width=3)
            canvas.create_arc(px - 50, py - 50, px + 50, py + 50, start=70, extent=40, style="arc", outline=COLORS["amber_soft"], width=4)

    def _draw_gradient_target_word(self, center_x: float, center_y: float, text: str) -> None:
        canvas = self.canvas
        font = self.target_canvas_font
        total_width = sum(font.measure(ch) for ch in text)
        cursor_x = center_x - total_width / 2
        start_color = COLORS["cyan"]
        end_color = COLORS["purple"]
        glow_color = "#10244d"

        for index, char in enumerate(text):
            char_width = font.measure(char)
            draw_x = cursor_x + char_width / 2
            ratio = index / max(len(text) - 1, 1)
            fill = blend_hex(start_color, end_color, ratio)
            if char != " ":
                for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                    canvas.create_text(
                        draw_x + dx,
                        center_y + dy,
                        text=char,
                        fill=glow_color,
                        font=font,
                    )
                canvas.create_text(
                    draw_x,
                    center_y + 3,
                    text=char,
                    fill=blend_hex(fill, "#ffffff", 0.35),
                    font=font,
                )
            canvas.create_text(draw_x, center_y, text=char, fill=fill, font=font)
            cursor_x += char_width

    def _update_target_word_label(self, text: str) -> None:
        if not hasattr(self, "target_word_row"):
            return
        for child in self.target_word_row.winfo_children():
            child.destroy()
        font = ("Segoe UI Semibold", 36)
        for index, char in enumerate(text):
            ratio = index / max(len(text) - 1, 1)
            ctk.CTkLabel(
                self.target_word_row,
                text=char,
                font=font,
                text_color=blend_hex(COLORS["cyan"], COLORS["purple"], ratio),
                fg_color="transparent",
            ).pack(side="left")

    def _play_sound(self, kind: str) -> None:
        try:
            if winsound is not None:
                if kind == "lose_life":
                    winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC)
                elif kind == "game_over":
                    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
            else:
                self.bell()
        except Exception:
            try:
                self.bell()
            except Exception:
                pass

    def _wrap_canvas_text(self, text: str, max_width: int, max_lines: int = 3) -> tuple[str, int]:
        words = text.split()
        lines: list[str] = []
        current = ""
        truncated = False
        for word in words:
            candidate = f"{current} {word}".strip()
            if self.object_canvas_font.measure(candidate) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
                if len(lines) >= max_lines:
                    truncated = True
                    break
        if current:
            if len(lines) < max_lines:
                lines.append(current)
            else:
                truncated = True
        if truncated and lines:
            last = lines[-1]
            while last and self.object_canvas_font.measure(f"{last}...") > max_width:
                last = last[:-1]
            lines[-1] = f"{last.rstrip()}..."
        return "\n".join(lines), len(lines)

    def _on_close(self) -> None:
        self.running = False
        self.tracker.stop()
        for after_id in list(self._after_ids):
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        self._after_ids.clear()
        self.destroy()
        if self._hidden_root is not None:
            try:
                self._hidden_root.destroy()
            except Exception:
                pass

    def _schedule(self, delay_ms: int, callback) -> None:
        after_id = ""

        def wrapped() -> None:
            self._after_ids.discard(after_id)
            if self.winfo_exists():
                callback()

        after_id = self.after(delay_ms, wrapped)
        self._after_ids.add(after_id)


def main() -> None:
    app = DodgeGameApp()
    try:
        app.attributes("-topmost", True)
        app.after(350, lambda: app.attributes("-topmost", False))
        app.after(120, app.lift)
        app.after(160, app.focus_force)
    except Exception:
        pass
    app.mainloop()


if __name__ == "__main__":
    main()
