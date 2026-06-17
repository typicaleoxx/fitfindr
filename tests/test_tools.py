import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import search_listings
from utils.data_loader import load_listings


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
