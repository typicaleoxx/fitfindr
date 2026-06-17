import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import style_profile


def use_temp_profile(monkeypatch, tmp_path):
    profile_path = tmp_path / "style_profile.local.json"
    monkeypatch.setattr(style_profile, "STYLE_PROFILE_PATH", profile_path)
    return profile_path


def test_missing_profile_file_returns_empty_profile(monkeypatch, tmp_path):
    use_temp_profile(monkeypatch, tmp_path)

    profile = style_profile.load_style_profile()

    assert profile == style_profile.empty_style_profile()


def test_valid_profile_file_loads_correctly(monkeypatch, tmp_path):
    profile_path = use_temp_profile(monkeypatch, tmp_path)
    profile_path.write_text(
        json.dumps(
            {
                "preferred_colors": ["Black", " gray "],
                "preferred_fits": ["Oversized"],
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    profile = style_profile.load_style_profile()

    assert profile["preferred_colors"] == ["black", "gray"]
    assert profile["preferred_fits"] == ["oversized"]
    assert profile["preferred_shoes"] == []
    assert profile["updated_at"] == "2026-01-01T00:00:00Z"


def test_invalid_json_returns_empty_profile(monkeypatch, tmp_path):
    profile_path = use_temp_profile(monkeypatch, tmp_path)
    profile_path.write_text("{bad json", encoding="utf-8")

    profile = style_profile.load_style_profile()

    assert profile == style_profile.empty_style_profile()


def test_missing_fields_are_filled_safely(monkeypatch, tmp_path):
    profile_path = use_temp_profile(monkeypatch, tmp_path)
    profile_path.write_text(
        json.dumps({"preferred_styles": ["vintage"]}),
        encoding="utf-8",
    )

    profile = style_profile.load_style_profile()

    assert profile["preferred_styles"] == ["vintage"]
    assert profile["preferred_colors"] == []
    assert profile["preferred_layers"] == []


def test_unsupported_fields_are_ignored(monkeypatch, tmp_path):
    profile_path = use_temp_profile(monkeypatch, tmp_path)
    profile_path.write_text(
        json.dumps(
            {
                "preferred_colors": ["black"],
                "email": "person@example.com",
                "chat_history": ["hello"],
            }
        ),
        encoding="utf-8",
    )

    profile = style_profile.load_style_profile()

    assert "email" not in profile
    assert "chat_history" not in profile
    assert profile["preferred_colors"] == ["black"]


def test_save_style_profile_writes_valid_json(monkeypatch, tmp_path):
    profile_path = use_temp_profile(monkeypatch, tmp_path)

    saved = style_profile.save_style_profile(
        {"preferred_colors": ["Black"], "preferred_shoes": ["Sneakers"]}
    )

    assert saved is True
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    assert data["preferred_colors"] == ["black"]
    assert data["preferred_shoes"] == ["sneakers"]


def test_save_style_profile_write_failure_returns_false(monkeypatch, tmp_path):
    profile_path = use_temp_profile(monkeypatch, tmp_path)
    profile_path.mkdir()

    saved = style_profile.save_style_profile({"preferred_colors": ["black"]})

    assert saved is False


def test_update_style_profile_merges_new_values():
    current = {
        "preferred_colors": ["black", "gray"],
        "preferred_fits": ["oversized"],
    }
    new = {
        "preferred_colors": ["gray", "cream"],
        "preferred_shoes": ["chunky sneakers"],
    }

    updated = style_profile.update_style_profile(current, new)

    assert updated["preferred_colors"] == ["black", "gray", "cream"]
    assert updated["preferred_fits"] == ["oversized"]
    assert updated["preferred_shoes"] == ["chunky sneakers"]
    assert updated["updated_at"].endswith("Z")


def test_update_style_profile_removes_duplicates_and_preserves_existing_values():
    updated = style_profile.update_style_profile(
        {"preferred_styles": ["vintage", "grunge"]},
        {"preferred_styles": ["vintage", "minimal", "minimal"]},
    )

    assert updated["preferred_styles"] == ["vintage", "grunge", "minimal"]


def test_update_style_profile_does_not_mutate_inputs():
    current = {"preferred_colors": ["black"]}
    new = {"preferred_colors": ["cream"]}
    original_current = deepcopy(current)
    original_new = deepcopy(new)

    style_profile.update_style_profile(current, new)

    assert current == original_current
    assert new == original_new


def test_update_style_profile_normalizes_values():
    updated = style_profile.update_style_profile(
        {"preferred_colors": [" Black  "]},
        {"preferred_colors": ["BLACK", "Gray"]},
    )

    assert updated["preferred_colors"] == ["black", "gray"]


def test_extract_style_preferences_finds_supported_colors():
    preferences = style_profile.extract_style_preferences(
        "I like neutral colors, black, gray, and earth tones."
    )

    assert preferences["preferred_colors"] == [
        "black",
        "gray",
        "neutral",
        "earth tones",
    ]


def test_extract_style_preferences_finds_supported_styles():
    preferences = style_profile.extract_style_preferences(
        "My style is vintage, grunge, and minimal."
    )

    assert preferences["preferred_styles"] == ["grunge", "minimal", "vintage"]


def test_extract_style_preferences_finds_supported_fits():
    preferences = style_profile.extract_style_preferences(
        "I usually wear oversized tops, relaxed jackets, and wide leg pants."
    )

    assert preferences["preferred_fits"] == ["oversized", "relaxed", "wide leg"]


def test_extract_style_preferences_finds_shoes_and_bottoms():
    preferences = style_profile.extract_style_preferences(
        "I wear baggy jeans with chunky sneakers or platform boots."
    )

    assert preferences["preferred_shoes"] == [
        "chunky sneakers",
        "platform boots",
    ]
    assert preferences["preferred_bottoms"] == ["baggy jeans"]


def test_query_with_no_style_preferences_returns_empty_lists():
    preferences = style_profile.extract_style_preferences("Find me something under $45")

    assert preferences == style_profile.empty_style_profile()


def test_extract_style_preferences_ignores_shopping_item_after_find_me():
    preferences = style_profile.extract_style_preferences(
        "Find me a denim jacket under $45 in size M."
    )

    assert preferences == style_profile.empty_style_profile()


def test_clear_style_profile_resets_the_profile(monkeypatch, tmp_path):
    profile_path = use_temp_profile(monkeypatch, tmp_path)
    style_profile.save_style_profile({"preferred_colors": ["black"]})

    cleared = style_profile.clear_style_profile()

    assert cleared is True
    assert json.loads(profile_path.read_text(encoding="utf-8")) == (
        style_profile.empty_style_profile()
    )


def test_helper_behavior_is_deterministic():
    query = "Neutral colors, oversized tops, baggy jeans, and chunky sneakers."

    first = style_profile.extract_style_preferences(query)
    second = style_profile.extract_style_preferences(query)

    assert first == second
