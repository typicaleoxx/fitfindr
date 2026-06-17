"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    compare_price(new_item, listings)              → dict
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re
from statistics import median

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# groq client

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# tool 1: search_listings

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    # normalize the query so matching does not depend on capitalization
    stop_words = {
        "a",
        "an",
        "and",
        "for",
        "in",
        "looking",
        "of",
        "or",
        "the",
        "to",
        "under",
        "with",
    }
    search_terms = [
        term
        for term in re.findall(r"[a-z0-9]+", description.lower())
        if len(term) > 1 and term not in stop_words
    ]

    # prepare optional filters only when the user gave useful values
    requested_size = size.strip().lower() if size and size.strip() else None
    requested_price = max_price if max_price is not None else None

    # return no matches if the listing data cannot be loaded
    try:
        listings = load_listings()
    except Exception:
        return []
    scored_listings = []

    for index, listing in enumerate(listings):
        if requested_price is not None and listing["price"] > requested_price:
            continue

        if requested_size:
            size_text = listing.get("size", "").lower()
            size_tokens = re.findall(r"[a-z0-9]+", size_text)
            requested_tokens = re.findall(r"[a-z0-9]+", requested_size)
            if requested_size not in size_text and not all(
                token in size_tokens for token in requested_tokens
            ):
                continue

        # rank stronger title and style matches above general description matches
        title_text = listing.get("title", "").lower()
        description_text = listing.get("description", "").lower()
        category_text = listing.get("category", "").lower()
        style_text = " ".join(listing.get("style_tags", [])).lower()
        color_text = " ".join(listing.get("colors", [])).lower()
        brand_text = (listing.get("brand") or "").lower()

        score = 0
        for term in search_terms:
            if term in title_text:
                score += 4
            if term in style_text:
                score += 4
            if term in category_text:
                score += 2
            if term in color_text:
                score += 2
            if term in brand_text:
                score += 2
            if term in description_text:
                score += 1

        # keep only listings with at least one real query match
        if score > 0:
            scored_listings.append((score, listing["price"], index, listing))

    scored_listings.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [listing for _, _, _, listing in scored_listings]


# tool 4: compare_price

def _usable_price(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _normalized_set(value) -> set[str]:
    if isinstance(value, list):
        return {
            str(item).strip().lower()
            for item in value
            if str(item).strip()
        }
    if isinstance(value, str) and value.strip():
        return {value.strip().lower()}
    return set()


def _price_comparison_result(
    item_price,
    comparable_count,
    average_price,
    median_price,
    price_difference,
    percentage_difference,
    assessment,
    reason,
    comparable_items,
) -> dict:
    return {
        "item_price": item_price,
        "comparable_count": comparable_count,
        "average_price": average_price,
        "median_price": median_price,
        "price_difference": price_difference,
        "percentage_difference": percentage_difference,
        "assessment": assessment,
        "reason": reason,
        "comparable_items": comparable_items,
    }


def _insufficient_price_data(item_price, reason: str) -> dict:
    return _price_comparison_result(
        item_price=item_price,
        comparable_count=0,
        average_price=None,
        median_price=None,
        price_difference=None,
        percentage_difference=None,
        assessment="insufficient data",
        reason=reason,
        comparable_items=[],
    )


def _listing_similarity(new_item: dict, listing: dict) -> int:
    score = 0

    if (new_item.get("category") or "").lower() == (
        listing.get("category") or ""
    ).lower():
        score += 8

    shared_styles = _normalized_set(new_item.get("style_tags")) & _normalized_set(
        listing.get("style_tags")
    )
    score += len(shared_styles) * 4

    if (new_item.get("size") or "").strip().lower() == (
        listing.get("size") or ""
    ).strip().lower():
        score += 3

    new_brand = (new_item.get("brand") or "").strip().lower()
    listing_brand = (listing.get("brand") or "").strip().lower()
    if new_brand and new_brand == listing_brand:
        score += 3

    if (new_item.get("condition") or "").strip().lower() == (
        listing.get("condition") or ""
    ).strip().lower():
        score += 2

    shared_colors = _normalized_set(new_item.get("colors")) & _normalized_set(
        listing.get("colors")
    )
    score += len(shared_colors)

    return score


def compare_price(new_item: dict, listings: list[dict] | None = None) -> dict:
    """
    Compare a selected listing price against similar mock listings.

    Args:
        new_item: Selected listing dict from the search results.
        listings: Optional comparison pool. If omitted, all mock listings load
                  from the local dataset.

    Returns:
        A structured price comparison dict with assessment, averages,
        differences, and comparable listing summaries. Returns an
        "insufficient data" assessment instead of raising for missing data.
    """
    item_price = None
    if isinstance(new_item, dict) and _usable_price(new_item.get("price")):
        item_price = float(new_item["price"])
    else:
        return _insufficient_price_data(
            item_price=None,
            reason="There is not enough comparable price data because the selected listing has no usable price.",
        )

    if listings is None:
        try:
            listings = load_listings()
        except Exception:
            return _insufficient_price_data(
                item_price=item_price,
                reason="There is not enough comparable price data because listings could not be loaded.",
            )

    if not isinstance(listings, list):
        return _insufficient_price_data(
            item_price=item_price,
            reason="There is not enough comparable price data because the comparison listings are unavailable.",
        )

    selected_id = new_item.get("id")
    scored_listings = []
    for index, listing in enumerate(listings):
        if not isinstance(listing, dict):
            continue
        if selected_id and listing.get("id") == selected_id:
            continue
        if not _usable_price(listing.get("price")):
            continue

        similarity_score = _listing_similarity(new_item, listing)
        if similarity_score <= 0:
            continue

        scored_listings.append((similarity_score, index, listing))

    scored_listings.sort(key=lambda item: (-item[0], item[1]))
    top_comparables = scored_listings[:5]

    if not top_comparables:
        return _insufficient_price_data(
            item_price=item_price,
            reason="There is not enough comparable price data for this listing yet.",
        )

    comparable_prices = [float(listing["price"]) for _, _, listing in top_comparables]
    average_price = round(sum(comparable_prices) / len(comparable_prices), 2)
    median_price = round(float(median(comparable_prices)), 2)
    price_difference = round(item_price - average_price, 2)
    percentage_difference = round((price_difference / average_price) * 100, 2)

    if percentage_difference <= -10:
        assessment = "good deal"
    elif percentage_difference > 10:
        assessment = "above average"
    else:
        assessment = "fair price"

    if price_difference < 0:
        direction = "below"
        difference_text = abs(price_difference)
    elif price_difference > 0:
        direction = "above"
        difference_text = price_difference
    else:
        direction = "at"
        difference_text = 0

    if direction == "at":
        reason = (
            f"This listing is at the average price of "
            f"{len(top_comparables)} comparable items, so it is classified as "
            f"{assessment}."
        )
    else:
        reason = (
            f"This listing is ${difference_text:.2f} {direction} the average "
            f"price of {len(top_comparables)} comparable items, so it is "
            f"classified as {assessment}."
        )

    comparable_items = []
    for similarity_score, _, listing in top_comparables:
        comparable_items.append(
            {
                "id": listing.get("id"),
                "title": listing.get("title"),
                "price": float(listing["price"]),
                "category": listing.get("category"),
                "size": listing.get("size"),
                "condition": listing.get("condition"),
                "platform": listing.get("platform"),
                "similarity_score": similarity_score,
            }
        )

    return _price_comparison_result(
        item_price=item_price,
        comparable_count=len(comparable_items),
        average_price=average_price,
        median_price=median_price,
        price_difference=price_difference,
        percentage_difference=percentage_difference,
        assessment=assessment,
        reason=reason,
        comparable_items=comparable_items,
    )


def _format_style_profile(profile: dict | None) -> str:
    if not isinstance(profile, dict):
        return "No saved style preferences."

    profile_labels = [
        ("Preferred colors", "preferred_colors"),
        ("Preferred styles", "preferred_styles"),
        ("Preferred fits", "preferred_fits"),
        ("Preferred shoes", "preferred_shoes"),
        ("Preferred bottoms", "preferred_bottoms"),
        ("Preferred layers", "preferred_layers"),
    ]
    profile_lines = []
    for label, field in profile_labels:
        values = [
            str(value).strip()
            for value in profile.get(field, [])
            if str(value).strip()
        ]
        if values:
            profile_lines.append(f"- {label}: {', '.join(values)}")

    if not profile_lines:
        return "No saved style preferences."
    return "\n".join(profile_lines)


# tool 2: suggest_outfit

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    # validate the selected item before building the outfit prompt
    if not isinstance(new_item, dict) or not new_item.get("title"):
        return (
            "I could not create an outfit because the selected listing is missing. "
            "Please search for an item first."
        )

    # keep the item summary limited to fields that help with styling
    item_summary = (
        f"Item: {new_item.get('title')}\n"
        f"Category: {new_item.get('category', 'unknown')}\n"
        f"Description: {new_item.get('description', 'No description provided')}\n"
        f"Size: {new_item.get('size', 'unknown')}\n"
        f"Colors: {', '.join(new_item.get('colors') or []) or 'unknown'}\n"
        f"Style tags: {', '.join(new_item.get('style_tags') or []) or 'none'}"
    )

    # use general styling guidance when the wardrobe has no usable pieces
    wardrobe_items = []
    if isinstance(wardrobe, dict):
        wardrobe_items = [
            item for item in wardrobe.get("items", []) if isinstance(item, dict)
        ]
    style_profile_text = _format_style_profile(
        wardrobe.get("style_profile") if isinstance(wardrobe, dict) else None
    )

    if wardrobe_items:
        wardrobe_lines = []
        for item in wardrobe_items:
            colors = ", ".join(item.get("colors") or []) or "unknown colors"
            styles = ", ".join(item.get("style_tags") or []) or "no style tags"
            notes = item.get("notes") or "no notes"
            wardrobe_lines.append(
                f"- {item.get('name', 'Unnamed item')} "
                f"({item.get('category', 'unknown category')}; "
                f"colors: {colors}; styles: {styles}; notes: {notes})"
            )
        wardrobe_text = "\n".join(wardrobe_lines)
        wardrobe_instruction = (
            "Use the user's wardrobe items when they fit. Do not invent owned "
            "items that are not listed here."
        )
    else:
        wardrobe_text = "No usable wardrobe items were provided."
        wardrobe_instruction = (
            "Give general styling advice. Do not claim the user owns specific "
            "pieces. Suggest common bottoms, shoes, layers, or accessories."
        )

    # keep the prompt focused on one useful styling answer
    prompt = f"""
You are helping style one secondhand listing for a user.

Selected listing:
{item_summary}

User wardrobe:
{wardrobe_text}

Saved style preferences:
{style_profile_text}

Instructions:
- Return only the outfit suggestion.
- Suggest one or two complete outfit combinations.
- Make the outfit specific to the selected listing.
- Include practical details like layering, shoes, accessories, color balance, or fit.
- {wardrobe_instruction}
- Use saved style preferences when they are available.
- Do not describe saved style preferences as clothing the user owns.
- Keep the response concise and natural.
""".strip()

    # return a clear message when the model request cannot be completed
    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You give concise outfit suggestions and return only "
                        "the suggestion text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=350,
        )
        outfit_text = response.choices[0].message.content.strip()
    except ValueError:
        return (
            "I could not generate an outfit because the Groq API key is not "
            "configured. Add GROQ_API_KEY to the local .env file and try again."
        )
    except Exception:
        return (
            "I found the item, but the outfit service could not complete the "
            "request. Check that GROQ_API_KEY is configured and try again."
        )

    if not outfit_text:
        return (
            "I found the item, but the outfit suggestion came back empty. "
            "Please try again."
        )

    return outfit_text


# tool 3: create_fit_card

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # validate the outfit before sending it to the caption service
    if not isinstance(outfit, str) or not outfit.strip():
        return (
            "I could not create the fit card because the outfit suggestion is "
            "missing. Generate an outfit first and try again."
        )

    # validate the selected item so the caption has real listing context
    if not isinstance(new_item, dict) or not new_item.get("title"):
        return (
            "I could not create the fit card because the selected listing is "
            "missing. Search for an item first and try again."
        )

    outfit_text = outfit.strip()

    # include only listing details that can make the caption more specific
    item_details = [
        f"Item title: {new_item.get('title')}",
        f"Platform: {new_item.get('platform', 'unknown')}",
        f"Price: ${new_item.get('price')}" if new_item.get("price") is not None else "",
        f"Category: {new_item.get('category', 'unknown')}",
        f"Condition: {new_item.get('condition', 'unknown')}",
        f"Colors: {', '.join(new_item.get('colors') or []) or 'unknown'}",
        f"Style tags: {', '.join(new_item.get('style_tags') or []) or 'none'}",
    ]
    item_summary = "\n".join(detail for detail in item_details if detail)

    # keep the prompt specific enough to vary with different inputs
    prompt = f"""
Create one short shareable fit card caption.

Outfit suggestion:
{outfit_text}

Selected thrift item:
{item_summary}

Instructions:
- Return only one final caption.
- Keep it to 2 to 4 natural sentences.
- Sound like a personal outfit caption, not a product listing.
- Use the outfit details and selected item details.
- Mention useful item facts naturally when available.
- Do not invent missing facts, trend claims, prices, brands, or platforms.
- Do not include markdown headings or reasoning.
""".strip()

    # return a clear message when caption generation cannot finish
    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write concise social outfit captions and return "
                        "only the final caption text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.85,
            max_tokens=180,
        )
        fit_card_text = response.choices[0].message.content.strip()
    except ValueError:
        return (
            "I could not generate the fit card because the Groq API key is not "
            "configured. Add GROQ_API_KEY to the local .env file and try again."
        )
    except Exception:
        return (
            "The listing and outfit are ready, but the fit card service could "
            "not finish. Try generating the fit card again."
        )

    if not fit_card_text:
        return (
            "The outfit is ready, but the fit card came back empty. "
            "Please try again."
        )

    return fit_card_text
