"""Utilities for detecting Continental bounty interactions in the Star Citizen log."""
from __future__ import annotations

import re
from collections import deque
from typing import Deque, Dict, Iterable, Optional, Tuple

from modules.bounty_list import BOUNTY_TARGETS


class BountyTracker:
    """Detect bounty-related interactions from Star Citizen log lines."""

    # Heuristic patterns that have proven reliable in the public game.log format.
    _LOCK_PATTERNS: Tuple[re.Pattern[str], ...] = (
        re.compile(r"Lock(?:ed|ing)?(?: target)? ['\"](?P<target>[A-Za-z0-9_\-]+)", re.IGNORECASE),
        re.compile(r"Target lock .*?['\"](?P<target>[A-Za-z0-9_\-]+)", re.IGNORECASE),
        re.compile(r"Radar contact .*?state=(?:Locked|Locking).*?['\"](?P<target>[A-Za-z0-9_\-]+)", re.IGNORECASE),
    )

    _SCAN_PATTERNS: Tuple[re.Pattern[str], ...] = (
        re.compile(r"Scan(?:ned|ning)?.*?['\"](?P<target>[A-Za-z0-9_\-]+)", re.IGNORECASE),
        re.compile(r"Scan (?:complete|success|result).*?['\"](?P<target>[A-Za-z0-9_\-]+)", re.IGNORECASE),
    )

    _DETECT_PATTERNS: Tuple[re.Pattern[str], ...] = (
        re.compile(r"Detect(?:ed|ing).*?['\"](?P<target>[A-Za-z0-9_\-]+)", re.IGNORECASE),
        re.compile(r"Tracking contact .*?['\"](?P<target>[A-Za-z0-9_\-]+)", re.IGNORECASE),
    )

    def __init__(self, gui, sounds) -> None:
        self._gui = gui
        self._sounds = sounds
        self._logger = None
        self._bounties: Dict[str, Tuple[str, str]] = {
            handle.lower(): (handle, requirement or "")
            for handle, requirement in BOUNTY_TARGETS.items()
        }
        # Track recently reported events so we do not spam duplicate notifications
        self._recent_events: Deque[Tuple[str, str, str]] = deque(maxlen=128)
        self._recent_keys = set()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def set_logger(self, logger) -> None:
        """Attach a logger instance once it exists."""
        self._logger = logger

    def inspect_line(self, line: str) -> None:
        """Inspect a raw log line for passive bounty interactions."""
        lowered = line.lower()
        # Quick keyword filters to avoid running regex on irrelevant lines
        if "lock" in lowered:
            self._try_patterns(line, "lock", self._LOCK_PATTERNS)
        if "scan" in lowered:
            self._try_patterns(line, "scan", self._SCAN_PATTERNS)
        if any(trigger in lowered for trigger in ("detect", "tracking", "radar contact")):
            self._try_patterns(line, "detect", self._DETECT_PATTERNS)

    def handle_kill(self, killer: str, victim: str, weapon: Optional[str] = None, raw_line: str = "") -> None:
        """Handle confirmed kill events reported elsewhere in the parser."""
        normalized = self._normalize_handle(victim)
        if normalized not in self._bounties:
            return
        canonical, requirement = self._bounties[normalized]
        message = f"Continental bounty kill on {canonical} by {killer}."
        if requirement:
            message += f" Requirement: {requirement}"
        self._notify(
            event_type="kill",
            target_key=normalized,
            message=message,
            actor=killer,
            raw_line=raw_line or victim,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _try_patterns(
        self,
        line: str,
        event_type: str,
        patterns: Iterable[re.Pattern[str]],
    ) -> None:
        for pattern in patterns:
            match = pattern.search(line)
            if not match:
                continue
            raw_handle = match.group("target") if "target" in match.groupdict() else None
            if not raw_handle:
                continue
            normalized = self._normalize_handle(raw_handle)
            if normalized not in self._bounties:
                continue
            canonical, requirement_text = self._bounties[normalized]
            message = f"Continental bounty {event_type} on {canonical} detected."
            if requirement_text:
                message += f" Requirement: {requirement_text}"
            self._notify(event_type, normalized, message, raw_line=line)
            break

    def _notify(
        self,
        event_type: str,
        target_key: str,
        message: str,
        actor: Optional[str] = None,
        raw_line: str = "",
    ) -> None:
        canonical, requirement = self._bounties[target_key]
        key = (event_type, canonical, raw_line.strip())
        if not self._remember_event(key):
            return
        if self._logger:
            if event_type == "kill":
                self._logger.success(message)
            else:
                self._logger.info(message)
        if self._sounds:
            try:
                self._sounds.play_bounty_sound()
            except Exception:
                # Sound playback should never break the parser flow
                pass
        if hasattr(self._gui, "display_bounty_event"):
            self._gui.display_bounty_event(
                event_type=event_type,
                target=canonical,
                requirement=requirement,
                actor=actor,
            )

    def _remember_event(self, key: Tuple[str, str, str]) -> bool:
        if key in self._recent_keys:
            return False
        self._recent_events.append(key)
        self._recent_keys.add(key)
        while len(self._recent_events) > self._recent_events.maxlen:
            old_key = self._recent_events.popleft()
            self._recent_keys.discard(old_key)
        return True

    @staticmethod
    def _normalize_handle(handle: str) -> str:
        cleaned = handle.strip().strip("'\"")
        if "[" in cleaned:
            cleaned = cleaned.split("[", 1)[0]
        return cleaned.lower()

