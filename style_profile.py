"""
style_profile.py

Small local storage helpers for remembered FitFindr style preferences.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path


PROFILE_FIELDS = [
    "preferred_colors",
    "preferred_styles",
    "preferred_fits",
    "preferred_shoes",
    "preferred_bottoms",
    "preferred_layers",
]

STYLE_PROFILE_PATH = (
    Path(__file__).resolve().parent / "data" / "style_profile.local.json"
)

SUPPORTED_TERMS = {
    "preferred_colors": [
        "black",
        "white",
        "gray",
        "grey",
        "cream",
        "beige",
        "brown",
        "blue",
        "red",
        "green",
        "neutral",
        "earth tones",
        "pastel",
    ],
    "preferred_styles": [
        "streetwear",
        "grunge",
        "minimal",
        "vintage",
        "preppy",
        "casual",
        "sporty",
        "classic",
        "y2k",
        "boho",
    ],
    "preferred_fits": [
        "oversized",
        "baggy",
        "relaxed",
        "fitted",
        "slim",
        "cropped",
        "wide leg",
    ],
    "preferred_shoes": [
        "chunky sneakers",
        "platform boots",
        "sneakers",
        "boots",
        "loafers",
        "heels",
        "sandals",
    ],
    "preferred_bottoms": [
        "baggy jeans",
        "wide leg jeans",
        "straight jeans",
        "cargo pants",
        "skirts",
        "shorts",
        "trousers",
    ],
    "preferred_layers": [
        "hoodie",
        "cardigan",
        "jacket",
        "blazer",
        "overshirt",
        "long sleeve",
    ],
}


def empty_style_profile() -> dict:
    return {field: [] for field in PROFILE_FIELDS} | {"updated_at": ""}


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _normalize_values(values) -> list[str]:
    normalized = []
    if not isinstance(values, list):
        return normalized

    for value in values:
        if not isinstance(value, str):
            continue
        clean_value = " ".join(value.strip().lower().split())
        if clean_value and clean_value not in normalized:
            normalized.append(clean_value)
    return normalized


def normalize_style_profile(profile: dict | None) -> dict:
    normalized = empty_style_profile()
    if not isinstance(profile, dict):
        return normalized

    for field in PROFILE_FIELDS:
        normalized[field] = _normalize_values(profile.get(field))

    updated_at = profile.get("updated_at")
    if isinstance(updated_at, str):
        normalized["updated_at"] = updated_at.strip()

    return normalized


def load_style_profile() -> dict:
    # return an empty profile when there is no saved runtime file yet
    if not STYLE_PROFILE_PATH.exists():
        return empty_style_profile()

    # ignore unreadable or invalid profile data so the main workflow can continue
    try:
        with STYLE_PROFILE_PATH.open("r", encoding="utf-8") as profile_file:
            profile = json.load(profile_file)
    except (OSError, json.JSONDecodeError):
        return empty_style_profile()

    return normalize_style_profile(profile)


def save_style_profile(profile: dict) -> bool:
    if not isinstance(profile, dict):
        return False

    normalized_profile = normalize_style_profile(profile)
    temp_path = STYLE_PROFILE_PATH.with_suffix(f"{STYLE_PROFILE_PATH.suffix}.tmp")

    # write to a temp file first so a failed write is less likely to corrupt data
    try:
        STYLE_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with temp_path.open("w", encoding="utf-8") as profile_file:
            json.dump(normalized_profile, profile_file, indent=2)
            profile_file.write("\n")
        temp_path.replace(STYLE_PROFILE_PATH)
    except (OSError, TypeError):
        return False

    return True


def update_style_profile(current_profile: dict, new_preferences: dict) -> dict:
    updated_profile = normalize_style_profile(current_profile)
    normalized_preferences = normalize_style_profile(new_preferences)

    # merge new preferences without removing earlier style choices
    for field in PROFILE_FIELDS:
        merged_values = list(updated_profile[field])
        for value in normalized_preferences[field]:
            if value not in merged_values:
                merged_values.append(value)
        updated_profile[field] = merged_values

    updated_profile["updated_at"] = _timestamp()
    return updated_profile


def extract_style_preferences(query: str) -> dict:
    preferences = empty_style_profile()
    raw_query = str(query or "").lower()
    for shopping_marker in ["find me", "looking for", "searching for"]:
        if shopping_marker in raw_query:
            before_marker = raw_query.split(shopping_marker, 1)[0]
            raw_query = before_marker
            break

    query_text = re.sub(r"[^a-z0-9]+", " ", raw_query)
    query_text = f" {' '.join(query_text.split())} "

    # find only supported phrases that are clearly present in the request
    for field, terms in SUPPORTED_TERMS.items():
        for term in terms:
            term_text = term.lower()
            if field == "preferred_fits" and term_text == "baggy":
                if " baggy jeans " in query_text:
                    continue
            if field == "preferred_fits" and term_text == "wide leg":
                if " wide leg jeans " in query_text:
                    continue
            if any(term_text in matched for matched in preferences[field]):
                continue
            if f" {term_text} " in query_text:
                preferences[field].append(term_text)

    return preferences


def clear_style_profile() -> bool:
    # clear saved preferences without deleting unrelated application data
    return save_style_profile(empty_style_profile())


def has_style_preferences(profile: dict | None) -> bool:
    normalized = normalize_style_profile(profile)
    return any(normalized[field] for field in PROFILE_FIELDS)
