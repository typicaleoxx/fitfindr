# FitFindr planning.md

Complete this document before writing any implementation code. This plan is the source of truth for the next phases of implementation.

## Project Purpose

FitFindr helps a user turn a natural language secondhand shopping request into a styled outfit idea. The user describes what they want, the app searches mock secondhand listings, chooses a matching item, uses the user's wardrobe state to suggest how to wear it, and generates a short shareable fit card caption.

## Tool Specifications

### Tool 1: search_listings

**Function signature:**
`search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`

**Function name:**
`search_listings`

**Exact parameter names, types, and meanings:**
- `description` (`str`): Keywords or a phrase from the user's request, such as `"vintage graphic tee"`. This is used to compare against listing text and style fields.
- `size` (`str | None`): Optional size filter from the user's request, such as `"M"` or `"US 8"`. If it is `None`, size filtering is skipped.
- `max_price` (`float | None`): Optional maximum price from the user's request. If it is `None`, price filtering is skipped.

**Exact return type:**
`list[dict]`

**Specific contents of the return value:**
The function returns matching listing dictionaries sorted by relevance, best match first. Each listing dict has these fields from `data/listings.json`: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

**Normal behavior:**
The tool loads listings with `load_listings()`, filters by `max_price` and `size` only when those parameters are provided, scores the remaining listings by keyword overlap with `description`, drops listings with a score of `0`, sorts matches by score descending, and returns the matching listing dicts.

**Specific failure mode:**
If no listings match the filters and description, the tool returns an empty list. It does not raise an exception for no matches.

**What the workflow does after that failure:**
The workflow writes the empty list to `session["search_results"]`, sets `session["error"]` to a helpful no-results message, returns the session early, and does not call `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**Function signature:**
`suggest_outfit(new_item: dict, wardrobe: dict) -> str`

**Function name:**
`suggest_outfit`

**Exact parameter names, types, and meanings:**
- `new_item` (`dict`): The selected listing dict from `session["selected_item"]`. It contains the thrifted item the user is considering buying.
- `wardrobe` (`dict`): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. It comes from `session["wardrobe"]` and may be the example wardrobe or the empty wardrobe template.

**Exact return type:**
`str`

**Specific contents of the return value:**
The function returns a non-empty outfit suggestion string. With a populated wardrobe, the string should suggest one or two complete outfits using the selected listing and named pieces from `wardrobe["items"]`. With an empty wardrobe, the string should give general styling advice for the selected listing instead of referencing closet items that do not exist.

**Normal behavior:**
The tool checks `wardrobe["items"]`. If the list has items, it formats the wardrobe and selected listing into a prompt and asks for outfit combinations. If the list is empty, it asks for general styling ideas for the selected listing.

**Specific failure mode:**
If the wardrobe is empty or minimal, the tool should still return a useful styling string. If the text request raises an exception or returns unusable text, the tool should return a clear fallback styling message rather than an empty string.

**What the workflow does after that failure:**
The workflow validates the returned string. If it is non-empty, it stores it in `session["outfit_suggestion"]` and continues. If it is empty or only whitespace, it sets `session["error"]` to a message explaining that an outfit could not be generated, returns early, and does not call `create_fit_card`.

---

### Tool 3: create_fit_card

**Function signature:**
`create_fit_card(outfit: str, new_item: dict) -> str`

**Function name:**
`create_fit_card`

**Exact parameter names, types, and meanings:**
- `outfit` (`str`): The outfit suggestion string from `session["outfit_suggestion"]`.
- `new_item` (`dict`): The selected listing dict from `session["selected_item"]`.

**Exact return type:**
`str`

**Specific contents of the return value:**
The function returns a two to four sentence caption string for an Instagram or TikTok style fit card. The caption should mention the item name, price, and platform once each, and should describe the outfit vibe using details from `outfit` and `new_item`.

**Normal behavior:**
The tool checks that `outfit` is not empty or whitespace, builds a prompt with the outfit suggestion and selected listing details, and returns the generated caption string.

**Specific failure mode:**
If `outfit` is empty or missing, the tool returns a descriptive error message string and does not raise an exception. If the text request raises an exception or cannot return usable text, the tool should return a clear fallback caption or error string.

**What the workflow does after that failure:**
The workflow checks the returned fit card string. If it is usable, it stores it in `session["fit_card"]` and returns the completed session. If it is empty or clearly an error message from missing outfit input, it sets `session["error"]`, leaves `session["fit_card"]` as `None` or the error string based on implementation choice, and returns the session.

---

### Tool 4: compare_price

**Function signature:**
`compare_price(new_item: dict, listings: list[dict] | None = None) -> dict`

**Function name:**
`compare_price`

**Exact parameter names, types, and meanings:**
- `new_item` (`dict`): The selected listing dict from `session["selected_item"]`. It contains the item price and listing attributes to compare against other secondhand listings.
- `listings` (`list[dict] | None`): Optional list of listing dicts to use as the comparison pool. If it is `None`, the tool loads all mock listings with `load_listings()`.

**Exact return type:**
`dict`

**Specific contents of the return value:**
The function returns a price comparison dict with `item_price`, `comparable_count`, `average_price`, `median_price`, `price_difference`, `percentage_difference`, `assessment`, `reason`, and `comparable_items`. Each comparable item summary includes `id`, `title`, `price`, `category`, `size`, `condition`, `platform`, and `similarity_score`.

**Normal behavior:**
The tool compares the selected listing against other listings using category, style tags, size, brand, condition, and colors. Category has the highest weight, style tags have strong weight, size and brand have moderate weight, and condition and colors have smaller weight. The selected listing itself is excluded by matching `id`. The tool keeps the top three to five most similar listings with usable prices, calculates average price, median price, price difference, and percentage difference, then classifies the selected item as `good deal`, `fair price`, or `above average`.

**Specific failure mode:**
If `new_item` is missing a usable price, the listings cannot be loaded, or there are no comparable listings with prices, the tool returns a structured dict with `assessment` set to `"insufficient data"`, zero comparable count, `None` for calculated prices and differences, a clear `reason`, and an empty `comparable_items` list.

**What the workflow does after that failure:**
The workflow stores the returned dict in `session["price_comparison"]` and continues to `suggest_outfit`. Price comparison is helpful context, not a required blocker for styling or fit card generation.

### Additional Tools

The required version uses the first three tools. The stretch version adds `compare_price` as a fourth local tool. Query parsing will happen inside `run_agent` before calling `search_listings`.

## Planning Loop

The planning loop is implemented by `run_agent(query: str, wardrobe: dict) -> dict` in `agent.py`. It should use conditional logic and should not call every tool unconditionally.

1. Initialize `session` by calling `_new_session(query, wardrobe)`.
2. Parse the user request into search parameters. The parser should extract:
   - `description`: the main item and style words, such as `"vintage graphic tee"`.
   - `size`: a size phrase if present, such as `"M"` or `"US 8"`, otherwise `None`.
   - `max_price`: a dollar amount after words like `"under"` or `"$"`, converted to `float`, otherwise `None`.
3. Store the parsed values in `session["parsed"]`, for example `{"description": "vintage graphic tee", "size": "M", "max_price": 30.0}`.
4. Call `search_listings(description=session["parsed"]["description"], size=session["parsed"]["size"], max_price=session["parsed"]["max_price"])`.
5. Store the returned list in `session["search_results"]`.
6. Check `session["search_results"]` immediately after search.
7. If the list is empty, set `session["error"]` to a clear no-results message and return the session early.
8. The workflow stops on an empty result because there is no selected listing to pass into `suggest_outfit`, and creating an outfit or fit card without an item would make later outputs unreliable.
9. If results exist, choose the first listing because `search_listings` sorts best matches first.
10. Store that listing in `session["selected_item"]`.
11. Pass the same stored listing into `compare_price` by calling `compare_price(new_item=session["selected_item"])`.
12. Store the returned dict in `session["price_comparison"]`.
13. Continue even when the price comparison assessment is `"insufficient data"` because the styling tools only require a selected listing.
14. Pass the same stored listing into `suggest_outfit` by calling `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`.
15. Validate the outfit result by checking that it is a string and not empty after stripping whitespace.
16. If the outfit result is not usable, set `session["error"]` and return early.
17. If usable, store it in `session["outfit_suggestion"]`.
18. Pass the same stored outfit and listing into `create_fit_card` by calling `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`.
19. Validate the fit card result by checking that it is a string and not empty after stripping whitespace.
20. Store the fit card in `session["fit_card"]` when usable. If it is not usable, set `session["error"]`.
21. Return the final session dict. On success, `session["error"]` is `None` and the selected listing, price comparison, outfit suggestion, and fit card are all available.

## State Management

The actual session structure is created by `_new_session(query, wardrobe)` in `agent.py`.

| State key | What it stores | When it is written | Later reader |
|---|---|---|---|
| `query` | The original user query string. | Written when `_new_session` is called. | The query parser in `run_agent`. |
| `parsed` | A dict containing extracted `description`, `size`, and `max_price`. | Written after query parsing. | `search_listings` call arguments. |
| `search_results` | A list of listing dicts returned by `search_listings`. | Written right after `search_listings` returns. | The result check and selected item step. |
| `selected_item` | The top listing dict chosen from `search_results[0]`. | Written only if search results are not empty. | `compare_price`, `suggest_outfit`, and `create_fit_card`. |
| `price_comparison` | A dict returned by `compare_price` with price assessment, averages, differences, and comparable item summaries. | Written after `selected_item` is stored. | The app price output panel and tests. |
| `wardrobe` | The wardrobe dict passed into `run_agent`, with an `items` list. | Written when `_new_session` is called. | `suggest_outfit`. |
| `outfit_suggestion` | The non-empty string returned by `suggest_outfit`. | Written after outfit validation passes. | `create_fit_card` and the app output. |
| `fit_card` | The caption string returned by `create_fit_card`. | Written after fit card validation passes. | The app output and final user response. |
| `error` | `None` on success, or a user-facing message when the workflow stops early. | Written when search fails, outfit generation fails, fit card generation fails, or the planning loop is not implemented yet. | `app.handle_query`, CLI checks, and tests. |

The user does not manually reenter the selected item, price comparison, or outfit suggestion. The workflow stores the selected listing once in `session["selected_item"]`, reuses that exact dict for price comparison, styling, and caption generation, stores the outfit once in `session["outfit_suggestion"]`, and passes that exact string into `create_fit_card`.

## Error Handling

| Tool | Failure trigger | Tool response | Workflow decision | Specific user facing response | Suggested next action |
|---|---|---|---|---|---|
| `search_listings` | No listings match the parsed `description`, `size`, and `max_price`. | Returns `[]`. | Store `[]` in `session["search_results"]`, set `session["error"]`, return early, and do not call later tools. | `I could not find any matching secondhand listings for that request. Try widening the size, raising the price limit, or using fewer style words.` | User should broaden the search, remove one filter, or try another item type. |
| `compare_price` | The selected item has no usable price, listings cannot load, or no comparable listings have usable prices. | Returns a structured dict with `assessment` set to `"insufficient data"`. | Store the dict in `session["price_comparison"]` and continue to `suggest_outfit`. | `There is not enough comparable price data for this listing yet.` | User can still use the listing, outfit idea, and fit card. I should keep the output readable without blocking the workflow. |
| `suggest_outfit` | `wardrobe["items"]` is empty or has too little useful information. | Returns a general styling suggestion for `new_item` instead of an empty string. | Store the non-empty suggestion and continue to `create_fit_card`. | `I do not have saved closet pieces for you yet, so I made a general styling idea for this item.` | User can keep going or later add wardrobe items for more personal suggestions. |
| `suggest_outfit` | The text request raises an exception or returns unusable text. | Returns a clear fallback styling message if possible. | If fallback text is non-empty, store it and continue. If empty, set `session["error"]` and stop. | `I found a listing, but I could not generate an outfit idea right now. Try again, or use a simpler styling request.` | User should retry or simplify the request. I should check the API key and text request error handling. |
| `create_fit_card` | `outfit` is empty or whitespace. | Returns a descriptive error message string and does not raise an exception. | Treat the missing outfit as a workflow error, set `session["error"]`, and return without a successful fit card. | `I found an item, but I need an outfit suggestion before I can make a fit card.` | I should rerun outfit generation before calling `create_fit_card`. |
| `create_fit_card` | The text request raises an exception or returns unusable text. | Returns a clear fallback caption or an error string. | If the caption is usable, store it in `session["fit_card"]`. If not, set `session["error"]`. | `I found and styled an item, but I could not create the shareable fit card right now. You can still use the listing and outfit idea above.` | User can retry fit card generation. I should check text request availability and prompt output validation. |

## Architecture Diagram

```text
User query
  |
  | raw natural language request
  v
Query parsing inside run_agent
  |
  | parsed: description, size, max_price
  v
Planning loop
  |
  | calls with parsed search parameters
  v
search_listings(description, size, max_price)
  |
  | list[dict] search_results
  v
Search result check
  |                         \
  | results found            \ no results
  v                           v
Session state              Early return error branch
  |                         |
  | selected_item stored    | session["error"] set
  |                         | final session returned
  v
compare_price(new_item=selected_item)
  |
  | price comparison dict
  v
Session state
  |
  | price_comparison stored
  | insufficient data continues
  v
suggest_outfit(new_item=selected_item, wardrobe=session["wardrobe"])
  |
  | outfit suggestion string
  v
Outfit validation
  |                         \
  | usable outfit            \ empty or unusable outfit
  v                           v
Session state              Early return error branch
  |                         |
  | outfit_suggestion stored | session["error"] set
  v                         | final session returned
create_fit_card(outfit=outfit_suggestion, new_item=selected_item)
  |
  | fit card caption string
  v
Final response
  |
  | completed session with selected_item, outfit_suggestion, fit_card, error=None
  v
Returned session dict
```

## Implementation Plan

### Phase 1: Implement `search_listings`

I will use the Tool 1 specification, the `search_listings` signature, the `load_listings()` helper, and the listing fields from `data/listings.json`. I will implement filtering by optional price and size, keyword scoring against listing text and tags, sorting by score, and returning only matching listing dicts. I will inspect the matching logic to make sure it uses the real dataset fields and does not invent fields. Tests should verify at least one successful graphic tee query, one size filtered query, one price filtered query, and one no-results query. The scoring rules can be revised if results feel relevant but appear in a weak order.

### Phase 2: Implement `suggest_outfit`

I will use the Tool 2 specification, the wardrobe schema, the selected listing shape, and the empty wardrobe error row. I will implement the wardrobe check, build prompts for populated and empty wardrobes, call the configured client helper in `tools.py`, and return a non-empty string. I will inspect the prompt to make sure it asks for named wardrobe pieces only when they exist. Tests should verify a populated wardrobe returns text, an empty wardrobe returns general styling advice, and request exceptions are handled without crashing. The exact wording of the prompt can be revised if suggestions sound too generic.

### Phase 3: Implement `create_fit_card`

I will use the Tool 3 specification, the selected listing fields, and the fit card error rows. I will add the empty outfit guard, build the caption prompt, call the configured client, and return a two to four sentence caption string. I will inspect that the prompt asks for the item name, price, platform, and outfit vibe without sounding like a product listing. Tests should verify empty outfit input returns an error string, normal input returns a non-empty caption, and request failure is handled. The caption style can be revised if it does not sound natural.

### Phase 4: Implement the planning loop and state

I will use the Planning Loop, State Management table, Architecture diagram, and Error Handling table. I will implement `run_agent` so it initializes session state, parses the query, calls each tool only when prior state is valid, stores outputs in the existing keys, and returns early on errors. I will inspect that the user never has to reenter the selected item or outfit because state is passed forward. Tests should verify a happy path, a no-results early return, and an outfit failure path. Query parsing can be revised or overridden if simple parsing misses common test queries.

### Phase 5: Connect the interface

I will use the `app.handle_query` TODO, the session structure, and the final response expectations from the walkthrough. I will implement empty query handling, wardrobe selection, `run_agent` calling, error mapping, and readable formatting for the selected listing. I will inspect the Gradio outputs to make sure errors appear in the first panel and successful results fill all three panels. Tests or manual checks should verify both wardrobe choices and the deliberate no-results example. The listing display format can be revised for clarity.

### Phase 6: Add tests

I will use all tool specifications, the planning loop section, and the error handling table. I will write focused pytest tests for each tool and for `run_agent`, using mocks for text generation calls so tests do not require a live request. I will inspect that tests check behavior and state, not exact creative wording. Tests should verify return types, state keys, early returns, and failure responses. I can override brittle assertions if they depend on wording that may change.

### Phase 7: Complete documentation

I will use the finished implementation, README, implementation plan, and interaction walkthrough. I will update documentation with setup steps, environment variable requirements, example queries, how to run the app, and how to run tests. I will inspect that documentation matches the final code and does not promise stretch features that were not built. Verification should include running tests and launching the app locally. Documentation wording can be revised to match my voice.

### Phase 8: Add price comparison stretch tool

I will use the Tool 4 specification, the state table, and the app output contract. I will implement `compare_price` as a local deterministic function that does not call the network, ranks comparable listings with weighted similarity, excludes the selected listing by `id`, and returns a structured assessment dict. I will update `run_agent` to store `session["price_comparison"]` after selecting the item and before generating the outfit. I will add one readable price assessment panel to the interface without redesigning the rest of the app. Tests should verify scoring, calculations, insufficient data, agent state flow, and app formatting. I will review the implementation output against the plan, run the test suite, manually compare an actual listing, and launch the app to confirm the panel appears.

## Complete Interaction Walkthrough

### Happy path

**Example user query:** `"I am looking for a vintage graphic tee under $30 in size M. I usually wear baggy jeans and chunky sneakers."`

**Step 1: Parse the query**
- Tool called: none.
- Exact arguments: none.
- Example parsed value: `{"description": "vintage graphic tee", "size": "M", "max_price": 30.0}`.
- State key updated: `session["parsed"]`.
- Next conditional decision: because `description` is present, call `search_listings`.

**Step 2: Search listings**
- Tool called: `search_listings`.
- Exact arguments: `description="vintage graphic tee"`, `size="M"`, `max_price=30.0`.
- Example return value:

```python
[
    {
        "id": "lst_002",
        "title": "Y2K Baby Tee - Butterfly Print",
        "description": "Super cute early 2000s baby tee with butterfly graphic. Fitted crop length. Tag says medium but fits like a small.",
        "category": "tops",
        "style_tags": ["y2k", "vintage", "graphic tee", "cottagecore"],
        "size": "S/M",
        "condition": "excellent",
        "price": 18.0,
        "colors": ["white", "pink", "purple"],
        "brand": None,
        "platform": "depop",
    }
]
```

- State key updated: `session["search_results"]`.
- Next conditional decision: because the list is not empty, store the first result.

**Step 3: Select the listing**
- Tool called: none.
- Exact arguments: none.
- Example return value: no tool return value.
- State key updated: `session["selected_item"] = session["search_results"][0]`.
- Next conditional decision: because `selected_item` is a listing dict, call `compare_price`.

**Step 4: Compare price**
- Tool called: `compare_price`.
- Exact arguments: `new_item=session["selected_item"]`.
- Example return value:

```python
{
    "item_price": 18.0,
    "comparable_count": 4,
    "average_price": 25.4,
    "median_price": 24.0,
    "price_difference": -7.4,
    "percentage_difference": -29.13,
    "assessment": "good deal",
    "reason": "This listing is $7.40 below the average price of 4 comparable items.",
    "comparable_items": [
        {
            "id": "lst_006",
            "title": "Vintage Bootleg Graphic Tee",
            "price": 24.0,
            "category": "tops",
            "size": "M",
            "condition": "good",
            "platform": "poshmark",
            "similarity_score": 13,
        }
    ],
}
```

- State key updated: `session["price_comparison"]`.
- Next conditional decision: continue to outfit generation even if the assessment is `"insufficient data"`.

**Step 5: Suggest an outfit**
- Tool called: `suggest_outfit`.
- Exact arguments: `new_item=session["selected_item"]`, `wardrobe=session["wardrobe"]`.
- Example return value: `"Wear the Y2K Baby Tee with your baggy straight-leg jeans, chunky white sneakers, and black cropped zip hoodie. Add the black crossbody bag to keep the outfit casual and streetwear leaning."`
- State key updated: `session["outfit_suggestion"]`.
- Next conditional decision: because the outfit string is non-empty, call `create_fit_card`.

**Step 6: Create the fit card**
- Tool called: `create_fit_card`.
- Exact arguments: `outfit=session["outfit_suggestion"]`, `new_item=session["selected_item"]`.
- Example return value: `"Found this Y2K Baby Tee - Butterfly Print on depop for $18, and it is going straight into a relaxed weekend fit. I would wear it with baggy denim, chunky white sneakers, a cropped hoodie, and a black crossbody for a soft vintage streetwear look."`
- State key updated: `session["fit_card"]`.
- Next conditional decision: because the fit card is non-empty, return the final session.

**Final user output:**
The user sees the top listing details, the price assessment, the outfit suggestion, and the shareable fit card caption. `session["error"]` remains `None`.

### No results path

**Example user query:** `"designer ballgown size XXS under $5"`

**Step 1: Parse the query**
- Tool called: none.
- Exact arguments: none.
- Example parsed value: `{"description": "designer ballgown", "size": "XXS", "max_price": 5.0}`.
- State key updated: `session["parsed"]`.
- Next conditional decision: because `description` is present, call `search_listings`.

**Step 2: Search listings**
- Tool called: `search_listings`.
- Exact arguments: `description="designer ballgown"`, `size="XXS"`, `max_price=5.0`.
- Example return value: `[]`.
- State key updated: `session["search_results"]`.
- Next conditional decision: because the list is empty, set `session["error"]` and return early.

**Final user output:**
`I could not find any matching secondhand listings for that request. Try widening the size, raising the price limit, or using fewer style words.`

`compare_price`, `suggest_outfit`, and `create_fit_card` are not called. `session["selected_item"]`, `session["price_comparison"]`, `session["outfit_suggestion"]`, and `session["fit_card"]` remain `None`.
