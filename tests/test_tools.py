from copy import deepcopy
from types import SimpleNamespace
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools
from tools import (
    compare_price,
    create_fit_card,
    get_style_trend,
    search_listings,
    suggest_outfit,
)
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe, load_listings


EXPECTED_TREND_FIELDS = {
    "trend_name",
    "styling_note",
    "source_platform",
    "source_url",
    "checked_at",
    "match_reason",
}


EXPECTED_LISTING_FIELDS = {
    "id",
    "title",
    "description",
    "category",
    "style_tags",
    "size",
    "condition",
    "price",
    "colors",
    "brand",
    "platform",
}


def test_search_returns_matching_listings():
    results = search_listings("graphic tee")

    assert isinstance(results, list)
    assert results
    assert any(item["id"] == "lst_006" for item in results)


def test_impossible_search_returns_empty_list():
    results = search_listings("designer ballgown", size="XXS", max_price=5)

    assert results == []


def test_search_handles_data_loading_failure(monkeypatch):
    def broken_load_listings():
        raise OSError("data unavailable")

    monkeypatch.setattr(tools, "load_listings", broken_load_listings)

    results = search_listings("graphic tee")

    assert results == []


def test_results_respect_max_price():
    results = search_listings("vintage", max_price=20)

    assert results
    assert all(item["price"] <= 20 for item in results)


def test_results_respect_requested_size():
    results = search_listings("vintage", size="M")

    assert results
    assert all("m" in item["size"].lower() for item in results)


def test_search_is_case_insensitive():
    lower_results = search_listings("graphic tee")
    mixed_results = search_listings("GrApHiC TEE")

    assert [item["id"] for item in mixed_results] == [
        item["id"] for item in lower_results
    ]


def test_size_none_keeps_valid_results():
    results = search_listings("graphic tee", size=None, max_price=30)
    result_ids = [item["id"] for item in results]

    assert "lst_006" in result_ids
    assert "lst_002" in result_ids
    assert "lst_033" in result_ids


def test_max_price_none_keeps_valid_results():
    results = search_listings("platform", size=None, max_price=None)
    result_ids = [item["id"] for item in results]

    assert "lst_009" in result_ids
    assert "lst_019" in result_ids


def test_returned_values_keep_listing_fields():
    results = search_listings("graphic tee")
    dataset_by_id = {item["id"]: item for item in load_listings()}

    assert results
    assert all(isinstance(item, dict) for item in results)
    assert all(set(item.keys()) == EXPECTED_LISTING_FIELDS for item in results)
    assert results[0] == dataset_by_id[results[0]["id"]]


def test_results_are_ordered_by_relevance_then_price_then_dataset_order():
    results = search_listings("graphic tee", max_price=30)

    assert [item["id"] for item in results[:3]] == ["lst_006", "lst_002", "lst_033"]


def comparison_item(**overrides):
    item = {
        "id": "selected",
        "title": "Vintage Graphic Tee",
        "description": "Soft black graphic tee.",
        "category": "tops",
        "style_tags": ["vintage", "graphic tee"],
        "size": "M",
        "condition": "good",
        "price": 20.0,
        "colors": ["black"],
        "brand": "Thread House",
        "platform": "depop",
    }
    item.update(overrides)
    return item


def comparison_pool():
    return [
        comparison_item(id="selected", price=20.0),
        comparison_item(id="same_style", price=30.0, title="Same Style Tee"),
        comparison_item(id="same_brand", price=40.0, title="Same Brand Tee"),
        comparison_item(
            id="other_color",
            price=50.0,
            title="White Graphic Tee",
            colors=["white"],
            brand=None,
        ),
        comparison_item(
            id="skirt",
            price=12.0,
            title="Vintage Skirt",
            category="bottoms",
            style_tags=["vintage"],
        ),
    ]


def test_compare_price_returns_expected_fields_and_good_deal_assessment():
    result = compare_price(comparison_item(), comparison_pool())

    assert set(result.keys()) == {
        "item_price",
        "comparable_count",
        "average_price",
        "median_price",
        "price_difference",
        "percentage_difference",
        "assessment",
        "reason",
        "comparable_items",
    }
    assert result["item_price"] == 20.0
    assert result["comparable_count"] == 4
    assert result["average_price"] == 33.0
    assert result["median_price"] == 35.0
    assert result["price_difference"] == -13.0
    assert result["percentage_difference"] == -39.39
    assert result["assessment"] == "good deal"
    assert "below the average price" in result["reason"]


def test_compare_price_excludes_selected_listing_by_id():
    result = compare_price(comparison_item(), comparison_pool())
    comparable_ids = [item["id"] for item in result["comparable_items"]]

    assert "selected" not in comparable_ids


def test_compare_price_includes_comparable_summaries_with_similarity_scores():
    result = compare_price(comparison_item(), comparison_pool())
    first_comparable = result["comparable_items"][0]

    assert first_comparable == {
        "id": "same_style",
        "title": "Same Style Tee",
        "price": 30.0,
        "category": "tops",
        "size": "M",
        "condition": "good",
        "platform": "depop",
        "similarity_score": 25,
    }


def test_compare_price_limits_comparables_to_five_items():
    pool = [
        comparison_item(id=f"comp_{index}", price=25.0 + index)
        for index in range(8)
    ]

    result = compare_price(comparison_item(), pool)

    assert result["comparable_count"] == 5
    assert len(result["comparable_items"]) == 5


def test_compare_price_classifies_fair_and_above_average_prices():
    fair_result = compare_price(
        comparison_item(price=42.0),
        [
            comparison_item(id="comp_1", price=40.0),
            comparison_item(id="comp_2", price=42.0),
            comparison_item(id="comp_3", price=44.0),
        ],
    )
    above_result = compare_price(
        comparison_item(price=60.0),
        [
            comparison_item(id="comp_1", price=40.0),
            comparison_item(id="comp_2", price=42.0),
            comparison_item(id="comp_3", price=44.0),
        ],
    )

    assert fair_result["assessment"] == "fair price"
    assert above_result["assessment"] == "above average"


def test_compare_price_returns_insufficient_data_for_missing_price():
    result = compare_price(comparison_item(price=None), comparison_pool())

    assert result["assessment"] == "insufficient data"
    assert result["item_price"] is None
    assert result["comparable_count"] == 0
    assert result["average_price"] is None
    assert result["comparable_items"] == []


def test_compare_price_returns_insufficient_data_when_listings_cannot_load(monkeypatch):
    def broken_load_listings():
        raise OSError("data unavailable")

    monkeypatch.setattr(tools, "load_listings", broken_load_listings)

    result = compare_price(comparison_item())

    assert result["assessment"] == "insufficient data"
    assert "could not be loaded" in result["reason"]


def test_compare_price_returns_insufficient_data_without_comparables():
    result = compare_price(
        comparison_item(),
        [
            comparison_item(
                id="unrelated",
                category="shoes",
                style_tags=["minimal"],
                size="8",
                condition="excellent",
                colors=["brown"],
                brand=None,
            )
        ],
    )

    assert result["assessment"] == "insufficient data"
    assert result["comparable_items"] == []


class FakeCompletions:
    def __init__(self, content=""):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content)
                )
            ]
        )


class BrokenCompletions:
    def create(self, **kwargs):
        raise RuntimeError("request failed")


def fake_client_with(content):
    completions = FakeCompletions(content)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )
    return client, completions


def selected_graphic_tee():
    return search_listings("graphic tee")[0]


def selected_track_jacket():
    return search_listings("track jacket")[0]


def test_suggest_outfit_with_populated_wardrobe_returns_string(monkeypatch):
    client, _ = fake_client_with("Wear it with baggy jeans and chunky sneakers.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = suggest_outfit(selected_graphic_tee(), get_example_wardrobe())

    assert isinstance(result, str)
    assert result == "Wear it with baggy jeans and chunky sneakers."


def test_suggest_outfit_prompt_contains_new_item(monkeypatch):
    client, completions = fake_client_with("Style it with denim.")
    item = selected_graphic_tee()
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    suggest_outfit(item, get_example_wardrobe())
    prompt = completions.calls[0]["messages"][1]["content"]

    assert item["title"] in prompt
    assert item["category"] in prompt
    assert "graphic tee" in prompt.lower()


def test_suggest_outfit_prompt_contains_wardrobe_information(monkeypatch):
    client, completions = fake_client_with("Use the jeans and sneakers.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    suggest_outfit(selected_graphic_tee(), get_example_wardrobe())
    prompt = completions.calls[0]["messages"][1]["content"]

    assert "Baggy straight-leg jeans, dark wash" in prompt
    assert "Chunky white sneakers" in prompt
    assert "streetwear" in prompt


def test_suggest_outfit_empty_wardrobe_returns_general_advice(monkeypatch):
    client, completions = fake_client_with(
        "Pair it with relaxed denim, simple sneakers, and a light layer."
    )
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = suggest_outfit(selected_graphic_tee(), get_empty_wardrobe())
    prompt = completions.calls[0]["messages"][1]["content"]

    assert "relaxed denim" in result
    assert "No usable wardrobe items were provided." in prompt
    assert "Do not claim the user owns specific pieces." in prompt


def test_suggest_outfit_prompt_includes_style_profile_information(monkeypatch):
    client, completions = fake_client_with("Use saved preferences in the outfit.")
    wardrobe = get_empty_wardrobe()
    wardrobe["style_profile"] = {
        "preferred_colors": ["neutral"],
        "preferred_styles": ["vintage"],
        "preferred_fits": ["oversized"],
        "preferred_shoes": ["chunky sneakers"],
        "preferred_bottoms": ["baggy jeans"],
        "preferred_layers": [],
        "updated_at": "2026-01-01T00:00:00Z",
    }
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    suggest_outfit(selected_graphic_tee(), wardrobe)
    prompt = completions.calls[0]["messages"][1]["content"]

    assert "Saved style preferences:" in prompt
    assert "Preferred colors: neutral" in prompt
    assert "Preferred fits: oversized" in prompt
    assert "Preferred shoes: chunky sneakers" in prompt
    assert "Preferred bottoms: baggy jeans" in prompt


def test_suggest_outfit_missing_style_profile_does_not_break_existing_behavior(monkeypatch):
    client, completions = fake_client_with("Style it with denim.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = suggest_outfit(selected_graphic_tee(), get_example_wardrobe())
    prompt = completions.calls[0]["messages"][1]["content"]

    assert result == "Style it with denim."
    assert "No saved style preferences." in prompt


def test_suggest_outfit_does_not_treat_saved_preferences_as_owned_items(monkeypatch):
    client, completions = fake_client_with("Use saved preferences in the outfit.")
    wardrobe = get_empty_wardrobe()
    wardrobe["style_profile"] = {
        "preferred_bottoms": ["baggy jeans"],
        "preferred_shoes": ["chunky sneakers"],
    }
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    suggest_outfit(selected_graphic_tee(), wardrobe)
    prompt = completions.calls[0]["messages"][1]["content"]

    assert "User wardrobe:\nNo usable wardrobe items were provided." in prompt
    assert "Saved style preferences:" in prompt
    assert "Do not describe saved style preferences as clothing the user owns." in prompt


def test_suggest_outfit_missing_item_returns_specific_error():
    result = suggest_outfit({}, get_example_wardrobe())

    assert isinstance(result, str)
    assert "selected listing is missing" in result
    assert "search for an item first" in result


def test_suggest_outfit_missing_api_key_returns_actionable_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    result = suggest_outfit(selected_graphic_tee(), get_example_wardrobe())

    assert "Groq API key is not configured" in result
    assert "GROQ_API_KEY" in result


def test_suggest_outfit_request_exception_returns_failure_message(monkeypatch):
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=BrokenCompletions())
    )
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = suggest_outfit(selected_graphic_tee(), get_example_wardrobe())

    assert "outfit service could not complete the request" in result
    assert "GROQ_API_KEY" in result
    assert "try again" in result.lower()


def test_suggest_outfit_empty_model_response_returns_clear_message(monkeypatch):
    client, _ = fake_client_with("   ")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = suggest_outfit(selected_graphic_tee(), get_example_wardrobe())

    assert "came back empty" in result
    assert isinstance(result, str)


def test_suggest_outfit_returns_string_not_response_object(monkeypatch):
    client, _ = fake_client_with("Try the tee with black jeans and boots.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = suggest_outfit(selected_graphic_tee(), get_example_wardrobe())

    assert isinstance(result, str)
    assert not hasattr(result, "choices")


def test_suggest_outfit_does_not_mutate_inputs(monkeypatch):
    client, _ = fake_client_with("Style it with a cropped layer.")
    item = selected_graphic_tee()
    wardrobe = get_example_wardrobe()
    original_item = deepcopy(item)
    original_wardrobe = deepcopy(wardrobe)
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    suggest_outfit(item, wardrobe)

    assert item == original_item
    assert wardrobe == original_wardrobe


def test_create_fit_card_with_valid_inputs_returns_string(monkeypatch):
    client, _ = fake_client_with("Bootleg tee, baggy denim, and chunky sneakers.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = create_fit_card(
        "Wear it with baggy jeans and chunky sneakers.",
        selected_graphic_tee(),
    )

    assert isinstance(result, str)
    assert result == "Bootleg tee, baggy denim, and chunky sneakers."


def test_create_fit_card_prompt_contains_outfit_text(monkeypatch):
    client, completions = fake_client_with("Caption text")
    outfit = "Wear it with baggy jeans, a black cropped hoodie, and sneakers."
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    create_fit_card(outfit, selected_graphic_tee())
    prompt = completions.calls[0]["messages"][1]["content"]

    assert outfit in prompt


def test_create_fit_card_prompt_contains_item_details(monkeypatch):
    client, completions = fake_client_with("Caption text")
    item = selected_graphic_tee()
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    create_fit_card("Style it with denim and sneakers.", item)
    prompt = completions.calls[0]["messages"][1]["content"]

    assert item["title"] in prompt
    assert item["platform"] in prompt
    assert str(item["price"]) in prompt
    assert "graphic tee" in prompt.lower()


def test_create_fit_card_empty_outfit_returns_specific_error(monkeypatch):
    client, completions = fake_client_with("Should not be used")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = create_fit_card("", selected_graphic_tee())

    assert "outfit suggestion is missing" in result
    assert "Generate an outfit first" in result
    assert completions.calls == []


def test_create_fit_card_whitespace_outfit_returns_specific_error(monkeypatch):
    client, completions = fake_client_with("Should not be used")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = create_fit_card("   ", selected_graphic_tee())

    assert "outfit suggestion is missing" in result
    assert completions.calls == []


def test_create_fit_card_missing_item_returns_specific_error(monkeypatch):
    client, completions = fake_client_with("Should not be used")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = create_fit_card("Style it with denim.", {})

    assert "selected listing is missing" in result
    assert "Search for an item first" in result
    assert completions.calls == []


def test_create_fit_card_invalid_item_does_not_call_service(monkeypatch):
    client, completions = fake_client_with("Should not be used")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = create_fit_card("Style it with denim.", None)

    assert "selected listing is missing" in result
    assert completions.calls == []


def test_create_fit_card_missing_api_key_returns_actionable_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    result = create_fit_card("Style it with denim.", selected_graphic_tee())

    assert "Groq API key is not configured" in result
    assert "GROQ_API_KEY" in result


def test_create_fit_card_request_exception_returns_failure_message(monkeypatch):
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=BrokenCompletions())
    )
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = create_fit_card("Style it with denim.", selected_graphic_tee())

    assert "fit card service could not finish" in result
    assert "Try generating the fit card again" in result


def test_create_fit_card_empty_model_response_returns_clear_message(monkeypatch):
    client, _ = fake_client_with("   ")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = create_fit_card("Style it with denim.", selected_graphic_tee())

    assert "fit card came back empty" in result
    assert isinstance(result, str)


def test_create_fit_card_returns_string_not_response_object(monkeypatch):
    client, _ = fake_client_with("Graphic tee with denim for the day.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = create_fit_card("Style it with denim.", selected_graphic_tee())

    assert isinstance(result, str)
    assert not hasattr(result, "choices")


def test_create_fit_card_does_not_mutate_inputs(monkeypatch):
    client, _ = fake_client_with("Graphic tee with denim for the day.")
    outfit = "Style it with denim and sneakers."
    item = selected_graphic_tee()
    original_outfit = outfit
    original_item = deepcopy(item)
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    create_fit_card(outfit, item)

    assert outfit == original_outfit
    assert item == original_item


def test_create_fit_card_different_inputs_make_different_prompts(monkeypatch):
    client, completions = fake_client_with("Caption text")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    create_fit_card(
        "Wear the tee with baggy jeans and chunky sneakers.",
        selected_graphic_tee(),
    )
    create_fit_card(
        "Layer the jacket over a white tank with wide-leg trousers.",
        selected_track_jacket(),
    )

    first_prompt = completions.calls[0]["messages"][1]["content"]
    second_prompt = completions.calls[1]["messages"][1]["content"]

    assert first_prompt != second_prompt
    assert "Graphic Tee" in first_prompt
    assert "90s Track Jacket" in second_prompt


def trend_item(**overrides):
    item = {
        "id": "trend_selected",
        "title": "Vintage Graphic Tee",
        "category": "tops",
        "style_tags": ["graphic tee", "vintage"],
        "size": "M",
    }
    item.update(overrides)
    return item


def test_get_style_trend_matching_item_returns_trend_dict():
    result = get_style_trend(trend_item())

    assert isinstance(result, dict)
    assert result["trend_name"] == "graphic tee layering"
    assert result["styling_note"]
    assert result["source_platform"] == "Pinterest Trends"


def test_get_style_trend_result_contains_all_documented_fields():
    matched = get_style_trend(trend_item())
    unmatched = get_style_trend(
        trend_item(category="accessories", style_tags=["western"])
    )

    assert set(matched.keys()) == EXPECTED_TREND_FIELDS
    assert set(unmatched.keys()) == EXPECTED_TREND_FIELDS


def test_get_style_trend_selects_expected_trend_by_category_and_tags():
    result = get_style_trend(
        trend_item(category="bottoms", style_tags=["denim", "baggy", "90s"])
    )

    assert result["trend_name"] == "baggy denim revival"
    assert "bottoms category" in result["match_reason"]


def test_get_style_trend_no_match_returns_empty_result():
    result = get_style_trend(
        trend_item(category="accessories", style_tags=["western"])
    )

    assert result["trend_name"] is None
    assert result["styling_note"] is None
    assert result["source_platform"] is None
    assert result["source_url"] is None
    assert result["checked_at"] is None
    assert "No matching trend was found" in result["match_reason"]


def test_get_style_trend_invalid_item_does_not_crash():
    assert get_style_trend({})["trend_name"] is None
    assert get_style_trend(None)["trend_name"] is None


def test_get_style_trend_missing_trend_file_does_not_crash(monkeypatch):
    monkeypatch.setattr(tools, "TRENDS_PATH", Path("does/not/exist/trends.json"))

    result = get_style_trend(trend_item())

    assert result["trend_name"] is None
    assert "No matching trend was found" in result["match_reason"]


def test_get_style_trend_does_not_mutate_input_item():
    item = trend_item()
    original_item = deepcopy(item)

    get_style_trend(item, size="M")

    assert item == original_item


def test_get_style_trend_is_deterministic():
    item = trend_item()

    first = get_style_trend(item, size="M")
    second = get_style_trend(item, size="M")

    assert first == second


def test_suggest_outfit_prompt_includes_trend_styling_note(monkeypatch):
    client, completions = fake_client_with("Layer it and add chunky sneakers.")
    wardrobe = get_empty_wardrobe()
    wardrobe["style_trend"] = {
        "trend_name": "graphic tee layering",
        "styling_note": "layer the graphic tee over a fitted long sleeve top",
        "source_platform": "Pinterest Trends",
    }
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    suggest_outfit(selected_graphic_tee(), wardrobe)
    prompt = completions.calls[0]["messages"][1]["content"]

    assert "Current trend context:" in prompt
    assert "graphic tee layering" in prompt
    assert "layer the graphic tee over a fitted long sleeve top" in prompt
    assert "Pinterest Trends" in prompt
    assert "incorporate it into the recommendation" in prompt


def test_suggest_outfit_missing_style_trend_preserves_behavior(monkeypatch):
    client, completions = fake_client_with("Style it with denim.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)

    result = suggest_outfit(selected_graphic_tee(), get_example_wardrobe())
    prompt = completions.calls[0]["messages"][1]["content"]

    assert result == "Style it with denim."
    assert "No current trend context." in prompt
