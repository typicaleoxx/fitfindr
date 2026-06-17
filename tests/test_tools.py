from copy import deepcopy
from types import SimpleNamespace
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe, load_listings


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
