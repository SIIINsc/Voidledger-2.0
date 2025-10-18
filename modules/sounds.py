from time import sleep
from random import choice
from os import listdir, path
from pathlib import Path
import pygame

# Import kill tracker modules
import modules.helpers as Helpers
import global_settings

class Sounds():
    """Sounds module for the Kill Tracker."""

    def __init__(self, cfg_handler):
        self.log = None
        self.cfg_handler = cfg_handler
        # --- CHANGE: We now only need one path for the sounds directory ---
        self.sounds_dir = None
        self.prev_volume = max(0.0, min(1.0, float(global_settings.volume)))
        pygame.mixer.init()
        pygame.mixer.music.set_volume(0.0 if global_settings.is_muted else self.prev_volume)
        self.gui = None

    def _debug_logs_enabled(self) -> bool:
        return bool(self.log and global_settings.DEBUG_MODE.get("enabled"))

    def _play_sound_file(self, filename: str, not_found_message: str) -> None:
        if not self.sounds_dir:
            if self.log:
                self.log.error("Sounds directory not set, cannot play sounds.")
            return

        sound_path = self.sounds_dir / filename
        if not sound_path.exists():
            fallback_path = Path(Helpers.resource_path("sounds")) / filename
            if fallback_path.exists():
                sound_path = fallback_path

        if sound_path.exists():
            if global_settings.is_muted or global_settings.volume <= 0.0:
                return

            try:
                if self._debug_logs_enabled():
                    self.log.debug(f"Playing sound: {sound_path.name}")
                sound = pygame.mixer.Sound(str(sound_path))
                sound.set_volume(global_settings.volume)
                sound.play()
            except Exception as e:
                if self.log:
                    self.log.error(f"When playing sound '{filename}': {e.__class__.__name__} {e}")
        else:
            if self.log:
                self.log.warning(not_found_message)

    def play_bounty_sound(self):
        """Play the ka-ching sound for a Continental bounty kill."""
        self._play_sound_file(
            "ka-ching.mp3",
            "Bounty sound file 'ka-ching.mp3' not found in bundled sounds.",
        )

    def _play_hitmarker(self) -> None:
        self._play_sound_file(
            "COD_hitmarker.wav",
            "Kill sound file 'COD_hitmarker.wav' not found in bundled sounds.",
        )

    def play_injected_kill_sound(self) -> None:
        """Play the hitmarker sound for injected kills."""
        self._play_hitmarker()

    def play_kill_sound(self) -> None:
        """Play the hitmarker for gameplay and injected kills alike."""
        self._play_hitmarker()

    def play_death_sound(self) -> None:
        """Play the punch sound when the player dies."""
        self._play_sound_file(
            "punch.mp3",
            "Death sound file 'punch.mp3' not found in bundled sounds.",
        )

    def load_sound_settings(self) -> None:
        """Load sound settings from cfg."""
        try:
            volume_dict = self.cfg_handler.cfg_dict.get("volume", {})
            global_settings.is_muted = bool(volume_dict.get("is_muted", False))
            level = float(volume_dict.get("level", global_settings.volume))
            level = max(0.0, min(1.0, level))
            self.prev_volume = level
            global_settings.volume = level
            self.apply_audio_state()

            if self._debug_logs_enabled():
                if global_settings.is_muted:
                    self.log.info("Sound volume muted.")
                else:
                    self.log.info(f"Sound volume set to {global_settings.volume * 100:.0f}%")
        except Exception as e:
            if self.log:
                self.log.warning(f"load_sound_settings(): {e.__class__.__name__} {e}")

    def set_volume(self, volume: float) -> None:
        """Set the playback volume."""
        try:
            clamped_volume = max(0.0, min(1.0, float(volume)))
            self.prev_volume = clamped_volume
            global_settings.volume = clamped_volume
            self.apply_audio_state()
        except Exception as e:
            if self.log:
                self.log.error(f"set_volume(): {e.__class__.__name__} {e}")

    def apply_audio_state(self) -> None:
        """Apply the current global mute and volume settings to the mixer and cfg."""
        try:
            effective_volume = 0.0 if global_settings.is_muted else global_settings.volume
            pygame.mixer.music.set_volume(effective_volume)

            volume_cfg = self.cfg_handler.cfg_dict.setdefault(
                "volume",
                {"level": self.prev_volume, "is_muted": global_settings.is_muted},
            )
            volume_cfg["level"] = self.prev_volume
            volume_cfg["is_muted"] = global_settings.is_muted

            if self.gui and hasattr(self.gui, "_update_sound_controls"):
                try:
                    self.gui._update_sound_controls()
                except Exception:
                    pass

            if self._debug_logs_enabled():
                if global_settings.is_muted:
                    self.log.info("Sound volume muted.")
                else:
                    self.log.info(f"Sound volume set to {effective_volume * 100:.0f}%")
        except Exception as e:
            if self.log:
                self.log.error(f"apply_audio_state(): {e.__class__.__name__} {e}")

    # --- CHANGE: Simplified setup to only point to bundled sounds ---
    def setup_sounds(self) -> None:
        """Setup the sounds module."""
        try:
            # Set the path to the bundled sounds directory. Prefer the new consolidated
            # "sounds" folder, but gracefully fall back to the legacy "static/sounds"
            # layout if it still exists inside an older bundle.
            candidate_dirs = [
                Path(Helpers.resource_path("sounds")),
                Path(Helpers.resource_path("static/sounds")),
            ]

            for candidate in candidate_dirs:
                if candidate.exists():
                    self.sounds_dir = candidate
                    break

            if not self.sounds_dir:
                self.log.error("setup_sounds(): Unable to locate a bundled sounds directory.")
                return

            sound_files = listdir(str(self.sounds_dir)) if path.exists(str(self.sounds_dir)) else []
            self.log.info(f"Loading sounds from executable bundle: {sound_files}")
        except Exception as e:
            self.log.error(f"setup_sounds(): {e.__class__.__name__} {e}")

    # --- CHANGE: Removed create_sounds_dir and copy_sounds functions entirely ---

    def play_random_sound(self) -> None:
        """Play a random sound from the sounds folder."""
        # --- CHANGE: Reads from the internal self.sounds_dir ---
        sounds = list(self.sounds_dir.glob('**/*.wav')) if self.sounds_dir else []
        if sounds:
            sound_to_play = choice(sounds)
            try:
                if global_settings.is_muted or global_settings.volume <= 0.0:
                    return
                if self._debug_logs_enabled():
                    self.log.debug(f"Playing sound: {sound_to_play.name}")
                sound = pygame.mixer.Sound(str(sound_to_play))
                sound.set_volume(global_settings.volume)
                sound.play()
                sleep(sound.get_length())
            except Exception as e:
                self.log.error(f"When playing sound {sound_to_play}: {e.__class__.__name__} {e}")
        else:
            self.log.error("No .wav sound files found in bundle.")
