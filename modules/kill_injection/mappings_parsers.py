# features/kill_injection/mappings_parser.py

import re
import json
import os

def parse_js_object(js_string):
    """
    Parses a JavaScript object literal string into a Python dictionary.
    """
    # Remove single-line comments
    js_string = re.sub(r'//.*', '', js_string)
    # Add quotes around unquoted keys to make it valid JSON
    # This handles keys at the start of the object, or after a comma/whitespace
    js_string = re.sub(r'([{\s,])(\w+)(:)', r'\1"\2"\3', js_string)
    return json.loads(js_string)

def load_mappings():
    """
    Loads ship and weapon mappings from mappings.js.
    """
    # Construct the path to mappings.js relative to this file
    # Assumes your mappings.js is in the root of the 'voidledgerfinal' directory
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        mappings_file_path = os.path.join(base_path, '..', '..', 'mappings.js')
        
        with open(mappings_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Could not find mappings.js at the expected path: {mappings_file_path}")

    # Extract the weaponMapping and shipMapping objects using regex
    weapon_match = re.search(r'const\s+weaponMapping\s*=\s*({.*?});', content, re.DOTALL)
    ship_match = re.search(r'const\s+shipMapping\s*=\s*({.*?});', content, re.DOTALL)

    if not weapon_match or not ship_match:
        raise ValueError("Could not find weaponMapping or shipMapping objects in mappings.js")

    weapon_map_str = weapon_match.group(1)
    ship_map_str = ship_match.group(1)

    weapons = parse_js_object(weapon_map_str)
    ships = parse_js_object(ship_map_str)

    return ships, weapons