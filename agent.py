"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re
from copy import deepcopy

from style_profile import (
    extract_style_preferences,
    has_style_preferences,
    load_style_profile,
    save_style_profile,
    update_style_profile,
)
from tools import (
    compare_price,
    create_fit_card,
    get_style_trend,
    search_listings,
    suggest_outfit,
)


# session state

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "style_profile": None,       # normalized saved style preferences
        "style_profile_updated": False,
        "style_profile_message": "",
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "price_comparison": None,    # dict returned by compare_price
        "style_trend": None,         # dict returned by get_style_trend
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# planning loop

def _parse_query(query: str) -> dict:
    """
    Extract a simple description, optional size, and optional budget from a
    natural language query.
    """
    query_text = query or ""
    parsed_query = query_text

    price_match = re.search(r"(?:under|below|less than)\s*\$?\s*(\d+(?:\.\d+)?)", query_text, re.I)
    if not price_match:
        price_match = re.search(r"\$\s*(\d+(?:\.\d+)?)", query_text)
    max_price = float(price_match.group(1)) if price_match else None
    if price_match:
        parsed_query = parsed_query.replace(price_match.group(0), " ")

    size_match = re.search(
        r"(?:in\s+)?size\s+([a-z0-9./-]+)|\b(?:us\s*)?(\d+(?:\.\d+)?)\b",
        parsed_query,
        re.I,
    )
    size = None
    if size_match:
        size = (size_match.group(1) or size_match.group(2)).upper()
        parsed_query = parsed_query.replace(size_match.group(0), " ")

    # clean search wording without trying to fully understand natural language
    parsed_query = re.sub(
        r"\b(i am|i'm|looking for|searching for|find me|want|need|please|usually wear|mostly wear)\b",
        " ",
        parsed_query,
        flags=re.I,
    )
    parsed_query = re.sub(r"[,.!?]", " ", parsed_query)
    description = " ".join(parsed_query.split()) or query_text.strip()

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


def _tool_text_failed(value: str | None) -> bool:
    """
    Return True when a tool output is empty or clearly reports a failure.
    """
    if not isinstance(value, str) or not value.strip():
        return True

    value_lower = value.lower()
    failure_signals = [
        "could not",
        "not configured",
        "missing",
        "came back empty",
        "service could not complete",
    ]
    return any(signal in value_lower for signal in failure_signals)


def _prepare_style_profile(query: str) -> tuple[dict, bool, str]:
    # load saved preferences before checking the current request
    loaded_profile = load_style_profile()
    new_preferences = extract_style_preferences(query)

    if not has_style_preferences(new_preferences):
        if has_style_preferences(loaded_profile):
            return loaded_profile, False, "Loaded saved style profile."
        return loaded_profile, False, "No saved style preferences yet."

    # merge new preferences without removing earlier style choices
    updated_profile = update_style_profile(loaded_profile, new_preferences)
    if save_style_profile(updated_profile):
        return updated_profile, True, "Style profile updated from this request."

    return (
        updated_profile,
        False,
        "Style profile could not be saved, but the search can continue.",
    )


def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # initialize one session object so each tool can pass its result forward
    session = _new_session(query, wardrobe)

    # keep style memory optional so storage never blocks the main workflow
    (
        session["style_profile"],
        session["style_profile_updated"],
        session["style_profile_message"],
    ) = _prepare_style_profile(query)

    # parse only the filters this starter app expects
    session["parsed"] = _parse_query(query)

    search_results = search_listings(
        description=session["parsed"]["description"],
        size=session["parsed"]["size"],
        max_price=session["parsed"]["max_price"],
    )
    session["search_results"] = search_results

    # stop here because later tools require a valid selected listing
    if not search_results:
        session["error"] = (
            "I could not find any listings that match that description, size, "
            "and budget. Try increasing the budget, removing the size filter, "
            "or using a broader description."
        )
        return session

    # store the exact selected item before passing it to the outfit tool
    session["selected_item"] = session["search_results"][0]

    # compare the selected listing price before styling; insufficient data is OK
    session["price_comparison"] = compare_price(
        new_item=session["selected_item"],
    )

    # match the selected item against the small curated trend dataset
    session["style_trend"] = get_style_trend(
        new_item=session["selected_item"],
        size=session["parsed"].get("size"),
    )

    # add the profile to a wardrobe copy so the original input stays unchanged
    wardrobe_with_profile = deepcopy(session["wardrobe"])
    if not isinstance(wardrobe_with_profile, dict):
        wardrobe_with_profile = {"items": []}
    wardrobe_with_profile["style_profile"] = session["style_profile"]
    # keep trend context optional so the required workflow can continue
    wardrobe_with_profile["style_trend"] = session["style_trend"]

    outfit_suggestion = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=wardrobe_with_profile,
    )
    session["outfit_suggestion"] = outfit_suggestion

    # prevent fit card generation when the outfit tool reports a failure
    if _tool_text_failed(outfit_suggestion):
        session["error"] = (
            "I found a listing, but the outfit service could not complete the "
            "request. Check that GROQ_API_KEY is configured and try again."
        )
        return session

    fit_card = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )
    session["fit_card"] = fit_card

    # keep the completed outfit state even if caption generation fails
    if _tool_text_failed(fit_card):
        session["error"] = (
            "The listing and outfit are ready, but the fit card service could "
            "not finish. Try generating the fit card again."
        )

    return session


# cli test

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
