import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


def test_importing_app_does_not_launch_gradio():
    assert app.__name__ == "app"
    assert hasattr(app, "build_interface")


def sample_listing(**overrides):
    listing = {
        "id": "lst_test",
        "title": "Faded Band Tee",
        "price": 22.0,
        "size": "M",
        "condition": "good",
        "platform": "depop",
        "brand": "Vintage",
        "colors": ["black", "gray"],
        "style_tags": ["vintage", "graphic tee"],
    }
    listing.update(overrides)
    return listing


def successful_session():
    return {
        "query": "vintage graphic tee",
        "style_profile": {
            "preferred_colors": ["neutral"],
            "preferred_styles": ["vintage"],
            "preferred_fits": ["oversized"],
            "preferred_shoes": ["chunky sneakers"],
            "preferred_bottoms": ["baggy jeans"],
            "preferred_layers": [],
            "updated_at": "2026-01-01T00:00:00Z",
        },
        "style_profile_updated": True,
        "style_profile_message": "Style profile updated from this request.",
        "parsed": {},
        "search_results": [sample_listing()],
        "selected_item": sample_listing(),
        "price_comparison": {
            "item_price": 22.0,
            "comparable_count": 3,
            "average_price": 28.0,
            "median_price": 27.0,
            "price_difference": -6.0,
            "percentage_difference": -21.43,
            "assessment": "good deal",
            "reason": "This listing is $6.00 below the average price of 3 comparable items.",
            "comparable_items": [],
        },
        "style_trend": {
            "trend_name": "graphic tee layering",
            "styling_note": "layer the graphic tee over a fitted long sleeve top",
            "source_platform": "Pinterest Trends",
            "source_url": "https://trends.pinterest.com/",
            "checked_at": "2026-06-17",
            "match_reason": "Matched the tops category and the vintage style tag.",
        },
        "wardrobe": {"items": []},
        "outfit_suggestion": "Wear it with baggy jeans and chunky sneakers.",
        "fit_card": "Faded tee, baggy denim, chunky sneakers.",
        "error": None,
    }


def test_successful_session_maps_listing_output(monkeypatch):
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: successful_session())

    listing_output, _, _, _, _, _ = app.handle_query("vintage graphic tee", "Example wardrobe")

    assert "Faded Band Tee" in listing_output
    assert "Price: $22.00" in listing_output
    assert "Size: M" in listing_output
    assert "Platform: Depop" in listing_output


def test_successful_session_maps_outfit_and_fit_card_outputs(monkeypatch):
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: successful_session())

    _, _, _, outfit_output, fit_card_output, _ = app.handle_query(
        "vintage graphic tee",
        "Example wardrobe",
    )

    assert outfit_output == "Wear it with baggy jeans and chunky sneakers."
    assert fit_card_output == "Faded tee, baggy denim, chunky sneakers."


def test_successful_session_maps_price_comparison_output(monkeypatch):
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: successful_session())

    _, _, price_output, _, _, _ = app.handle_query("vintage graphic tee", "Example wardrobe")

    assert "Assessment: Good Deal" in price_output
    assert "Item price: $22.00" in price_output
    assert "Average comparable price: $28.00" in price_output
    assert "Comparable listings: 3" in price_output
    assert "below the average price" in price_output


def test_saved_style_profile_displays_clearly(monkeypatch):
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: successful_session())

    _, profile_output, _, _, _, _ = app.handle_query("vintage graphic tee", "Example wardrobe")

    assert "Saved style profile" in profile_output
    assert "Colors: neutral" in profile_output
    assert "Styles: vintage" in profile_output
    assert "Fits: oversized" in profile_output
    assert "Shoes: chunky sneakers" in profile_output
    assert "Bottoms: baggy jeans" in profile_output


def test_updated_profile_shows_update_status(monkeypatch):
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: successful_session())

    _, profile_output, _, _, _, _ = app.handle_query("vintage graphic tee", "Example wardrobe")

    assert "Updated this request: yes" in profile_output
    assert "Style profile updated from this request." in profile_output


def test_missing_profile_state_does_not_crash(monkeypatch):
    session = successful_session()
    session["style_profile"] = None
    session["style_profile_updated"] = False
    session["style_profile_message"] = ""
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: session)

    _, profile_output, _, _, _, _ = app.handle_query("simple tee", "Example wardrobe")

    assert "Saved style profile" in profile_output
    assert "No saved preferences yet." in profile_output


def test_insufficient_price_comparison_output_is_readable(monkeypatch):
    session = successful_session()
    session["price_comparison"] = {
        "item_price": 22.0,
        "comparable_count": 0,
        "average_price": None,
        "median_price": None,
        "price_difference": None,
        "percentage_difference": None,
        "assessment": "insufficient data",
        "reason": "There is not enough comparable price data for this listing yet.",
        "comparable_items": [],
    }
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: session)

    _, _, price_output, _, _, _ = app.handle_query("rare tee", "Example wardrobe")

    assert "Assessment: Insufficient Data" in price_output
    assert "Item price: $22.00" in price_output
    assert "Comparable listings: 0" in price_output
    assert "not enough comparable price data" in price_output


def test_clear_profile_action_resets_display(monkeypatch):
    monkeypatch.setattr(app, "clear_style_profile", lambda: True)

    profile_output, status_output = app.handle_clear_style_profile()

    assert "No saved preferences yet." in profile_output
    assert "Updated this request: no" in profile_output
    assert status_output == "Style profile cleared."


def test_clear_profile_action_reports_failure(monkeypatch):
    monkeypatch.setattr(app, "clear_style_profile", lambda: False)

    profile_output, status_output = app.handle_clear_style_profile()

    assert "Style profile could not be cleared." in profile_output
    assert status_output == "Style profile could not be cleared."


def test_handle_query_calls_run_agent_once_for_valid_query(monkeypatch):
    calls = []

    def fake_run_agent(query, wardrobe):
        calls.append((query, wardrobe))
        return successful_session()

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    app.handle_query("  vintage graphic tee  ", "Example wardrobe")

    assert len(calls) == 1


def test_query_is_trimmed_before_run_agent(monkeypatch):
    seen = {}

    def fake_run_agent(query, wardrobe):
        seen["query"] = query
        return successful_session()

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    app.handle_query("  vintage graphic tee  ", "Example wardrobe")

    assert seen["query"] == "vintage graphic tee"


def test_example_wardrobe_is_passed_to_run_agent(monkeypatch):
    expected_wardrobe = {"items": [{"name": "test jeans"}]}
    seen = {}
    monkeypatch.setattr(app, "get_example_wardrobe", lambda: expected_wardrobe)

    def fake_run_agent(query, wardrobe):
        seen["wardrobe"] = wardrobe
        return successful_session()

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    app.handle_query("vintage graphic tee", "Example wardrobe")

    assert seen["wardrobe"] is expected_wardrobe


def test_empty_wardrobe_choice_is_passed_to_run_agent(monkeypatch):
    expected_wardrobe = {"items": []}
    seen = {}
    monkeypatch.setattr(app, "get_empty_wardrobe", lambda: expected_wardrobe)

    def fake_run_agent(query, wardrobe):
        seen["wardrobe"] = wardrobe
        return successful_session()

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    app.handle_query("vintage graphic tee", "Empty wardrobe (new user)")

    assert seen["wardrobe"] is expected_wardrobe


def test_empty_query_does_not_call_run_agent(monkeypatch):
    called = False

    def fake_run_agent(query, wardrobe):
        nonlocal called
        called = True
        return successful_session()

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    outputs = app.handle_query("   ", "Example wardrobe")

    assert called is False
    assert outputs[0].startswith("Enter a clothing request")
    assert outputs[1:] == ("", "", "", "", "")


def test_no_results_error_clears_all_content_outputs(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {
            "query": query,
            "style_profile": None,
            "style_profile_updated": False,
            "style_profile_message": "No saved style preferences yet.",
            "parsed": {},
            "search_results": [],
            "selected_item": None,
            "price_comparison": None,
            "wardrobe": wardrobe,
            "outfit_suggestion": None,
            "fit_card": None,
            "error": "I could not find any listings that match that description.",
        }

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    outputs = app.handle_query("designer ballgown", "Example wardrobe")

    assert outputs == (
        "I could not find any listings that match that description.",
        (
            "Saved style profile\n"
            "Colors: none\n"
            "Styles: none\n"
            "Fits: none\n"
            "Shoes: none\n"
            "Bottoms: none\n"
            "Layers: none\n"
            "\n"
            "No saved preferences yet.\n"
            "\n"
            "Updated this request: no\n"
            "No saved style preferences yet."
        ),
        "",
        "",
        "",
        "",
    )


def test_outfit_failure_preserves_listing_and_clears_fit_card(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {
            "query": query,
            "style_profile": successful_session()["style_profile"],
            "style_profile_updated": False,
            "style_profile_message": "Loaded saved style profile.",
            "parsed": {},
            "search_results": [sample_listing()],
            "selected_item": sample_listing(),
            "price_comparison": successful_session()["price_comparison"],
            "wardrobe": wardrobe,
            "outfit_suggestion": None,
            "fit_card": None,
            "error": (
                "I found a listing, but the outfit service could not complete "
                "the request. Check that GROQ_API_KEY is configured and try again."
            ),
        }

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    listing_output, profile_output, price_output, outfit_output, fit_card_output, trend_output = app.handle_query(
        "vintage graphic tee",
        "Example wardrobe",
    )

    assert "Faded Band Tee" in listing_output
    assert "Updated this request: no" in profile_output
    assert "Assessment: Good Deal" in price_output
    assert "outfit service could not complete the request" in outfit_output
    assert "GROQ_API_KEY" in outfit_output
    assert fit_card_output == ""
    assert "No matching trend was found" in trend_output


def test_fit_card_failure_preserves_listing_and_outfit(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {
            "query": query,
            "style_profile": successful_session()["style_profile"],
            "style_profile_updated": False,
            "style_profile_message": "Loaded saved style profile.",
            "parsed": {},
            "search_results": [sample_listing()],
            "selected_item": sample_listing(),
            "price_comparison": successful_session()["price_comparison"],
            "wardrobe": wardrobe,
            "outfit_suggestion": "Wear it with baggy jeans.",
            "fit_card": None,
            "error": (
                "The listing and outfit are ready, but the fit card service "
                "could not finish. Try generating the fit card again."
            ),
        }

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    listing_output, profile_output, price_output, outfit_output, fit_card_output, trend_output = app.handle_query(
        "vintage graphic tee",
        "Example wardrobe",
    )

    assert "Faded Band Tee" in listing_output
    assert "Updated this request: no" in profile_output
    assert "Assessment: Good Deal" in price_output
    assert outfit_output == "Wear it with baggy jeans."
    assert "fit card service could not finish" in fit_card_output
    assert "Try generating the fit card again" in fit_card_output
    assert "No matching trend was found" in trend_output


def test_missing_optional_listing_fields_do_not_crash(monkeypatch):
    minimal_listing = {"title": "Simple Tee"}

    def fake_run_agent(query, wardrobe):
        session = successful_session()
        session["selected_item"] = minimal_listing
        return session

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    listing_output, _, _, _, _, _ = app.handle_query("simple tee", "Example wardrobe")

    assert listing_output == "Simple Tee"


def test_failed_request_does_not_reuse_previous_success(monkeypatch):
    sessions = [
        successful_session(),
        {
            "query": "designer ballgown",
            "style_profile": None,
            "style_profile_updated": False,
            "style_profile_message": "No saved style preferences yet.",
            "parsed": {},
            "search_results": [],
            "selected_item": None,
            "price_comparison": None,
            "wardrobe": {"items": []},
            "outfit_suggestion": None,
            "fit_card": None,
            "error": "I could not find any listings that match that description.",
        },
    ]
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: sessions.pop(0))

    first_outputs = app.handle_query("vintage graphic tee", "Example wardrobe")
    second_outputs = app.handle_query("designer ballgown", "Example wardrobe")

    assert "Faded Band Tee" in first_outputs[0]
    assert second_outputs[0] == "I could not find any listings that match that description."
    assert "No saved preferences yet." in second_outputs[1]
    assert second_outputs[2:] == ("", "", "", "")


def test_handle_query_returns_six_outputs(monkeypatch):
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: successful_session())

    outputs = app.handle_query("vintage graphic tee", "Example wardrobe")

    assert isinstance(outputs, tuple)
    assert len(outputs) == 6


def test_matching_trend_displays_clearly(monkeypatch):
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: successful_session())

    _, _, _, _, _, trend_output = app.handle_query("vintage graphic tee", "Example wardrobe")

    assert "Trend: graphic tee layering" in trend_output
    assert "layer the graphic tee over a fitted long sleeve top" in trend_output
    assert "Source: Pinterest Trends" in trend_output
    assert "Checked: 2026-06-17" in trend_output


def test_no_trend_match_displays_fallback_message(monkeypatch):
    session = successful_session()
    session["style_trend"] = {
        "trend_name": None,
        "styling_note": None,
        "source_platform": None,
        "source_url": None,
        "checked_at": None,
        "match_reason": "No matching trend was found for this item.",
    }
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: session)

    _, _, _, _, _, trend_output = app.handle_query("rare item", "Example wardrobe")

    assert trend_output == (
        "No matching trend was found for this item. "
        "The outfit was generated without trend context."
    )


def test_failed_request_clears_trend_output(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {
            "query": query,
            "style_profile": None,
            "style_profile_updated": False,
            "style_profile_message": "No saved style preferences yet.",
            "parsed": {},
            "search_results": [],
            "selected_item": None,
            "price_comparison": None,
            "style_trend": None,
            "wardrobe": wardrobe,
            "outfit_suggestion": None,
            "fit_card": None,
            "error": "I could not find any listings that match that description.",
        }

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    outputs = app.handle_query("designer ballgown", "Example wardrobe")

    assert outputs[-1] == ""
