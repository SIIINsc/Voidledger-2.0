# modules/mappings_parser.py

import re
import json
import os
import sys

# --- NEW: Filter lists containing only the RAW names you want to show ---
# The code will only allow items with these keys to appear in the dropdowns.

ALLOWED_WEAPON_KEYS = {
    "KLWE_MassDriver_S10", "HRST_LaserBeam_Bespoke", "RSI_Bespoke_BallisticCannon_A",
    "KLWE_LaserRepeater_S1", "KLWE_LaserRepeater_S2", "KLWE_LaserRepeater_S3",
    "KLWE_LaserRepeater_S4", "KLWE_LaserRepeater_S5", "KLWE_LaserRepeater_S6",
    "NONE_LaserRepeater_S1", "NONE_LaserRepeater_S2", "NONE_LaserRepeater_S3",
    "HRST_LaserRepeater_S1", "HRST_LaserRepeater_S2", "HRST_LaserRepeater_S3",
    "HRST_LaserRepeater_S4", "HRST_LaserRepeater_S5", "HRST_LaserRepeater_S6",
    "MXOX_NeutronRepeater_S1", "MXOX_NeutronRepeater_S2", "MXOX_NeutronRepeater_S3",
    "Krig_BallisticGatling_Bespoke_S4", "KRON_LaserCannon_S3", "AMRS_LaserCannon_S1",
    "AMRS_LaserCannon_S2", "AMRS_LaserCannon_S3", "AMRS_LaserCannon_S4",
    "AMRS_LaserCannon_S5", "AMRS_LaserCannon_S6", "APAR_MassDriver_S2",
    "BEHR_BallisticGatling_S4", "BEHR_BallisticGatling_S5", "BEHR_BallisticGatling_S6",
    "BEHR_LaserCannon_S3", "BEHR_LaserCannon_S4", "BEHR_LaserCannon_S5",
    "BEHR_LaserCannon_SF7E_S7", "ESPR_BallisticCannon_S3", "ESPR_BallisticCannon_S4",
    "ESPR_BallisticCannon_S5", "GATS_BallisticGatling_S3", "GATS_BallisticCannon_S3", # Note: Corrected the key with a space
    "BEHR_BallisticGatling_Hornet_Bespoke", "APAR_BallisticGatling_S4",
    "VNCL_LaserCannon_S2", "VNCL_PlasmaCannon_S3", "VNCL_PlasmaCannon_S5"
}

ALLOWED_SHIP_KEYS = {
    "AEGS_Avenger_Stalker", "AEGS_Avenger_Titan", "AEGS_Eclipse", "AEGS_Gladius",
    "AEGS_Gladius_PIR", "AEGS_Sabre", "AEGS_Sabre_Comet", "AEGS_Sabre_Firebird",
    "AEGS_Sabre_Raven", "AEGS_Vanguard_Harbinger", "AEGS_Vanguard_Sentinel",
    "AEGS_Vanguard_Hoplite", "ANVL_Arrow", "ANVL_Ballista", "ANVL_Hornet_F7A_Mk1",
    "ANVL_Hornet_F7CM", "ANVL_Hornet_F7C_Mk2", "ANVL_Hornet_F7A_Mk2",
    "ANVL_Lightning_F8C", "ANVL_Gladiator", "ANVL_Hawk", "ANVL_Hurricane",
    "XIAN_Scout", "BANU_Defender", "CNOU_Mustang_Alpha", "CNOU_Mustang_Delta",
    "CRUS_Starfighter_Inferno", "CRUS_Starfighter_Ion", "CRUS_Starfighter_Ino",
    "DRAK_Buccaneer", "ESPR_Talon", "VNCL_Glaive", "KRIG_P72_Archimedes",
    "KRIG_L21_Wolf", "MISC_Fury", "MRAI_Guardian", "MISC_Razor_EX", "ORIG_m50",
    "RSI_Aurora_MR", "RSI_Polaris", "RSI_Scorpius", "RSI_Meteor", "VNCL_Scythe",
    "VNCL_Blade"
}


def parse_js_object(js_string):
    js_string = re.sub(r'//.*', '', js_string)
    js_string = js_string.strip()
    if js_string.endswith(','):
        js_string = js_string[:-1]
    
    js_string = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', js_string)
    
    try:
        return json.loads(js_string)
    except json.JSONDecodeError as e:
        print(f"JSON Parsing Error: {e}")
        error_pos = e.pos
        start = max(0, error_pos - 30)
        end = min(len(js_string), error_pos + 30)
        print(f"Problematic section: ...{js_string[start:end]}...")
        return {}

def load_mappings():
    """
    Loads ship and weapon mappings from mappings.js, then filters them
    to only include the items approved for the injection UI.
    """
    try:
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
            mappings_file_path = os.path.join(base_path, 'mappings.js')
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            mappings_file_path = os.path.join(base_path, '..', 'mappings.js')

        with open(mappings_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: Could not find mappings.js at the expected path: {mappings_file_path}")
        return {}, {}

    weapon_match = re.search(r'const\s+weaponMapping\s*=\s*({.*?});', content, re.DOTALL)
    ship_match = re.search(r'const\s+shipMapping\s*=\s*({.*?});', content, re.DOTALL)

    if not weapon_match or not ship_match:
        print("ERROR: Could not find weaponMapping or shipMapping objects in mappings.js")
        return {}, {}

    full_ships_map = parse_js_object(ship_match.group(1))
    full_weapons_map = parse_js_object(weapon_match.group(1))

    # --- CHANGE: Filter the full maps down to the allowed keys ---
    filtered_ships = {key: value for key, value in full_ships_map.items() if key in ALLOWED_SHIP_KEYS}
    filtered_weapons = {key: value for key, value in full_weapons_map.items() if key in ALLOWED_WEAPON_KEYS}

    return filtered_ships, filtered_weapons