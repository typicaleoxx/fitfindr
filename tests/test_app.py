import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


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
        "parsed": {},
        "search_results": [sample_listing()],
        "selected_item": sample_listing(),
        "wardrobe": {"items": []},
        "outfit_suggestion": "Wear it with baggy jeans and chunky sneakers.",
        "fit_card": "Faded tee, baggy denim, chunky sneakers.",
        "error": None,
    }


def test_successful_session_maps_listing_output(monkeypatch):
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: successful_session())

    listing_output, _, _ = app.handle_query("vintage graphic tee", "Example wardrobe")

    assert "Faded Band Tee" in listing_output
    assert "Price: $22.00" in listing_output
    assert "Size: M" in listing_output
    assert "Platform: Depop" in listing_output


def test_successful_session_maps_outfit_and_fit_card_outputs(monkeypatch):
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: successful_session())

    _, outfit_output, fit_card_output = app.handle_query(
        "vintage graphic tee",
        "Example wardrobe",
    )

    assert outfit_output == "Wear it with baggy jeans and chunky sneakers."
    assert fit_card_output == "Faded tee, baggy denim, chunky sneakers."


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
    assert outputs[1:] == ("", "")


def test_no_results_error_clears_all_content_outputs(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {
            "query": query,
            "parsed": {},
            "search_results": [],
            "selected_item": None,
            "wardrobe": wardrobe,
            "outfit_suggestion": None,
            "fit_card": None,
            "error": "I could not find any listings that match that description.",
        }

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    outputs = app.handle_query("designer ballgown", "Example wardrobe")

    assert outputs == (
        "I could not find any listings that match that description.",
        "",
        "",
    )


def test_outfit_failure_preserves_listing_and_clears_fit_card(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {
            "query": query,
            "parsed": {},
            "search_results": [sample_listing()],
            "selected_item": sample_listing(),
            "wardrobe": wardrobe,
            "outfit_suggestion": None,
            "fit_card": None,
            "error": "I found a listing, but I could not create a usable outfit suggestion.",
        }

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    listing_output, outfit_output, fit_card_output = app.handle_query(
        "vintage graphic tee",
        "Example wardrobe",
    )

    assert "Faded Band Tee" in listing_output
    assert "could not create a usable outfit suggestion" in outfit_output
    assert fit_card_output == ""


def test_fit_card_failure_preserves_listing_and_outfit(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {
            "query": query,
            "parsed": {},
            "search_results": [sample_listing()],
            "selected_item": sample_listing(),
            "wardrobe": wardrobe,
            "outfit_suggestion": "Wear it with baggy jeans.",
            "fit_card": None,
            "error": "I created the outfit suggestion, but I could not generate the fit card.",
        }

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    listing_output, outfit_output, fit_card_output = app.handle_query(
        "vintage graphic tee",
        "Example wardrobe",
    )

    assert "Faded Band Tee" in listing_output
    assert outfit_output == "Wear it with baggy jeans."
    assert "could not generate the fit card" in fit_card_output


def test_missing_optional_listing_fields_do_not_crash(monkeypatch):
    minimal_listing = {"title": "Simple Tee"}

    def fake_run_agent(query, wardrobe):
        session = successful_session()
        session["selected_item"] = minimal_listing
        return session

    monkeypatch.setattr(app, "run_agent", fake_run_agent)

    listing_output, _, _ = app.handle_query("simple tee", "Example wardrobe")

    assert listing_output == "Simple Tee"


def test_failed_request_does_not_reuse_previous_success(monkeypatch):
    sessions = [
        successful_session(),
        {
            "query": "designer ballgown",
            "parsed": {},
            "search_results": [],
            "selected_item": None,
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
    assert second_outputs[1:] == ("", "")


def test_handle_query_returns_three_outputs(monkeypatch):
    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: successful_session())

    outputs = app.handle_query("vintage graphic tee", "Example wardrobe")

    assert isinstance(outputs, tuple)
    assert len(outputs) == 3
