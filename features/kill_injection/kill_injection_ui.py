# features/kill_injection/kill_injection_ui.py

import tkinter as tk
from tkinter import ttk, messagebox
import datetime

class KillInjectionFrame(ttk.Frame):
    def __init__(self, parent, api_client, ship_mapping, weapon_mapping, **kwargs):
        super().__init__(parent, **kwargs)
        self.api_client = api_client
        self.ship_mapping = ship_mapping
        self.weapon_mapping = weapon_mapping
        
        self.reverse_ship_map = {v: k for k, v in self.ship_mapping.items()}
        self.reverse_weapon_map = {v: k for k, v in self.weapon_mapping.items()}

        self.grid_columnconfigure(1, weight=1)
        self.create_widgets()

    def create_widgets(self):
        killer_frame = ttk.LabelFrame(self, text="Killer Details", padding=(10, 5))
        killer_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        killer_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(killer_frame, text="Killer Ship:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.killer_ship_combo = ttk.Combobox(killer_frame, state="readonly", width=40)
        self.killer_ship_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(killer_frame, text="Killer Weapon:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.killer_weapon_combo = ttk.Combobox(killer_frame, state="readonly", width=40)
        self.killer_weapon_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        victim_frame = ttk.LabelFrame(self, text="Victim Details", padding=(10, 5))
        victim_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        victim_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(victim_frame, text="Victim Ship/Zone:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.victim_ship_combo = ttk.Combobox(victim_frame, state="readonly", width=40)
        self.victim_ship_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        submit_button = ttk.Button(self, text="Inject Kill", command=self._inject_kill)
        submit_button.grid(row=2, column=0, columnspan=2, pady=10)

        self.populate_dropdowns()

    def populate_dropdowns(self):
        ship_names = sorted(self.reverse_ship_map.keys())
        weapon_names = sorted(self.reverse_weapon_map.keys())
        
        self.killer_ship_combo['values'] = ship_names
        self.victim_ship_combo['values'] = ship_names
        self.killer_weapon_combo['values'] = weapon_names

        if ship_names:
            self.killer_ship_combo.current(0)
            self.victim_ship_combo.current(0)
        if weapon_names:
            self.killer_weapon_combo.current(0)
            
    def _inject_kill(self):
        killer_ship_display = self.killer_ship_combo.get()
        killer_weapon_display = self.killer_weapon_combo.get()
        victim_ship_display = self.victim_ship_combo.get()

        if not all([killer_ship_display, killer_weapon_display, victim_ship_display]):
            messagebox.showerror("Error", "All fields are required.")
            return

        killer_ship_raw = self.reverse_ship_map.get(killer_ship_display)
        killer_weapon_raw = self.reverse_weapon_map.get(killer_weapon_display)
        victim_ship_raw = self.reverse_ship_map.get(victim_ship_display)

        payload = {
            "event": "kill",
            "victimName": "Manual Injection",
            "victimShip": victim_ship_raw,
            "killerName": "Tracker Operator",
            "killerShip": killer_ship_raw,
            "weapon": killer_weapon_raw,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }
        
        try:
            self.api_client.send_event(payload)
            messagebox.showinfo("Success", "Kill event injected successfully.")
        except Exception as e:
            messagebox.showerror("Injection Failed", f"An error occurred: {e}")
            print(f"[ERROR] Kill Injection Failed: {e}")