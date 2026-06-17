import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent


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

    assert calls == ["search"]
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
