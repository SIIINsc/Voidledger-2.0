import math
import os
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from threading import Thread
from time import sleep
from tkinter import messagebox, scrolledtext, font, ttk
from typing import Optional
import webbrowser

import global_settings
import modules.helpers as Helpers
from modules import mappings_parser
from modules.bounty_list import BOUNTY_TARGETS

class AppLogger():
    def __init__(self, text_widget): self.text_widget = text_widget
    def Decorator(log_writer):
        def widget_handler(self, message):
            if not self.text_widget.winfo_exists(): return
            self.text_widget.config(state=tk.NORMAL)
            log_time = datetime.now().strftime("%X")
            log_writer(self, log_time, message)
            self.text_widget.config(state=tk.DISABLED)
            self.text_widget.see(tk.END)
        return widget_handler
    @Decorator
    def debug(self, lt, msg):
        if global_settings.DEBUG_MODE["enabled"]: self.text_widget.insert(tk.END, f"{lt} DEBUG: {msg}\n")
    @Decorator
    def info(self, lt, msg): self.text_widget.insert(tk.END, f"{lt} {msg}\n")
    @Decorator
    def warning(self, lt, msg): self.text_widget.insert(tk.END, f"{lt} ⚠️ WARNING: {msg}\n")
    @Decorator
    def error(self, lt, msg): self.text_widget.insert(tk.END, f"{lt} ❌ ERROR: {msg}\n")
    @Decorator
    def success(self, lt, msg): self.text_widget.insert(tk.END, f"{lt} ✅ SUCCESS: {msg}\n")

class GUI():
    def __init__(self, cfg_handler, local_version, anonymize_state):
        self.local_version = local_version
        self.anonymize_state = anonymize_state
        self.init_run = True; self.cfg_handler = cfg_handler
        self.log=None; self.sounds=None; self.api=None; self.cm=None; self.app=None
        self.key_entry=None; self.api_status_label=None; self.volume_slider=None
        self.session_kills_label=None; self.session_deaths_label=None; self.kd_ratio_label=None
        self.curr_killstreak_label=None; self.max_killstreak_label=None
        self.log_parser=None
        self.killer_handle_entry=None
        self.killer_ship_combo=None
        self.killer_weapon_combo=None
        self.victim_handle_entry=None
        self.victim_ship_combo=None
        self.injection_env_var=None
        self.injection_delivery_var=None
        self.ship_map = {}
        self.weapon_map = {}
        self.reverse_ship_map = {}
        self.reverse_weapon_map = {}
        self.kill_history_widget = None
        self.kill_history_entries = []
        self.star_citizen_log_widget = None
        self.star_citizen_log_entries = []
        self.star_citizen_summary_widgets = {}
        self.pvp_summary_data = {}
        self.summary_fonts = {}
        self.mode_display_names = {"PU": "Persistent Universe", "AC": "Arena Commander"}
        self._updating_volume_slider = False
        self._pending_volume_percent = None
        self._pending_icon_warnings = []
        self._manual_stat_state = {"kills": 0, "deaths": 0, "curr_streak": 0, "max_streak": 0}
        self.colors = {'bg_dark':'#1e1e1e','bg_mid':'#252526','bg_light':'#333333','text':'#cccccc',
                       'text_dark':'#D6D6D6','accent':'#007acc','button':'#007acc',
                       'submit_button':'#4CAF50','error':'#f44747','gold':'#d4af37'}
        self.blightveil_theme = {
            'title': '#A855F7',
            'accent': '#8B5CF6',
            'hover': '#C084FC'
        }

    def display_bounty_event(self, event_type, target, requirement, actor=None):
        """Surface requirement details and record bounty activity in the UI."""
        requirement_display = requirement if requirement else "No requirement."

        # Pop a detail dialog so the pilot immediately sees the requirement.
        message_lines = [
            f"Event: {event_type.title()}",
            f"Target: {target}",
        ]
        if actor:
            message_lines.insert(1, f"Actor: {actor}")
        message_lines.append(f"Requirement: {requirement_display}")
        if event_type != "kill":
            messagebox.showinfo(
                title="Continental Bounty Update",
                message="\n".join(message_lines)
            )

        if event_type == "kill":
            self._append_kill_history(actor, target, requirement)

    def _append_kill_history(self, actor, target, requirement):
        """Record a bounty kill in the on-screen session history."""
        if not (self.kill_history_widget and self.kill_history_widget.winfo_exists()):
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = (timestamp, target, requirement if requirement else None)
        self.kill_history_entries.insert(0, entry)
        # Keep the history manageable.
        if len(self.kill_history_entries) > 50:
            self.kill_history_entries.pop()

        self.kill_history_widget.config(state=tk.NORMAL)
        self.kill_history_widget.delete("1.0", tk.END)
        for event_time, tgt, req in self.kill_history_entries:
            self._render_kill_history_line(event_time, tgt, req)
        self.kill_history_widget.config(state=tk.DISABLED)
        self.kill_history_widget.see("1.0")

    def _render_kill_history_line(self, event_time, target, requirement):
        self.kill_history_widget.insert(tk.END, "[PU] ", ("prefix",))
        self.kill_history_widget.insert(tk.END, event_time, ("prefix",))
        self.kill_history_widget.insert(tk.END, " | ", ("separator",))
        self.kill_history_widget.insert(tk.END, "You eliminated ", ("kill_text",))
        self.kill_history_widget.insert(tk.END, target, ("victim_name",))

        if requirement:
            self.kill_history_widget.insert(tk.END, " | ", ("separator",))
            requirement_text = requirement.strip()
            if not requirement_text.startswith("⚠️"):
                requirement_text = f"⚠️ {requirement_text}"
            self.kill_history_widget.insert(tk.END, f"{requirement_text}\n", ("requirement_alert",))
        else:
            self.kill_history_widget.insert(tk.END, "\n")

    def _locate_emoji_candidate(self, filename: str) -> Optional[Path]:
        candidate = Path(filename)
        if candidate.is_file():
            return candidate

        lowercase_name = filename.lower()
        for entry in Path(".").iterdir():
            if entry.is_file() and entry.name.lower() == lowercase_name:
                return entry
        return None

    def _fit_image_to_box(self, image: tk.PhotoImage, box_size: int) -> tk.PhotoImage:
        width, height = image.width(), image.height()
        if width <= 0 or height <= 0:
            return image

        scale = max(width / box_size, height / box_size, 1.0)
        scaled = image
        if scale > 1.0:
            factor = max(1, math.ceil(scale))
            scaled = image.subsample(factor, factor)
            width, height = scaled.width(), scaled.height()

        if width == box_size and height == box_size:
            return scaled

        final_image = tk.PhotoImage(width=box_size, height=box_size)
        offset_x = max(0, (box_size - width) // 2)
        offset_y = max(0, (box_size - height) // 2)
        final_image.tk.call(final_image, 'copy', scaled, '-from', 0, 0, width, height, '-to', offset_x, offset_y)
        return final_image

    def _load_single_emoji(self, filename: str, fallback_factory, box_size: int) -> tk.PhotoImage:
        candidate_paths = []

        static_candidate = Path(Helpers.resource_path(os.path.join("static", "images", filename)))
        if static_candidate.is_file():
            candidate_paths.append(static_candidate)

        located = self._locate_emoji_candidate(filename)
        if located and located not in candidate_paths:
            candidate_paths.append(located)

        for candidate in candidate_paths:
            try:
                loaded = tk.PhotoImage(file=str(candidate))
                return self._fit_image_to_box(loaded, box_size)
            except tk.TclError:
                continue

        self._pending_icon_warnings.append(f"Main Log, missing emoji, {filename}")
        return fallback_factory()

    def _load_emoji_assets(self) -> None:
        self._pending_icon_warnings.clear()
        self.continental_history_badge_image = self._load_single_emoji(
            "continental_logo.png",
            self._create_continental_badge_image,
            24,
        )
        self.star_citizen_logo_image = self._load_single_emoji(
            "starcitizen_logo.png",
            self._create_star_citizen_logo_image,
            26,
        )
        self.blightveil_badge_image = self._load_single_emoji(
            "Blightveil_logo.png",
            self._create_blightveil_badge_image,
            28,
        )

    def _flush_icon_warnings(self) -> None:
        if not self.log or not self._pending_icon_warnings:
            return
        for warning in self._pending_icon_warnings:
            self.log.warning(warning)
        self._pending_icon_warnings.clear()

    def _create_continental_badge_image(self):
        """Create a small Continental crest badge using Tk's native drawing."""
        size = 24
        badge = tk.PhotoImage(width=size, height=size)
        center = (size - 1) / 2
        outer_radius = (size - 2) / 2
        inner_radius = outer_radius * 0.68
        cross_radius = inner_radius * 0.45
        gold = "#d4a017"
        highlight = "#f6dd74"
        inner = "#1b1b1b"

        for y in range(size):
            for x in range(size):
                dx = x - center
                dy = y - center
                dist_sq = dx * dx + dy * dy
                if dist_sq > outer_radius * outer_radius:
                    continue

                dist = dist_sq ** 0.5
                color = gold
                if dist < inner_radius:
                    color = inner

                    # horizontal ring accent
                    if abs(dy) <= 1.0:
                        color = gold

                    # vertical spine
                    if abs(dx) <= 1.0:
                        color = gold

                    # descending diagonal arms
                    if dy >= 0 and abs(dx * 0.85 - (dy - inner_radius * 0.2)) <= 1.2 and dist >= cross_radius:
                        color = gold
                    if dy >= 0 and abs(dx * 0.85 + (dy - inner_radius * 0.2)) <= 1.2 and dist >= cross_radius:
                        color = gold

                    # upper cross beam
                    if abs(dy + inner_radius * 0.55) <= 1.0 and dist >= cross_radius:
                        color = gold

                # top arc highlight for a subtle sheen
                if dist >= inner_radius and dy < 0:
                    color = highlight

                badge.put(color, (x, y))

        return badge

    def _create_blightveil_badge_image(self):
        """Create a compact robotic skull badge in the BlightVeil palette."""
        size = 28
        badge = tk.PhotoImage(width=size, height=size)
        center = (size - 1) / 2
        outer_radius = (size - 2) / 2
        inner_radius = outer_radius * 0.75
        face_radius = inner_radius * 0.85

        rim_color = "#5f33b8"
        rim_highlight = "#8c5cfd"
        glow_color = "#b892ff"
        face_color = "#14111f"
        jaw_plate = "#1d1829"
        eye_color = "#ff4d4d"
        eye_glow = "#ff7a7a"
        accent = "#8d62ff"

        left_eye_center = (-face_radius * 0.38, -face_radius * 0.05)
        right_eye_center = (face_radius * 0.38, -face_radius * 0.05)
        eye_rx = face_radius * 0.42
        eye_ry = face_radius * 0.28

        for y in range(size):
            for x in range(size):
                dx = x - center
                dy = y - center
                dist = (dx * dx + dy * dy) ** 0.5

                if dist > outer_radius:
                    continue

                color = rim_color

                if inner_radius <= dist <= outer_radius:
                    color = rim_highlight if dy < -outer_radius * 0.1 else rim_color

                if dist < inner_radius:
                    color = glow_color

                    if dist < face_radius:
                        color = face_color

                        # brow accent strip
                        if dy < -face_radius * 0.15 and abs(dx) <= face_radius * 0.78:
                            color = accent

                        # cheek glow arc
                        if abs(dy + face_radius * 0.05) <= face_radius * 0.25 and abs(dx) >= face_radius * 0.45:
                            color = glow_color

                        # jaw plate and grille
                        if dy > face_radius * 0.35 and abs(dx) <= face_radius * 0.7:
                            color = jaw_plate
                            if abs(dx) <= face_radius * 0.18:
                                color = accent
                        if dy > face_radius * 0.55 and abs(dx) <= face_radius * 0.6:
                            band = int(abs(dx) / (face_radius * 0.18))
                            color = accent if band % 2 == 0 else jaw_plate

                        # vertical respirator vents
                        if dy > face_radius * 0.45 and abs(dx) <= face_radius * 0.12:
                            color = accent

                        # eye sockets with glow
                        for cx, cy in (left_eye_center, right_eye_center):
                            norm = ((dx - cx) / eye_rx) ** 2 + ((dy - cy) / eye_ry) ** 2
                            if norm <= 1.0:
                                color = eye_color
                                if norm <= 0.45:
                                    color = eye_glow
                                break

                # subtle outer glow halo
                if inner_radius * 0.96 <= dist <= inner_radius and dy < 0:
                    color = glow_color

                badge.put(color, (x, y))

        return badge

    def _create_star_citizen_logo_image(self):
        """Render a tiny Aegis Gladius styled starfighter badge."""
        size = 26
        bg_color = self.colors['bg_dark']
        hull_main = "#d1d9e8"
        hull_shadow = "#8a94a7"
        hull_highlight = "#f3f6fb"
        canopy = "#1f3556"
        engine_glow = "#4cd6ff"
        accent = "#9ea8ba"

        logo = tk.PhotoImage(width=size, height=size)
        center = (size - 1) / 2
        outer_radius = (size - 2) / 2

        for y in range(size):
            for x in range(size):
                logo.put(bg_color, (x, y))

        for y in range(size):
            for x in range(size):
                dx = x - center
                dy = y - center

                in_ship = False
                color = None

                # Forward fuselage and nose
                if dy <= -outer_radius * 0.1:
                    taper = max(0.0, 1.0 - (-dy - outer_radius * 0.1) / (outer_radius * 0.55))
                    half_width = size * 0.16 * taper + size * 0.04
                    if abs(dx) <= half_width:
                        in_ship = True
                        color = hull_highlight if dy < -outer_radius * 0.45 else hull_main

                # Mid fuselage
                fuselage_half = size * 0.18 + max(0, (outer_radius * 0.22 - abs(dy))) * 0.25
                if not in_ship and abs(dx) <= fuselage_half and abs(dy) <= outer_radius * 0.65:
                    in_ship = True
                    color = hull_main if dy < outer_radius * 0.1 else hull_shadow

                # Delta wings
                if not in_ship and -outer_radius * 0.05 <= dy <= outer_radius * 0.32:
                    wing_extent = size * 0.6 - abs(dy) * 0.32
                    if abs(dx) <= wing_extent:
                        in_ship = True
                        color = hull_shadow if abs(dx) > size * 0.34 else hull_main

                # Tail plane
                if not in_ship and dy > outer_radius * 0.32:
                    tail_extent = size * 0.32 - (dy - outer_radius * 0.32) * 0.55
                    if tail_extent > 0 and abs(dx) <= tail_extent:
                        in_ship = True
                        color = hull_shadow

                if not in_ship:
                    continue

                # Wing leading edges highlight
                if -outer_radius * 0.05 <= dy <= outer_radius * 0.22 and abs(dx) >= size * 0.42:
                    color = hull_highlight

                # Mid-body accent panel
                if abs(dx) <= size * 0.22 and -outer_radius * 0.05 <= dy <= outer_radius * 0.18:
                    color = accent

                # Canopy strip
                if abs(dx) <= size * 0.12 and -outer_radius * 0.18 <= dy <= outer_radius * 0.05:
                    color = canopy

                # Engine glow
                if abs(dx) <= size * 0.12 and outer_radius * 0.28 <= dy <= outer_radius * 0.45:
                    color = engine_glow

                logo.put(color, (x, y))

        return logo

    def open_discord_link(self, event): webbrowser.open_new(r"https://discord.com/channels/1166103102378750033/1329181164933480578")
    def toggle_anonymize(self):
        self.anonymize_state["enabled"] = not self.anonymize_state["enabled"]
        self.anonymize_button.config(text="Anonymity On" if self.anonymize_state["enabled"] else "Anonymity Off",
                                     bg=self.colors['submit_button'] if self.anonymize_state["enabled"] else self.colors['bg_light'])
        if self.log: self.log.info("You are now anonymous." if self.anonymize_state["enabled"] else "You are no longer anonymous.")
    def toggle_debug(self):
        global_settings.DEBUG_MODE["enabled"] = not global_settings.DEBUG_MODE["enabled"]
        self.debug_button.config(text="Debug On" if global_settings.DEBUG_MODE["enabled"] else "Debug Off",
                                 bg=self.colors['submit_button'] if global_settings.DEBUG_MODE["enabled"] else self.colors['bg_light'])
        if self.log: self.log.info("Debug mode enabled." if global_settings.DEBUG_MODE["enabled"] else "Debug mode disabled.")

    def _update_sound_controls(self):
        if getattr(self, "mute_button", None):
            icon = "🔇" if global_settings.is_muted else "🔊"
            mute_kwargs = {
                "text": icon,
                "fg": "#ffffff" if global_settings.is_muted else self.colors['text'],
                "bg": "#8A0000" if global_settings.is_muted else self.colors['bg_light'],
            }
            self.mute_button.config(**mute_kwargs)

        if getattr(self, "volume_slider", None):
            target_volume = self.sounds.prev_volume if self.sounds else global_settings.volume
            target_percent = int(round(max(0.0, min(1.0, target_volume)) * 100))

            self._updating_volume_slider = True
            try:
                self.volume_slider.set(target_percent)
            finally:
                self._updating_volume_slider = False

            if self.sounds:
                self.volume_slider.config(state=tk.NORMAL)
            else:
                self.volume_slider.config(state=tk.DISABLED)

    def toggle_mute(self):
        if not self.sounds:
            return
        global_settings.is_muted = not global_settings.is_muted
        self.sounds.apply_audio_state()
        self._update_sound_controls()
        if self.log:
            message = "Main Log, Audio muted" if global_settings.is_muted else "Main Log, Audio unmuted"
            self.log.info(message)

    def handle_volume(self, vol_str):
        if not self.sounds or self._updating_volume_slider:
            return
        try:
            self._pending_volume_percent = float(vol_str)
        except (TypeError, ValueError):
            self._pending_volume_percent = None

    def _commit_volume(self, _event=None):
        if not self.sounds or self._updating_volume_slider:
            return

        if self._pending_volume_percent is None:
            self._pending_volume_percent = float(self.volume_slider.get())

        percent = max(0.0, min(100.0, self._pending_volume_percent))
        self._pending_volume_percent = None

        normalized = max(0.0, min(1.0, percent / 100.0))
        self.sounds.set_volume(normalized)
        self._update_sound_controls()

        if self.log:
            self.log.info(f"Main Log, Volume set to {normalized:.2f}")
    def update_vehicle_status(self, text):
        label = getattr(self, 'vehicle_status_label', None)
        if label and label.winfo_exists():
            label.config(text=text, fg="#B0B0B0")

    def update_kills(self, count):
        label = getattr(self, 'session_kills_label', None)
        if label and label.winfo_exists():
            label.config(text=str(count), fg="#04B431")

    def update_deaths(self, count):
        label = getattr(self, 'session_deaths_label', None)
        if label and label.winfo_exists():
            label.config(text=str(count), fg="#f44747")

    def update_current_streak(self, count):
        label = getattr(self, 'curr_killstreak_label', None)
        if label and label.winfo_exists():
            label.config(text=str(count), fg="#FFA500")

    def update_max_streak(self, count):
        label = getattr(self, 'max_killstreak_label', None)
        if label and label.winfo_exists():
            label.config(text=str(count), fg="#00FF7F")

    def update_kd(self, ratio):
        label = getattr(self, 'kd_ratio_label', None)
        if label and label.winfo_exists():
            if isinstance(ratio, (int, float)):
                display_value = f"{ratio:.2f}"
            else:
                display_value = str(ratio)
            label.config(text=display_value, fg="#FFD700")

    def _reset_pvp_summary_data(self):
        self.pvp_summary_data = {mode: {"kills": {}, "deaths": {}} for mode in self.mode_display_names}

    def _create_summary_text_widget(self, parent, category):
        widget = tk.Text(
            parent,
            wrap=tk.WORD,
            height=3,
            state=tk.DISABLED,
            bg=self.colors['bg_mid'],
            fg=self.colors['text'],
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            cursor="arrow",
            borderwidth=0,
            highlightthickness=0,
        )
        widget.configure(spacing1=2, spacing3=2)

        if category == "kills":
            widget.tag_configure("kill_name", foreground="#32CD32", font=self.summary_fonts["name"])
            widget.tag_configure("kill_counter", foreground="#FFFFFF", font=self.summary_fonts["counter"])
        else:
            widget.tag_configure("death_name", foreground=self.colors['error'], font=self.summary_fonts["name"])
            widget.tag_configure("death_counter", foreground="#FFFFFF", font=self.summary_fonts["counter"])

        widget.tag_configure("placeholder", foreground=self.colors['text_dark'], font=self.summary_fonts["counter"])
        return widget

    def _initialize_star_citizen_summary_ui(self, parent):
        self.summary_fonts = {
            "name": font.Font(parent, family="Segoe UI", size=9, weight="bold"),
            "counter": font.Font(parent, family="Segoe UI", size=9),
        }

        self._reset_pvp_summary_data()
        self.star_citizen_summary_widgets = {}

        summary_container = tk.Frame(parent, bg=self.colors['bg_dark'])
        summary_container.pack(fill=tk.X, pady=(0, 8))

        for idx in range(len(self.mode_display_names)):
            summary_container.grid_columnconfigure(idx, weight=1)

        for column_index, mode_key in enumerate(self.mode_display_names.keys()):
            section_frame = tk.Frame(summary_container, bg=self.colors['bg_dark'])
            section_frame.grid(row=0, column=column_index, sticky="nsew", padx=4)

            header_row = tk.Frame(section_frame, bg=self.colors['bg_dark'])
            header_row.pack(fill=tk.X)

            title_label = tk.Label(
                header_row,
                text=self.mode_display_names[mode_key],
                font=("Segoe UI", 9, "bold"),
                fg="#FFFFFF",
                bg=self.colors['bg_dark'],
            )
            title_label.pack(side=tk.LEFT)

            clear_button = tk.Button(
                header_row,
                text="Clear",
                command=lambda m=mode_key: self._clear_summary_mode(m),
                font=("Segoe UI", 8, "bold"),
                bg=self.colors['bg_light'],
                fg="#FFFFFF",
                relief=tk.FLAT,
                padx=8,
                pady=2,
                activebackground=self.colors['accent'],
                activeforeground="#FFFFFF",
                cursor="hand2",
            )
            clear_button.pack(side=tk.RIGHT)

            kills_label = tk.Label(
                section_frame,
                text="You killed:",
                font=("Segoe UI", 9, "bold"),
                fg=self.colors['text_dark'],
                bg=self.colors['bg_dark'],
            )
            kills_label.pack(anchor="w", pady=(6, 0))

            kills_widget = self._create_summary_text_widget(section_frame, "kills")
            kills_widget.pack(fill=tk.X, pady=(2, 4))

            deaths_label = tk.Label(
                section_frame,
                text="Killed you:",
                font=("Segoe UI", 9, "bold"),
                fg=self.colors['text_dark'],
                bg=self.colors['bg_dark'],
            )
            deaths_label.pack(anchor="w", pady=(4, 0))

            deaths_widget = self._create_summary_text_widget(section_frame, "deaths")
            deaths_widget.pack(fill=tk.X, pady=(2, 4))

            self.star_citizen_summary_widgets[mode_key] = {
                "kills": kills_widget,
                "deaths": deaths_widget,
            }

            self._update_summary_display(mode_key)

    def _clear_summary_mode(self, mode_key):
        if mode_key not in self.pvp_summary_data:
            return
        self.pvp_summary_data[mode_key]["kills"].clear()
        self.pvp_summary_data[mode_key]["deaths"].clear()
        self._update_summary_display(mode_key)

    def _update_summary_display(self, mode_key, category=None):
        if mode_key not in self.star_citizen_summary_widgets:
            return

        categories = [category] if category else ("kills", "deaths")
        for cat in categories:
            widget = self.star_citizen_summary_widgets[mode_key].get(cat)
            if not widget or not widget.winfo_exists():
                continue

            widget.config(state=tk.NORMAL)
            widget.delete("1.0", tk.END)

            entries = self.pvp_summary_data.get(mode_key, {}).get(cat, {})
            if entries:
                name_tag = "kill_name" if cat == "kills" else "death_name"
                counter_tag = "kill_counter" if cat == "kills" else "death_counter"
                for index, (name, count) in enumerate(entries.items()):
                    if index > 0:
                        widget.insert(tk.END, "  ")
                    widget.insert(tk.END, name, (name_tag,))
                    if count > 1:
                        widget.insert(tk.END, f"[x{count}]", (counter_tag,))
            else:
                widget.insert(tk.END, "—", ("placeholder",))

            widget.config(state=tk.DISABLED)

    def _record_pvp_summary(self, mode_key, category, name):
        if not name:
            return

        normalized_name = name.strip()
        if not normalized_name:
            return

        if mode_key not in self.pvp_summary_data:
            self.pvp_summary_data[mode_key] = {"kills": {}, "deaths": {}}

        counts = self.pvp_summary_data[mode_key].setdefault(category, {})
        counts[normalized_name] = counts.get(normalized_name, 0) + 1
        self._update_summary_display(mode_key, category)

    def _normalize_mode_key(self, game_mode):
        normalized_mode = (game_mode or "").upper()
        if "SC_DEFAULT" in normalized_mode:
            return "PU"
        return "AC"

    def _configure_star_citizen_log_tags(self, widget):
        """Configure tags for the combined Star Citizen kill tracker."""
        bold_font = font.Font(widget, widget.cget("font"))
        bold_font.configure(weight="bold")

        widget.tag_configure("prefix", foreground=self.colors['text_dark'])
        widget.tag_configure("separator", foreground=self.colors['text_dark'])
        widget.tag_configure("kill_body", foreground=self.colors['submit_button'])
        widget.tag_configure("death_body", foreground=self.colors['error'])
        widget.tag_configure("siiin_death_body", foreground=self.colors['error'])
        widget.tag_configure("suicide_body", foreground=self.colors['text_dark'])
        widget.tag_configure("bold_name", font=bold_font, foreground="#FFFFFF")

    def _render_star_citizen_log(self):
        widget = self.star_citizen_log_widget
        if not widget or not widget.winfo_exists():
            return

        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        for entry in self.star_citizen_log_entries:
            body_tag = entry.get("body_tag")
            if not body_tag:
                body_tag = {
                    "kill": "kill_body",
                    "death": "death_body",
                }.get(entry["tag"], "suicide_body")

            widget.insert(tk.END, f"{entry['prefix']} ", ("prefix",))
            widget.insert(tk.END, entry["time"], ("prefix",))
            widget.insert(tk.END, " | ", ("separator",))

            for segment_text, segment_style in entry["segments"]:
                tags = [body_tag]
                if segment_style == "bold":
                    tags.append("bold_name")
                widget.insert(tk.END, segment_text, tuple(tags))

            widget.insert(tk.END, "\n")

        widget.config(state=tk.DISABLED)
        widget.see(tk.END)

    def log_mode_kill(self, game_mode, timestamp, description, tag, killer=None, victim=None, context=None):
        """Append a kill or death entry to the combined Star Citizen log and summary."""
        widget = self.star_citizen_log_widget
        if not widget or not widget.winfo_exists():
            return

        mode_key = self._normalize_mode_key(game_mode)
        prefix = "[PU]" if mode_key == "PU" else "[AC]"
        display_time = timestamp or datetime.now().strftime("%H:%M:%S")

        context_value = (context or (tag if tag else "")).lower()
        if not context_value:
            context_value = "pvp" if tag in {"kill", "death"} else tag
        if tag in {"kill", "death"} and context_value not in {"pvp", "environment", "collision", "suicide"}:
            context_value = "pvp"

        if tag == "suicide" and mode_key == "PU":
            return

        message_text = description or ""
        custom_body_tag = None

        if tag == "death":
            if context_value == "environment":
                message_text = "NPC/Game Environment"
                custom_body_tag = "death_body"
            elif context_value == "collision":
                message_text = "Collision"
                custom_body_tag = "death_body"

        segments = []
        lower_text = message_text.lower()

        if tag == "death" and context_value == "pvp" and " killed you" in lower_text:
            killed_you_index = lower_text.index(" killed you")
            killer_text = message_text[:killed_you_index].strip()
            remainder = message_text[killed_you_index:]

            segments.append((killer_text, "bold"))

            remainder_lower = remainder.lower()
            using_index = remainder_lower.find(" using ")
            if using_index != -1:
                killed_phrase = remainder[:using_index]
                weapon_text = remainder[using_index + len(" using "):].strip()
                segments.append((killed_phrase, None))
                if weapon_text:
                    segments.append((" using ", None))
                    segments.append((weapon_text, None))
            else:
                segments.append((remainder, None))

            custom_body_tag = "siiin_death_body"

        elif tag == "death" and context_value == "pvp" and lower_text.startswith("you got killed by "):
            details = message_text[len("You got killed by ") :]
            killer_text = details
            weapon_text = ""
            connector = ", using "
            if ", using " in details:
                killer_text, weapon_text = details.split(", using ", 1)
            elif " - using " in details:
                killer_text, weapon_text = details.split(" - using ", 1)
                connector = " - using "
            segments.append(("You got killed by ", None))
            segments.append((killer_text.strip(), "bold"))
            if weapon_text.strip():
                segments.append((connector, None))
                segments.append((weapon_text.strip(), None))
            custom_body_tag = "siiin_death_body"

        elif tag == "kill" and lower_text.startswith("you killed "):
            details = message_text[len("You killed ") :]
            victim_text = details.split(" with ")[0].strip()
            weapon_text = ""
            if " with " in details:
                _, weapon_text = details.split(" with ", 1)
                weapon_text = weapon_text.strip()
            segments.append(("You killed ", None))
            segments.append((victim_text, "bold"))
            if weapon_text:
                segments.append((" with ", None))
                segments.append((weapon_text, None))
        else:
            segments.append((message_text, None))

        entry = {
            "prefix": prefix,
            "time": display_time,
            "segments": segments,
            "tag": tag,
        }

        if custom_body_tag:
            entry["body_tag"] = custom_body_tag

        self.star_citizen_log_entries.append(entry)
        if len(self.star_citizen_log_entries) > 200:
            self.star_citizen_log_entries.pop(0)

        self._render_star_citizen_log()

        if context_value == "pvp":
            if tag == "kill":
                self._record_pvp_summary(mode_key, "kills", victim)
            elif tag == "death":
                self._record_pvp_summary(mode_key, "deaths", killer)

    def _load_and_populate_mappings(self):
        self.log.info("Loading ship and weapon mappings...")
        self.ship_map, self.weapon_map = mappings_parser.load_mappings()
        if not self.ship_map or not self.weapon_map:
            self.log.error("Failed to load mappings. Dropdowns will be empty.")
            messagebox.showerror("Mapping Error", "Could not load ship and weapon data from mappings.js. Please ensure the file exists and is correctly formatted.")
            return
        self.reverse_ship_map = {v: k for k, v in self.ship_map.items()}
        self.reverse_weapon_map = {v: k for k, v in self.weapon_map.items()}
        ship_game_names = sorted(self.reverse_ship_map.keys())
        weapon_game_names = sorted(self.reverse_weapon_map.keys())
        self.killer_ship_combo['values'] = ship_game_names
        self.victim_ship_combo['values'] = ship_game_names
        self.killer_weapon_combo['values'] = weapon_game_names
        self.log.success("Mappings loaded successfully. Star citizen Must be open to continue...")

    def _apply_injected_stat_update(self, outcome):
        parser = getattr(self, "log_parser", None)
        if parser:
            if outcome == "kill":
                parser.handle_player_kill()
            elif outcome == "death":
                parser.handle_player_death()
            return

        state = self._manual_stat_state
        if outcome == "kill":
            state["kills"] += 1
            state["curr_streak"] += 1
            if state["curr_streak"] > state["max_streak"]:
                state["max_streak"] = state["curr_streak"]
        elif outcome == "death":
            state["deaths"] += 1
            state["curr_streak"] = 0
        else:
            return

        self.update_kills(state["kills"])
        self.update_deaths(state["deaths"])
        self.update_current_streak(state["curr_streak"])
        self.update_max_streak(state["max_streak"])

        kills = state["kills"]
        deaths = state["deaths"]
        if kills == 0 and deaths == 0:
            kd_value = "--"
        elif deaths == 0:
            kd_value = "∞"
        else:
            kd_value = kills / deaths

        self.update_kd(kd_value)

    def handle_kill_injection(self):
        try:
            killer_h = self.killer_handle_entry.get()
            killer_s_game_name = self.killer_ship_combo.get()
            killer_w_game_name = self.killer_weapon_combo.get()
            victim_h = self.victim_handle_entry.get()
            victim_s_game_name = self.victim_ship_combo.get()
            game_mode_from_ui = self.injection_env_var.get()
            delivery_mode = self.injection_delivery_var.get() if self.injection_delivery_var else "online"
            post_online = delivery_mode == "online"

            if post_online and not (self.api and self.api.api_key.get("value")):
                if self.log:
                    self.log.error("Cannot inject kill online: API key not valid.")
                return

            if game_mode_from_ui == "PU":
                game_mode_for_server = "SC_Default"
            else:
                game_mode_for_server = "EA_FreeFlight"

            if not all([killer_h, killer_s_game_name, killer_w_game_name, victim_h, victim_s_game_name]):
                if self.log: self.log.error("All inject fields are required."); return

            killer_s_raw = self.reverse_ship_map.get(killer_s_game_name)
            killer_w_raw = self.reverse_weapon_map.get(killer_w_game_name)
            victim_s_raw = self.reverse_ship_map.get(victim_s_game_name)

            normalized_mode = (game_mode_for_server or "").upper()
            is_gameplay_mode = normalized_mode in {"SC_DEFAULT", "EA_FREEFLIGHT"}

            payload = {"result":"kill", "data": {
                        "player": killer_h, "victim": victim_h, "time": datetime.now().isoformat(),
                        "zone": victim_s_raw, "weapon": killer_w_raw,
                        "rsi_profile": f"https://robertsspaceindustries.com/citizens/{killer_h}",
                        "game_mode": game_mode_for_server, "client_ver": self.local_version,
                        "killers_ship": killer_s_raw,
                        "anonymize_state": self.anonymize_state.get("enabled", False)
                      }}

            if self.log:
                self.log.info(f"Injecting kill: {killer_h} -> {victim_h}")

            self_handle = None
            normalized_self = ""
            if self.api and getattr(self.api, "rsi_handle", None):
                self_handle = self.api.rsi_handle.get("current")
                normalized_self = (self_handle or "").strip().lower()

            killer_h_normalized = killer_h.strip().lower()
            victim_h_normalized = victim_h.strip().lower()
            is_self_killer = bool(normalized_self and killer_h_normalized == normalized_self)
            is_self_victim = bool(normalized_self and victim_h_normalized == normalized_self)
            is_self_involved = is_self_killer or is_self_victim

            if post_online:
                Thread(target=self.api.post_kill_event, args=(payload, "reportKill"), daemon=True).start()
            else:
                if self.log:
                    self.log.info("Test mode selected: Kill event prepared locally without contacting Servitor.")

            if is_self_involved:
                timestamp_display = datetime.now().strftime("%H:%M:%S")
                weapon_display = killer_w_game_name or "Unknown weapon"

                if is_self_victim:
                    death_message = f"{killer_h} killed you using {weapon_display}"
                    self.log_mode_kill(
                        game_mode_for_server,
                        timestamp_display,
                        death_message,
                        "death",
                        killer=killer_h,
                        victim=self_handle,
                        context="pvp",
                    )
                    if self.sounds:
                        self.sounds.play_death_sound()
                    self._apply_injected_stat_update("death")
                else:
                    self.log_mode_kill(
                        game_mode_for_server,
                        timestamp_display,
                        f"You killed {victim_h} with {weapon_display}",
                        "kill",
                        killer=self_handle,
                        victim=victim_h,
                        context="pvp",
                    )
                    if self.sounds:
                        self.sounds.play_kill_sound()
                    self._apply_injected_stat_update("kill")
            else:
                if self.log:
                    self.log.info(
                        "Kill log entry skipped: your handle was not involved in this injected event."
                    )

            if game_mode_for_server == "SC_Default":
                cleaned_victim_input = victim_h.strip().lower()
                for target_name, requirement in BOUNTY_TARGETS.items():
                    if cleaned_victim_input == target_name.lower():
                        if self.log:
                            self.log.success(
                                f"Bounty Test triggered for injected kill on {target_name}!"
                            )
                        if self.sounds:
                            self.sounds.play_bounty_sound()
                        self.display_bounty_event(
                            event_type="kill",
                            target=target_name,
                            requirement=requirement,
                            actor=killer_h
                        )
                        break
            
            self.killer_handle_entry.delete(0, tk.END)
            self.victim_handle_entry.delete(0, tk.END)

        except Exception as e:
            if self.log: self.log.error(f"Inject kill failed: {e}")

    def setup_gui(self, game_running):
        self.app = tk.Tk(); self.app.title(f"Voidledger v{self.local_version}"); self.app.configure(bg=self.colors['bg_dark']); self.app.resizable(False, False)
        self.kill_history_entries.clear()
        self.star_citizen_log_entries.clear()
        try:
            icon_path = os.path.join(getattr(sys, '_MEIPASS', '.'), 'static', 'images', 'voidveil.png')
            self.app.iconphoto(True, tk.PhotoImage(file=icon_path))
        except tk.TclError: print("Icon not found.")
        self._load_emoji_assets()
        main_frame = tk.Frame(self.app, bg=self.colors['bg_dark'], padx=10, pady=10); main_frame.pack(fill=tk.BOTH, expand=True)
        history_frame = tk.LabelFrame(
            main_frame,
            bg=self.colors['bg_dark'],
            fg=self.colors['gold'],
            font=("Segoe UI", 9, "bold"),
            relief=tk.GROOVE,
            labelanchor='nw',
            padx=6,
            pady=6
        )
        history_frame.pack(fill=tk.X, pady=(0, 8))

        history_label = tk.Label(
            history_frame,
            text="Continental Bounty",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['gold'],
            image=self.continental_history_badge_image,
            compound=tk.LEFT,
            padx=4
        )
        history_frame.configure(labelwidget=history_label)
        self.kill_history_widget = scrolledtext.ScrolledText(
            history_frame,
            wrap=tk.WORD,
            height=4,
            state=tk.DISABLED,
            bg=self.colors['bg_mid'],
            fg=self.colors['text'],
            font=("Consolas", 10),
            relief=tk.FLAT
        )
        self.kill_history_widget.pack(fill=tk.BOTH, expand=True)
        kill_history_bold = font.Font(self.kill_history_widget, self.kill_history_widget.cget("font"))
        kill_history_bold.configure(weight="bold")
        self.kill_history_widget.tag_configure("prefix", foreground=self.colors['text_dark'])
        self.kill_history_widget.tag_configure("separator", foreground=self.colors['text_dark'])
        self.kill_history_widget.tag_configure("kill_text", foreground=self.colors['submit_button'])
        self.kill_history_widget.tag_configure("bold_name", font=kill_history_bold)
        self.kill_history_widget.tag_configure("victim_name", foreground=self.colors['gold'], font=kill_history_bold)
        self.kill_history_widget.tag_configure("requirement_alert", foreground=self.colors['error'])

        star_citizen_frame = tk.LabelFrame(
            main_frame,
            bg=self.colors['bg_dark'],
            fg=self.colors['accent'],
            font=("Segoe UI", 9, "bold"),
            relief=tk.GROOVE,
            labelanchor='nw',
            padx=6,
            pady=6
        )
        star_citizen_frame.pack(fill=tk.X, pady=(0, 8))

        star_citizen_label = tk.Label(
            star_citizen_frame,
            text="Star Citizen Kill Log",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors['bg_dark'],
            fg="#FFFFFF",
            padx=4
        )
        star_citizen_frame.configure(labelwidget=star_citizen_label)

        stat_font = ("Segoe UI", 9, "bold")
        stats_header = tk.Frame(star_citizen_frame, bg=self.colors['bg_dark'])
        stats_header.pack(fill=tk.X, pady=(0, 8))

        stats_inner = tk.Frame(stats_header, bg=self.colors['bg_mid'], padx=6, pady=6)
        stats_inner.pack(fill=tk.X)

        for idx in range(5):
            stats_inner.grid_columnconfigure(idx, weight=1)

        def build_stat_display(parent, column, label_text, initial_value, value_color):
            container = tk.Frame(parent, bg=self.colors['bg_mid'])
            container.grid(row=0, column=column, sticky="w", padx=4)
            tk.Label(
                container,
                text=label_text,
                font=stat_font,
                bg=self.colors['bg_mid'],
                fg=self.colors['text_dark'],
            ).pack(side=tk.LEFT)
            value_label = tk.Label(
                container,
                text=initial_value,
                font=stat_font,
                bg=self.colors['bg_mid'],
                fg=value_color,
            )
            value_label.pack(side=tk.LEFT)
            return value_label

        self.session_kills_label = build_stat_display(
            stats_inner,
            0,
            "Total Session Kills:",
            "0",
            "#04B431",
        )

        self.session_deaths_label = build_stat_display(
            stats_inner,
            1,
            "Total Session Deaths:",
            "0",
            "#f44747",
        )

        self.kd_ratio_label = build_stat_display(
            stats_inner,
            2,
            "K/D Ratio:",
            "--",
            "#FFD700",
        )

        self.curr_killstreak_label = build_stat_display(
            stats_inner,
            3,
            "Current Kill Streak:",
            "0",
            "#FFA500",
        )

        self.max_killstreak_label = build_stat_display(
            stats_inner,
            4,
            "Max Kill Streak:",
            "0",
            "#00FF7F",
        )

        vehicle_container = tk.Frame(stats_inner, bg=self.colors['bg_mid'])
        vehicle_container.grid(row=1, column=0, columnspan=5, sticky="w", padx=4, pady=(6, 0))
        tk.Label(
            vehicle_container,
            text="Current Vehicle:",
            font=("Segoe UI", 9, "italic"),
            bg=self.colors['bg_mid'],
            fg=self.colors['text_dark'],
        ).pack(side=tk.LEFT)
        self.vehicle_status_label = tk.Label(
            vehicle_container,
            text="Inactive",
            font=("Segoe UI", 9, "italic"),
            bg=self.colors['bg_mid'],
            fg="#B0B0B0",
        )
        self.vehicle_status_label.pack(side=tk.LEFT)

        self._initialize_star_citizen_summary_ui(star_citizen_frame)

        self.star_citizen_log_widget = scrolledtext.ScrolledText(
            star_citizen_frame,
            wrap=tk.WORD,
            height=6,
            state=tk.DISABLED,
            bg=self.colors['bg_mid'],
            fg=self.colors['text'],
            font=("Consolas", 10),
            relief=tk.FLAT
        )
        self.star_citizen_log_widget.pack(fill=tk.BOTH, expand=True)
        self._configure_star_citizen_log_tags(self.star_citizen_log_widget)

        text_area = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, state=tk.DISABLED, bg=self.colors['bg_mid'], fg=self.colors['text'], font=("Consolas", 10), relief=tk.FLAT, height=12); text_area.pack(fill=tk.X, pady=(0, 10))
        self.log = AppLogger(text_area)
        self._flush_icon_warnings()
        features_frame = tk.LabelFrame(main_frame, bg=self.colors['bg_dark'], fg=self.colors['accent'], font=("Segoe UI", 9, "bold"), relief=tk.GROOVE, padx=8, pady=8)
        features_frame.pack(fill=tk.X, pady=(0, 10))

        features_label = tk.Label(
            features_frame,
            text="BlightVeil Tracker",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors['bg_dark'],
            fg="#A855F7",
            padx=4
        )
        features_frame.configure(labelwidget=features_label)

        api_frame = tk.Frame(features_frame, bg=self.colors['bg_dark'])
        api_frame.pack(fill=tk.X)
        tk.Label(api_frame, text="BlightVeil Servitor | Insert key →", font=("Segoe UI", 9), bg=self.colors['bg_dark'], fg=self.colors['text_dark']).pack(side=tk.LEFT, padx=(0, 5))
        self.key_entry = tk.Entry(api_frame, font=("Segoe UI", 9), width=34, bg=self.colors['bg_light'], fg=self.colors['text'], relief=tk.FLAT, insertbackground=self.colors['text'])
        self.key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(api_frame, text="Load Key", command=lambda: self.api.load_activate_key(), bg=self.colors['button'], fg='#FFFFFF', relief=tk.FLAT, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(5, 0))

        status_frame = tk.Frame(features_frame, bg=self.colors['bg_dark'])
        status_frame.pack(fill=tk.X, pady=5)
        link_font = font.Font(family="Segoe UI", size=9, underline=False)
        generate_key_link = tk.Label(status_frame, text="Generate Key 🗝", fg=self.colors['accent'], font=link_font, cursor="hand2", bg=self.colors['bg_dark'])
        generate_key_link.pack(side=tk.LEFT)
        generate_key_link.bind("<Button-1>", self.open_discord_link)
        self.api_status_label = tk.Label(status_frame, text="Key Status: Invalid", fg=self.colors['error'], font=("Segoe UI", 9, "italic"), bg=self.colors['bg_dark'])
        self.api_status_label.pack(side=tk.RIGHT)

        inject_frame = tk.Frame(features_frame, bg=self.colors['bg_dark'])
        inject_frame.pack(fill=tk.X, pady=(5, 10))

        entry_style = {'bg': self.colors['bg_light'], 'fg': self.colors['text'], 'relief': tk.FLAT, 'font': ("Segoe UI", 9)}
        label_style = {'bg': self.colors['bg_dark'], 'fg': self.colors['text_dark'], 'font': ("Segoe UI", 8)}

        style = ttk.Style(self.app)
        style.theme_use('clam')
        style.configure(
            'Blightveil.TCombobox',
            fieldbackground=self.colors['bg_light'],
            background=self.colors['bg_light'],
            foreground=self.colors['text'],
            arrowcolor=self.colors['text'],
            selectbackground=self.colors['bg_light'],
            selectforeground=self.colors['text'],
            bordercolor=self.colors['bg_dark'],
            lightcolor=self.colors['bg_dark'],
            darkcolor=self.colors['bg_dark'],
            padding=4
        )
        style.map(
            'Blightveil.TCombobox',
            fieldbackground=[('readonly', self.colors['bg_light'])],
            bordercolor=[('focus', self.colors['bg_dark']), ('!focus', self.colors['bg_dark'])],
            lightcolor=[('focus', self.blightveil_theme['hover']), ('!focus', self.colors['bg_dark'])]
        )

        tk.Label(inject_frame, text="Killer Handle", **label_style).grid(row=0, column=0, sticky='w')
        self.killer_handle_entry = tk.Entry(inject_frame, **entry_style)
        self.killer_handle_entry.grid(row=1, column=0, sticky='ew', padx=(0,5))

        tk.Label(inject_frame, text="Killer Ship", **label_style).grid(row=0, column=1, sticky='w')
        self.killer_ship_combo = ttk.Combobox(inject_frame, state='readonly', font=("Segoe UI", 9), style='Blightveil.TCombobox')
        self.killer_ship_combo.grid(row=1, column=1, sticky='ew', padx=(0,5))

        tk.Label(inject_frame, text="Killer Weapon", **label_style).grid(row=0, column=2, sticky='w')
        self.killer_weapon_combo = ttk.Combobox(inject_frame, state='readonly', font=("Segoe UI", 9), style='Blightveil.TCombobox')
        self.killer_weapon_combo.grid(row=1, column=2, sticky='ew')

        tk.Label(inject_frame, text="Victim Handle", **label_style).grid(row=2, column=0, sticky='w', pady=(5,0))
        self.victim_handle_entry = tk.Entry(inject_frame, **entry_style)
        self.victim_handle_entry.grid(row=3, column=0, sticky='ew', padx=(0,5))

        tk.Label(inject_frame, text="Victim Ship", **label_style).grid(row=2, column=1, sticky='w', pady=(5,0))
        self.victim_ship_combo = ttk.Combobox(inject_frame, state='readonly', font=("Segoe UI", 9), style='Blightveil.TCombobox')
        self.victim_ship_combo.grid(row=3, column=1, sticky='ew', padx=(0,5))
        
        self.injection_env_var = tk.StringVar(value="PU")
        self.injection_delivery_var = tk.StringVar(value="online")
        radio_style = {"bg":self.colors['bg_dark'],"fg":self.colors['text_dark'],"selectcolor":self.colors['bg_light'],"activebackground":self.colors['bg_dark'],"font":("Segoe UI",8),"highlightthickness":0}

        env_mode_frame = tk.Frame(inject_frame, bg=self.colors['bg_dark'])
        env_mode_frame.grid(row=3, column=2, sticky='ew')
        env_mode_frame.grid_columnconfigure((0, 1), weight=1)

        env_frame = tk.Frame(env_mode_frame, bg=self.colors['bg_dark'])
        env_frame.grid(row=0, column=0, sticky='w', padx=(0, 5))
        tk.Radiobutton(env_frame, text="PU", variable=self.injection_env_var, value="PU", **radio_style).pack(side=tk.LEFT, expand=True)
        tk.Radiobutton(env_frame, text="AC", variable=self.injection_env_var, value="AC", **radio_style).pack(side=tk.LEFT, expand=True)

        delivery_frame = tk.Frame(env_mode_frame, bg=self.colors['bg_dark'])
        delivery_frame.grid(row=0, column=1, sticky='e')
        tk.Radiobutton(delivery_frame, text="Send it", variable=self.injection_delivery_var, value="online", **radio_style).pack(side=tk.LEFT, expand=True)
        tk.Radiobutton(delivery_frame, text="Test", variable=self.injection_delivery_var, value="offline", **radio_style).pack(side=tk.LEFT, expand=True)
        tk.Button(inject_frame, text="Submit Kill", command=self.handle_kill_injection, bg=self.colors['submit_button'], fg='#FFFFFF', relief=tk.FLAT, font=("Segoe UI", 9, "bold")).grid(row=2, column=2, sticky='ew', pady=(5,0))
        inject_frame.grid_columnconfigure((0,1,2), weight=1)

        bottom_frame = tk.Frame(features_frame, bg=self.colors['bg_dark'])
        bottom_frame.pack(fill=tk.X)
        button_style = {'relief': tk.FLAT, 'font': ("Segoe UI", 9, "bold"), 'fg': '#FFFFFF'}
        tk.Button(bottom_frame, text="Commander Mode", command=lambda: self.cm.setup_commander_mode() if self.cm else None, bg=self.colors['button'], **button_style).pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 5))
        self.anonymize_button = tk.Button(bottom_frame, text="Anonymity Off", command=self.toggle_anonymize, **button_style, bg=self.colors['bg_light'], width=9); self.anonymize_button.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(5, 0))

        footer_frame = tk.Frame(main_frame, bg=self.colors['bg_dark'])
        footer_frame.pack(fill=tk.X, pady=(5, 0))
        tk.Label(footer_frame, text="© BlightVeil / SIIIN - Work in progress", font=("Segoe UI", 10, "italic"), bg=self.colors['bg_dark'], fg=self.colors['text_dark']).pack(side=tk.LEFT, pady=(5, 0))

        controls_frame = tk.Frame(footer_frame, bg=self.colors['bg_dark'])
        controls_frame.pack(side=tk.RIGHT)
        self.debug_button = tk.Button(controls_frame, text="Debug Off", command=self.toggle_debug, **button_style, bg=self.colors['bg_light'], width=9)
        self.debug_button.pack(side=tk.LEFT, padx=(0, 8), pady=(5, 0))

        volume_frame = tk.Frame(controls_frame, bg=self.colors['bg_dark'])
        volume_frame.pack(side=tk.LEFT, pady=(5, 0))
        self.mute_button = tk.Button(
            volume_frame,
            text="🔊",
            command=self.toggle_mute,
            width=2,
            bg=self.colors['bg_light'],
            fg=self.colors['text'],
            relief=tk.FLAT,
        )
        self.mute_button.pack(side=tk.LEFT, padx=(0, 5))
        self.volume_slider = tk.Scale(
            volume_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            command=self.handle_volume,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            troughcolor=self.colors['bg_light'],
            highlightthickness=0,
            relief=tk.FLAT,
            sliderrelief=tk.FLAT,
            showvalue=0,
            length=60,
            state=tk.DISABLED,
        )
        self.volume_slider.pack(side=tk.LEFT)
        for sequence in (
            "<ButtonRelease-1>",
            "<KeyRelease-Left>",
            "<KeyRelease-Right>",
            "<KeyRelease-Up>",
            "<KeyRelease-Down>",
        ):
            self.volume_slider.bind(sequence, self._commit_volume)
        self._update_sound_controls()

        Thread(target=self._load_and_populate_mappings, daemon=True).start()

        self.app.update_idletasks()
        current_width = self.app.winfo_width()
        current_height = self.app.winfo_height()
        if current_width > 0 and current_height > 0:
            reduced_width = max(600, int(current_width * 0.75))
            self.app.geometry(f"{reduced_width}x{current_height}")
