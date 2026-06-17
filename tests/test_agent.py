import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import agent
import style_profile


def empty_profile():
    return {
        "preferred_colors": [],
        "preferred_styles": [],
        "preferred_fits": [],
        "preferred_shoes": [],
        "preferred_bottoms": [],
        "preferred_layers": [],
        "updated_at": "",
    }


@pytest.fixture(autouse=True)
def isolate_style_profile(monkeypatch):
    monkeypatch.setattr(agent, "load_style_profile", empty_profile)
    monkeypatch.setattr(agent, "extract_style_preferences", lambda query: empty_profile())
    monkeypatch.setattr(
        agent,
        "update_style_profile",
        lambda current_profile, new_preferences: current_profile,
    )
    monkeypatch.setattr(agent, "save_style_profile", lambda profile: True)


def sample_item(item_id="lst_test"):
    return {
        "id": item_id,
        "title": "Vintage Graphic Tee",
        "description": "Soft black graphic tee.",
        "category": "tops",
        "style_tags": ["vintage", "graphic tee"],
        "size": "M",
        "condition": "good",
        "price": 24.0,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }


def sample_price_comparison():
    return {
        "item_price": 24.0,
        "comparable_count": 3,
        "average_price": 28.0,
        "median_price": 27.0,
        "price_difference": -4.0,
        "percentage_difference": -14.29,
        "assessment": "good deal",
        "reason": "This listing is below the average price.",
        "comparable_items": [],
    }


def sample_style_profile():
    profile = empty_profile()
    profile["preferred_colors"] = ["neutral"]
    profile["preferred_fits"] = ["oversized"]
    profile["preferred_shoes"] = ["chunky sneakers"]
    profile["preferred_bottoms"] = ["baggy jeans"]
    profile["updated_at"] = "2026-01-01T00:00:00Z"
    return profile


def test_successful_interaction_calls_all_tools_once(monkeypatch):
    selected_item = sample_item()
    calls = []

    def fake_search_listings(**kwargs):
        calls.append("search")
        return [selected_item]

    def fake_compare_price(new_item):
        calls.append("compare")
        return sample_price_comparison()

    def fake_suggest_outfit(new_item, wardrobe):
        calls.append("outfit")
        return "Wear it with baggy jeans and chunky sneakers."

    def fake_create_fit_card(outfit, new_item):
        calls.append("fit_card")
        return "Graphic tee, baggy jeans, and chunky sneakers."

    monkeypatch.setattr(agent, "search_listings", fake_search_listings)
    monkeypatch.setattr(agent, "compare_price", fake_compare_price)
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", fake_create_fit_card)

    session = agent.run_agent("vintage graphic tee under $30 size M", {"items": []})

    assert calls == ["search", "compare", "outfit", "fit_card"]
    assert session["error"] is None


def test_search_result_state_flows_into_selected_item_compare_and_outfit(monkeypatch):
    selected_item = sample_item()
    seen = {}

    def fake_search_listings(**kwargs):
        seen["search_kwargs"] = kwargs
        return [selected_item]

    def fake_suggest_outfit(new_item, wardrobe):
        seen["outfit_item"] = new_item
        return "Use the tee with denim."

    def fake_compare_price(new_item):
        seen["price_item"] = new_item
        return sample_price_comparison()

    def fake_create_fit_card(outfit, new_item):
        return "Fit card text."

    monkeypatch.setattr(agent, "search_listings", fake_search_listings)
    monkeypatch.setattr(agent, "compare_price", fake_compare_price)
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", fake_create_fit_card)

    session = agent.run_agent("vintage graphic tee under $30 size M", {"items": []})

    assert session["search_results"] == [selected_item]
    assert session["selected_item"] is selected_item
    assert session["price_comparison"] == sample_price_comparison()
    assert seen["price_item"] is session["selected_item"]
    assert seen["outfit_item"] is session["selected_item"]
    assert seen["search_kwargs"]["size"] == "M"
    assert seen["search_kwargs"]["max_price"] == 30.0


def test_outfit_state_flows_into_fit_card(monkeypatch):
    selected_item = sample_item()
    outfit_text = "Use the tee with denim."
    seen = {}

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(
        agent,
        "suggest_outfit",
        lambda new_item, wardrobe: outfit_text,
    )

    def fake_create_fit_card(outfit, new_item):
        seen["fit_card_outfit"] = outfit
        seen["fit_card_item"] = new_item
        return "Fit card text."

    monkeypatch.setattr(agent, "create_fit_card", fake_create_fit_card)

    session = agent.run_agent("vintage graphic tee", {"items": []})

    assert session["outfit_suggestion"] is outfit_text
    assert seen["fit_card_outfit"] is session["outfit_suggestion"]
    assert seen["fit_card_item"] is session["selected_item"]
    assert session["fit_card"] == "Fit card text."


def test_profile_loads_before_outfit_generation(monkeypatch):
    selected_item = sample_item()
    calls = []

    def fake_load_style_profile():
        calls.append("load_profile")
        return sample_style_profile()

    def fake_suggest_outfit(new_item, wardrobe):
        calls.append("outfit")
        return "Outfit"

    monkeypatch.setattr(agent, "load_style_profile", fake_load_style_profile)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    agent.run_agent("denim jacket", {"items": []})

    assert calls == ["load_profile", "outfit"]


def test_new_preferences_from_query_update_profile(monkeypatch):
    selected_item = sample_item()
    loaded_profile = empty_profile()
    new_preferences = empty_profile()
    new_preferences["preferred_colors"] = ["neutral"]
    updated_profile = sample_style_profile()
    seen = {}

    monkeypatch.setattr(agent, "load_style_profile", lambda: loaded_profile)
    monkeypatch.setattr(agent, "extract_style_preferences", lambda query: new_preferences)

    def fake_update_style_profile(current_profile, preferences):
        seen["current_profile"] = current_profile
        seen["preferences"] = preferences
        return updated_profile

    def fake_save_style_profile(profile):
        seen["saved_profile"] = profile
        return True

    monkeypatch.setattr(agent, "update_style_profile", fake_update_style_profile)
    monkeypatch.setattr(agent, "save_style_profile", fake_save_style_profile)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    session = agent.run_agent("neutral oversized tee", {"items": []})

    assert seen["current_profile"] is loaded_profile
    assert seen["preferences"] is new_preferences
    assert seen["saved_profile"] is updated_profile
    assert session["style_profile"] is updated_profile
    assert session["style_profile_updated"] is True
    assert "updated" in session["style_profile_message"].lower()


def test_query_without_preferences_reuses_saved_profile(monkeypatch):
    selected_item = sample_item()
    saved_profile = sample_style_profile()
    save_called = False

    def fake_save_style_profile(profile):
        nonlocal save_called
        save_called = True
        return True

    monkeypatch.setattr(agent, "load_style_profile", lambda: saved_profile)
    monkeypatch.setattr(agent, "extract_style_preferences", lambda query: empty_profile())
    monkeypatch.setattr(agent, "save_style_profile", fake_save_style_profile)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    session = agent.run_agent("Find me a denim jacket under $45", {"items": []})

    assert session["style_profile"] is saved_profile
    assert session["style_profile_updated"] is False
    assert "loaded" in session["style_profile_message"].lower()
    assert save_called is False


def test_profile_is_stored_in_session_state(monkeypatch):
    selected_item = sample_item()
    saved_profile = sample_style_profile()

    monkeypatch.setattr(agent, "load_style_profile", lambda: saved_profile)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    session = agent.run_agent("denim jacket", {"items": []})

    assert session["style_profile"] is saved_profile
    assert session["style_profile_updated"] is False
    assert isinstance(session["style_profile_message"], str)


def test_original_wardrobe_is_not_mutated_by_profile_context(monkeypatch):
    selected_item = sample_item()
    wardrobe = {"items": [{"name": "jeans"}]}
    original_wardrobe = deepcopy(wardrobe)

    monkeypatch.setattr(agent, "load_style_profile", sample_style_profile)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    agent.run_agent("denim jacket", wardrobe)

    assert wardrobe == original_wardrobe
    assert "style_profile" not in wardrobe


def test_suggest_outfit_receives_wardrobe_copy_with_style_profile(monkeypatch):
    selected_item = sample_item()
    wardrobe = {"items": [{"name": "jeans"}]}
    saved_profile = sample_style_profile()
    seen = {}

    monkeypatch.setattr(agent, "load_style_profile", lambda: saved_profile)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())

    def fake_suggest_outfit(new_item, wardrobe):
        seen["wardrobe"] = wardrobe
        return "Outfit"

    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    agent.run_agent("denim jacket", wardrobe)

    assert seen["wardrobe"] is not wardrobe
    assert seen["wardrobe"]["items"] == wardrobe["items"]
    assert seen["wardrobe"]["style_profile"] is saved_profile


def test_profile_save_failure_does_not_stop_required_workflow(monkeypatch):
    selected_item = sample_item()
    new_preferences = empty_profile()
    new_preferences["preferred_fits"] = ["oversized"]
    updated_profile = sample_style_profile()

    monkeypatch.setattr(agent, "extract_style_preferences", lambda query: new_preferences)
    monkeypatch.setattr(agent, "update_style_profile", lambda current, new: updated_profile)
    monkeypatch.setattr(agent, "save_style_profile", lambda profile: False)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    session = agent.run_agent("oversized vintage tee", {"items": []})

    assert session["style_profile"] is updated_profile
    assert session["style_profile_updated"] is False
    assert "could not be saved" in session["style_profile_message"]
    assert session["selected_item"] is selected_item
    assert session["price_comparison"] == sample_price_comparison()
    assert session["outfit_suggestion"] == "Outfit"
    assert session["fit_card"] == "Card"
    assert session["error"] is None


def test_two_interactions_reuse_saved_style_preferences(monkeypatch):
    first_item = sample_item("first")
    second_item = sample_item("second")
    search_results = [[first_item], [second_item]]
    profile_store = empty_profile()
    seen_profiles = []

    def fake_load_style_profile():
        return deepcopy(profile_store)

    def fake_save_style_profile(profile):
        profile_store.clear()
        profile_store.update(deepcopy(profile))
        return True

    def fake_suggest_outfit(new_item, wardrobe):
        seen_profiles.append(deepcopy(wardrobe["style_profile"]))
        if len(seen_profiles) == 2:
            return "Use the denim jacket with baggy jeans and chunky sneakers."
        return "Wear the tee with neutral colors and chunky sneakers."

    monkeypatch.setattr(agent, "load_style_profile", fake_load_style_profile)
    monkeypatch.setattr(agent, "save_style_profile", fake_save_style_profile)
    monkeypatch.setattr(agent, "extract_style_preferences", style_profile.extract_style_preferences)
    monkeypatch.setattr(agent, "update_style_profile", style_profile.update_style_profile)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: search_results.pop(0))
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    first_session = agent.run_agent(
        (
            "I usually wear neutral colors, oversized tops, baggy jeans, and "
            "chunky sneakers. Find me a vintage graphic tee under $30 in size M."
        ),
        {"items": []},
    )
    second_session = agent.run_agent(
        "Find me a denim jacket under $45 in size M.",
        {"items": []},
    )

    assert profile_store["preferred_colors"] == ["neutral"]
    assert profile_store["preferred_fits"] == ["oversized"]
    assert profile_store["preferred_bottoms"] == ["baggy jeans"]
    assert profile_store["preferred_shoes"] == ["chunky sneakers"]
    assert first_session["style_profile_updated"] is True
    assert second_session["style_profile_updated"] is False
    assert seen_profiles[1]["preferred_colors"] == ["neutral"]
    assert seen_profiles[1]["preferred_fits"] == ["oversized"]
    assert seen_profiles[1]["preferred_bottoms"] == ["baggy jeans"]
    assert seen_profiles[1]["preferred_shoes"] == ["chunky sneakers"]
    assert "baggy jeans" in second_session["outfit_suggestion"]
    assert "chunky sneakers" in second_session["outfit_suggestion"]


def test_insufficient_price_data_does_not_stop_outfit_or_fit_card(monkeypatch):
    selected_item = sample_item()
    price_result = {
        "item_price": 24.0,
        "comparable_count": 0,
        "average_price": None,
        "median_price": None,
        "price_difference": None,
        "percentage_difference": None,
        "assessment": "insufficient data",
        "reason": "There is not enough comparable price data.",
        "comparable_items": [],
    }

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: price_result)
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    session = agent.run_agent("vintage graphic tee", {"items": []})

    assert session["price_comparison"] is price_result
    assert session["outfit_suggestion"] == "Outfit"
    assert session["fit_card"] == "Card"
    assert session["error"] is None


def test_empty_search_returns_early_without_later_tools(monkeypatch):
    calls = []

    def fake_search_listings(**kwargs):
        calls.append("search")
        return []

    def fake_compare_price(new_item):
        calls.append("compare")
        return sample_price_comparison()

    def fake_suggest_outfit(new_item, wardrobe):
        calls.append("outfit")
        return "Should not run"

    def fake_create_fit_card(outfit, new_item):
        calls.append("fit_card")
        return "Should not run"

    monkeypatch.setattr(agent, "search_listings", fake_search_listings)
    monkeypatch.setattr(agent, "compare_price", fake_compare_price)
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", fake_create_fit_card)

    session = agent.run_agent("designer ballgown size XXS under $5", {"items": []})

    # the empty first search triggers exactly one fallback search, then stops
    assert calls == ["search", "search"]
    assert session["retry_attempted"] is True
    assert session["search_results"] == []
    assert session["selected_item"] is None
    assert session["price_comparison"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None
    assert "could not find any listings" in session["error"]
    assert "increasing the budget" in session["error"]


def test_outfit_failure_stops_before_fit_card(monkeypatch):
    selected_item = sample_item()
    calls = []

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())

    def fake_suggest_outfit(new_item, wardrobe):
        calls.append("outfit")
        return "I could not generate an outfit because the service failed."

    def fake_create_fit_card(outfit, new_item):
        calls.append("fit_card")
        return "Should not run"

    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", fake_create_fit_card)

    session = agent.run_agent("vintage graphic tee", {"items": []})

    assert calls == ["outfit"]
    assert session["selected_item"] is selected_item
    assert session["outfit_suggestion"].startswith("I could not")
    assert session["fit_card"] is None
    assert "outfit service could not complete the request" in session["error"]
    assert "GROQ_API_KEY" in session["error"]


def test_empty_outfit_result_stops_before_fit_card(monkeypatch):
    selected_item = sample_item()
    fit_card_called = False

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "   ")

    def fake_create_fit_card(outfit, new_item):
        nonlocal fit_card_called
        fit_card_called = True
        return "Should not run"

    monkeypatch.setattr(agent, "create_fit_card", fake_create_fit_card)

    session = agent.run_agent("vintage graphic tee", {"items": []})

    assert fit_card_called is False
    assert session["fit_card"] is None
    assert "outfit service could not complete the request" in session["error"]


def test_fit_card_failure_preserves_selected_item_and_outfit(monkeypatch):
    selected_item = sample_item()
    outfit_text = "Use the tee with denim."

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: outfit_text)
    monkeypatch.setattr(
        agent,
        "create_fit_card",
        lambda outfit, new_item: "The fit card service could not complete the request.",
    )

    session = agent.run_agent("vintage graphic tee", {"items": []})

    assert session["selected_item"] is selected_item
    assert session["outfit_suggestion"] is outfit_text
    assert session["fit_card"].startswith("The fit card service could not")
    assert "fit card service could not finish" in session["error"]
    assert "Try generating the fit card again" in session["error"]


def test_empty_fit_card_result_sets_error(monkeypatch):
    selected_item = sample_item()

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "")

    session = agent.run_agent("vintage graphic tee", {"items": []})

    assert session["fit_card"] == ""
    assert "fit card service could not finish" in session["error"]


def test_original_query_stays_in_session(monkeypatch):
    selected_item = sample_item()
    query = "vintage graphic tee under $30 size M"

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    session = agent.run_agent(query, {"items": []})

    assert session["query"] == query


def test_each_run_uses_clean_session_state(monkeypatch):
    first_item = sample_item("first")
    second_item = sample_item("second")
    search_results = [[first_item], [second_item]]

    def fake_search_listings(**kwargs):
        return search_results.pop(0)

    monkeypatch.setattr(agent, "search_listings", fake_search_listings)
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    first_session = agent.run_agent("first query", {"items": []})
    second_session = agent.run_agent("second query", {"items": []})

    assert first_session is not second_session
    assert first_session["selected_item"] is first_item
    assert second_session["selected_item"] is second_item
    assert first_session["search_results"] == [first_item]
    assert second_session["search_results"] == [second_item]


def test_failure_after_success_does_not_reuse_stale_state(monkeypatch):
    selected_item = sample_item("first")
    search_results = [[selected_item], []]

    def fake_search_listings(**kwargs):
        return search_results.pop(0)

    monkeypatch.setattr(agent, "search_listings", fake_search_listings)
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    first_session = agent.run_agent("first query", {"items": []})
    second_session = agent.run_agent("designer ballgown", {"items": []})

    assert first_session["selected_item"] is selected_item
    assert second_session["selected_item"] is None
    assert second_session["outfit_suggestion"] is None
    assert second_session["fit_card"] is None
    assert "could not find any listings" in second_session["error"]


def sample_style_trend():
    return {
        "trend_name": "graphic tee layering",
        "styling_note": "layer the graphic tee over a fitted long sleeve top",
        "source_platform": "Pinterest Trends",
        "source_url": "https://trends.pinterest.com/",
        "checked_at": "2026-06-17",
        "match_reason": "Matched the tops category and the vintage style tag.",
    }


def test_get_style_trend_runs_after_selected_item(monkeypatch):
    selected_item = sample_item()
    calls = []

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: (calls.append("compare"), sample_price_comparison())[1])

    def fake_get_style_trend(new_item, size=None):
        calls.append("trend")
        return sample_style_trend()

    def fake_suggest_outfit(new_item, wardrobe):
        calls.append("outfit")
        return "Outfit"

    monkeypatch.setattr(agent, "get_style_trend", fake_get_style_trend)
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    agent.run_agent("vintage graphic tee", {"items": []})

    assert calls == ["compare", "trend", "outfit"]


def test_exact_selected_item_passed_to_get_style_trend(monkeypatch):
    selected_item = sample_item()
    seen = {}

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())

    def fake_get_style_trend(new_item, size=None):
        seen["trend_item"] = new_item
        seen["trend_size"] = size
        return sample_style_trend()

    monkeypatch.setattr(agent, "get_style_trend", fake_get_style_trend)
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    session = agent.run_agent("vintage graphic tee size M", {"items": []})

    assert seen["trend_item"] is session["selected_item"]
    assert seen["trend_size"] == "M"


def test_style_trend_is_stored_in_session(monkeypatch):
    selected_item = sample_item()
    trend = sample_style_trend()

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "get_style_trend", lambda new_item, size=None: trend)
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    session = agent.run_agent("vintage graphic tee", {"items": []})

    assert session["style_trend"] is trend


def test_trend_context_is_added_to_wardrobe_copy(monkeypatch):
    selected_item = sample_item()
    wardrobe = {"items": [{"name": "jeans"}]}
    original_wardrobe = deepcopy(wardrobe)
    trend = sample_style_trend()
    seen = {}

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "get_style_trend", lambda new_item, size=None: trend)

    def fake_suggest_outfit(new_item, wardrobe):
        seen["wardrobe"] = wardrobe
        return "Outfit"

    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    agent.run_agent("vintage graphic tee", wardrobe)

    assert seen["wardrobe"] is not wardrobe
    assert seen["wardrobe"]["style_trend"] is trend
    assert wardrobe == original_wardrobe
    assert "style_trend" not in wardrobe


def test_no_matching_trend_does_not_stop_required_flow(monkeypatch):
    selected_item = sample_item()
    empty_trend = {
        "trend_name": None,
        "styling_note": None,
        "source_platform": None,
        "source_url": None,
        "checked_at": None,
        "match_reason": "No matching trend was found for this item.",
    }

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "get_style_trend", lambda new_item, size=None: empty_trend)
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    session = agent.run_agent("vintage graphic tee", {"items": []})

    assert session["style_trend"] is empty_trend
    assert session["outfit_suggestion"] == "Outfit"
    assert session["fit_card"] == "Card"
    assert session["error"] is None


def test_empty_search_does_not_call_trend_tool(monkeypatch):
    trend_called = False

    def fake_get_style_trend(new_item, size=None):
        nonlocal trend_called
        trend_called = True
        return sample_style_trend()

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [])
    monkeypatch.setattr(agent, "get_style_trend", fake_get_style_trend)
    monkeypatch.setattr(agent, "compare_price", lambda new_item: sample_price_comparison())
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Card")

    session = agent.run_agent("designer ballgown size XXS under $5", {"items": []})

    assert trend_called is False
    assert session["style_trend"] is None


def fallback_tools(monkeypatch, search_side_effect):
    """Wire deterministic tool stubs for retry tests and return a call log."""
    calls = []

    def fake_search_listings(**kwargs):
        calls.append(("search", dict(kwargs)))
        return search_side_effect(kwargs)

    monkeypatch.setattr(agent, "search_listings", fake_search_listings)
    monkeypatch.setattr(
        agent,
        "compare_price",
        lambda new_item: (calls.append(("compare", new_item)), sample_price_comparison())[1],
    )
    monkeypatch.setattr(
        agent,
        "get_style_trend",
        lambda new_item, size=None: (calls.append(("trend", new_item)), {"trend_name": None})[1],
    )
    monkeypatch.setattr(
        agent,
        "suggest_outfit",
        lambda new_item, wardrobe: (calls.append(("outfit", new_item)), "Outfit")[1],
    )
    monkeypatch.setattr(
        agent,
        "create_fit_card",
        lambda outfit, new_item: (calls.append(("fit_card", new_item)), "Card")[1],
    )
    return calls


def test_successful_first_search_does_not_retry(monkeypatch):
    selected_item = sample_item()
    calls = fallback_tools(monkeypatch, lambda kwargs: [selected_item])

    session = agent.run_agent("vintage graphic tee under $30 size M", {"items": []})

    search_calls = [c for c in calls if c[0] == "search"]
    assert len(search_calls) == 1
    assert session["retry_attempted"] is False
    assert session["fallback_message"] == ""
    assert session["error"] is None


def test_empty_first_search_triggers_exactly_one_retry(monkeypatch):
    selected_item = sample_item()

    def search(kwargs):
        # the first call with a size returns nothing, the relaxed call finds an item
        return [] if kwargs["size"] else [selected_item]

    calls = fallback_tools(monkeypatch, search)

    session = agent.run_agent("vintage graphic tee under $30 size M", {"items": []})

    search_calls = [c for c in calls if c[0] == "search"]
    assert len(search_calls) == 2
    assert session["retry_attempted"] is True


def test_retry_removes_size_and_keeps_description_and_budget(monkeypatch):
    selected_item = sample_item()

    def search(kwargs):
        return [] if kwargs["size"] else [selected_item]

    calls = fallback_tools(monkeypatch, search)

    session = agent.run_agent("vintage graphic tee under $30 size M", {"items": []})

    first_search = [c for c in calls if c[0] == "search"][0][1]
    second_search = [c for c in calls if c[0] == "search"][1][1]
    assert first_search["size"] == "M"
    assert second_search["size"] is None
    assert second_search["description"] == first_search["description"]
    assert second_search["max_price"] == first_search["max_price"]
    assert session["retry_reason"] == "removed size filter"
    assert session["original_search_parameters"]["size"] == "M"
    assert session["final_search_parameters"]["size"] is None


def test_successful_retry_continues_through_workflow_with_fallback_item(monkeypatch):
    fallback_item = sample_item("fallback")

    def search(kwargs):
        return [] if kwargs["size"] else [fallback_item]

    calls = fallback_tools(monkeypatch, search)

    session = agent.run_agent("vintage graphic tee under $30 size M", {"items": []})

    # the fallback item must reach every later tool unchanged
    assert session["selected_item"] is fallback_item
    assert ("compare", fallback_item) in calls
    assert ("trend", fallback_item) in calls
    assert ("outfit", fallback_item) in calls
    assert ("fit_card", fallback_item) in calls
    assert session["outfit_suggestion"] == "Outfit"
    assert session["fit_card"] == "Card"
    assert session["error"] is None
    assert "removed size filter" in session["retry_reason"]
    assert "retried without the size filter" in session["fallback_message"]


def test_failed_retry_stops_before_later_tools(monkeypatch):
    calls = fallback_tools(monkeypatch, lambda kwargs: [])

    session = agent.run_agent("vintage graphic tee under $30 size M", {"items": []})

    search_calls = [c for c in calls if c[0] == "search"]
    later_calls = [c for c in calls if c[0] in {"compare", "trend", "outfit", "fit_card"}]
    assert len(search_calls) == 2
    assert later_calls == []
    assert session["selected_item"] is None
    assert session["price_comparison"] is None
    assert session["style_trend"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None


def test_failed_retry_stores_specific_actionable_error(monkeypatch):
    fallback_tools(monkeypatch, lambda kwargs: [])

    session = agent.run_agent("vintage graphic tee under $30 size M", {"items": []})

    assert session["retry_attempted"] is True
    assert "original request or the relaxed search" in session["error"]
    assert "broader item description" in session["error"]
    assert "returned nothing either" in session["fallback_message"]


def test_retry_runs_at_most_once_even_when_both_empty(monkeypatch):
    calls = fallback_tools(monkeypatch, lambda kwargs: [])

    agent.run_agent("vintage graphic tee under $30 size M", {"items": []})

    search_calls = [c for c in calls if c[0] == "search"]
    assert len(search_calls) == 2


def test_no_constraint_to_loosen_does_not_retry(monkeypatch):
    calls = fallback_tools(monkeypatch, lambda kwargs: [])

    session = agent.run_agent("designer ballgown", {"items": []})

    search_calls = [c for c in calls if c[0] == "search"]
    assert len(search_calls) == 1
    assert session["retry_attempted"] is False
    assert "could not find any listings" in session["error"]
