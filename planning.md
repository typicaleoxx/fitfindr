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

### Tool 5: get_style_trend

**Function signature:**
`get_style_trend(new_item: dict, size: str | None = None) -> dict`

**Function name:**
`get_style_trend`

**Exact parameter names, types, and meanings:**
- `new_item` (`dict`): The selected listing dict from `session["selected_item"]`. Its `category` and `style_tags` are matched against the curated trend snapshot.
- `size` (`str | None`): Optional parsed size from the user request, such as `"M"`. It is only used as a small compatibility nudge, never as a hard filter. If it is `None`, size is ignored.

**Exact return type:**
`dict`

**Specific contents of the return value:**
The function returns a trend dict with `trend_name`, `styling_note`, `source_platform`, `source_url`, `checked_at`, and `match_reason`. On a match these fields describe the single best matching trend and how it matched. When nothing matches, every field except `match_reason` is `None` and `match_reason` explains that no trend was found.

**Local trend dataset structure:**
The trends live in `data/trends.json`, a small curated trend snapshot of about four to six records. Each record has `trend_name`, `categories` (list), `style_tags` (list), `sizes` (list), `styling_note`, `source_platform`, `source_url`, and `checked_at`. The categories and style tags mirror values already present in `data/listings.json`. The file is curated by hand from public trend pages and does not update automatically.

**How the selected item matches a trend:**
The tool normalizes the selected item `category` and `style_tags`, then scores each trend record. A shared category is the strongest signal and is weighted highest. Each shared style tag adds a smaller amount to the score. The highest scoring record with a positive score wins, and ties resolve to the earliest record in file order so the result is deterministic.

**How size is considered:**
Size is only a small compatibility check. If `size` is provided and it appears in the trend record `sizes`, the score gets a small bonus. A size mismatch never removes a trend from consideration, because trend relevance is about category and style, not exact fit.

**What happens when no trend matches:**
The tool returns the documented empty trend dict with `None` values and a clear `match_reason`. The agent stores that result and continues the required workflow without interruption.

**How trend context reaches `suggest_outfit`:**
`run_agent` attaches `wardrobe_with_profile["style_trend"] = session["style_trend"]` to the same wardrobe copy that already carries the style profile. The original wardrobe is not mutated. `suggest_outfit` reads optional `style_trend` context and, when `trend_name`, `styling_note`, and `source_platform` are present, adds them to the prompt and asks the model to incorporate the styling note into the recommendation without describing the trend as clothing the user owns.

**How the trend appears in the interface:**
A compact Trend Insight panel shows the trend name, styling note, source platform, checked date, and match reason. It never shows raw JSON. When no trend matches it shows a short line saying no matching trend was found and that the outfit was generated without trend context.

**How the feature will be tested:**
Tests cover a matching item returning a full trend dict, the documented fields being present, category or style tag matching selecting the expected trend, the empty result on no match, invalid item and missing file not crashing, the input item staying unchanged, deterministic output, agent state flow and call order, trend context reaching the wardrobe copy, the styling note appearing in the prompt, and the interface display for both the matched and unmatched cases. Groq is mocked and no network request is made.

**How generated code will be reviewed:**
I will confirm the tool is deterministic, makes no network or model calls, does not mutate the selected item, handles missing files and fields safely, keeps the three required tool signatures unchanged, leaves price comparison and style profile memory intact, and uses real public source names in the dataset. I will inspect the diff, run targeted and full tests, and verify the trend visibly affects the outfit prompt.

### Additional Tools

The required version uses the first three tools. The stretch version adds `compare_price` as a fourth local tool, style profile helpers in `style_profile.py`, and `get_style_trend` as a fifth local tool backed by `data/trends.json`. Query parsing will happen inside `run_agent` before calling `search_listings`.

## Style Profile Memory

Style Profile Memory stores clear fashion preferences from earlier requests so later outfit suggestions can use them without the user repeating the same details.

**What style information is stored:**
The profile stores only fashion preferences needed by this project: `preferred_colors`, `preferred_styles`, `preferred_fits`, `preferred_shoes`, `preferred_bottoms`, `preferred_layers`, and `updated_at`. It does not store API keys, personal identifiers, email addresses, full chat history, or unrelated user data.

**Where it is stored:**
The runtime profile is stored in `data/style_profile.local.json`. This file is created at runtime and ignored by Git so personal style data from testing is not committed. The documented empty profile structure is created in code by `style_profile.py` instead of committing real user data.

**How preferences are extracted from a user request:**
`extract_style_preferences(query: str) -> dict` uses a deterministic phrase parser. It looks for supported color, style, fit, shoe, bottom, and layer terms that are clearly present in the request, such as `neutral`, `vintage`, `oversized`, `baggy jeans`, and `chunky sneakers`. It does not call the text service and does not infer sensitive or unrelated traits.

**When a new profile is created:**
A new empty profile is created in memory when the runtime profile file is missing. If the current query contains supported preferences, those preferences are merged into the empty structure and saved to `data/style_profile.local.json`.

**When an existing profile is loaded:**
At the start of every `run_agent` call, `load_style_profile()` reads the saved runtime file if it exists. The loaded profile is normalized before the query is parsed for listings or any tool is called.

**How new preferences update an existing profile:**
`update_style_profile(current_profile, new_preferences)` returns a new dict that preserves existing values, appends newly found values, removes empty values, normalizes values to lowercase where appropriate, and updates `updated_at` with a clear UTC timestamp. Existing preferences are not replaced just because the current query is shorter.

**How duplicate values are avoided:**
Each preference list is normalized and merged in stable order. A value already present in the profile is not added again, so repeated phrases like `baggy jeans` or `chunky sneakers` remain single entries.

**How the profile reaches `suggest_outfit`:**
`run_agent` makes a copy of the wardrobe dict, attaches `wardrobe_with_profile["style_profile"] = session["style_profile"]`, and passes that copy into `suggest_outfit(new_item, wardrobe)`. The original wardrobe object is not mutated. `suggest_outfit` reads optional `style_profile` context from the wardrobe dict and separates saved preferences from owned wardrobe items in the prompt.

**What happens when no profile exists:**
The workflow uses the empty normalized profile structure. Outfit generation still works normally, and the profile display says no saved preferences yet.

**What happens when the storage file is missing:**
`load_style_profile()` returns an empty normalized profile without raising. If the current request has preferences, the profile is saved during the same interaction.

**What happens when the storage file contains invalid data:**
Invalid JSON, missing fields, unsupported fields, or non-list preference fields are ignored safely. The loader returns an empty or normalized profile and the main workflow continues.

**How the user can clear the saved profile:**
The interface includes a Clear Style Profile control. It calls `clear_style_profile()`, resets the runtime file to the empty profile structure, updates the profile display, and returns a clear success or failure message without restarting the app.

**How the feature will be tested:**
Tests cover missing, valid, invalid, incomplete, and unsupported profile file data; saving; mocked write failure; merging and duplicate removal; deterministic extraction; clearing; agent state flow; wardrobe copy behavior; prompt inclusion; app display; output order; and two-interaction memory reuse with mocked text responses.

**How generated code will be reviewed and revised:**
I will compare the implementation against this plan, inspect the diff, confirm comments stay short and natural, run targeted and full tests, verify the runtime profile file is ignored, and revise any behavior that mutates input data, stores unsupported information, changes required tool signatures, weakens price comparison, or blocks the main workflow on storage failure.

**How the feature will be demonstrated using two interactions:**
First, the user submits `I usually wear neutral colors, oversized tops, baggy jeans, and chunky sneakers. Find me a vintage graphic tee under $30 in size M.` The profile saves `neutral`, `oversized`, `baggy jeans`, and `chunky sneakers`. Second, the user submits `Find me a denim jacket under $45 in size M.` The second outfit prompt includes those saved preferences even though they are not repeated in the second request.

## Planning Loop

The planning loop is implemented by `run_agent(query: str, wardrobe: dict) -> dict` in `agent.py`. It should use conditional logic and should not call every tool unconditionally.

1. Initialize `session` by calling `_new_session(query, wardrobe)`.
2. Load the saved style profile with `load_style_profile()`.
3. Extract new style preferences from the current query with `extract_style_preferences(query)`.
4. Merge and save the profile only when useful preferences are found.
5. Store `session["style_profile"]`, `session["style_profile_updated"]`, and `session["style_profile_message"]`.
6. Continue the main workflow even when profile storage fails.
7. Parse the user request into search parameters. The parser should extract:
   - `description`: the main item and style words, such as `"vintage graphic tee"`.
   - `size`: a size phrase if present, such as `"M"` or `"US 8"`, otherwise `None`.
   - `max_price`: a dollar amount after words like `"under"` or `"$"`, converted to `float`, otherwise `None`.
8. Store the parsed values in `session["parsed"]`, for example `{"description": "vintage graphic tee", "size": "M", "max_price": 30.0}`.
9. Call `search_listings(description=session["parsed"]["description"], size=session["parsed"]["size"], max_price=session["parsed"]["max_price"])`.
10. Store the returned list in `session["search_results"]`.
11. Check `session["search_results"]` immediately after search.
12. If the list is empty, set `session["error"]` to a clear no-results message and return the session early.
13. The workflow stops on an empty result because there is no selected listing to pass into `suggest_outfit`, and creating an outfit or fit card without an item would make later outputs unreliable.
14. If results exist, choose the first listing because `search_listings` sorts best matches first.
15. Store that listing in `session["selected_item"]`.
16. Pass the same stored listing into `compare_price` by calling `compare_price(new_item=session["selected_item"])`.
17. Store the returned dict in `session["price_comparison"]`.
18. Continue even when the price comparison assessment is `"insufficient data"` because the styling tools only require a selected listing.
19. Pass the same stored listing into `get_style_trend` by calling `get_style_trend(new_item=session["selected_item"], size=session["parsed"]["size"])`.
20. Store the returned dict in `session["style_trend"]`.
21. Continue even when no trend matched because trend context is optional.
22. Create a wardrobe copy, attach `session["style_profile"]` and `session["style_trend"]` to it, and pass that copy into `suggest_outfit`.
23. Validate the outfit result by checking that it is a string and not empty after stripping whitespace.
24. If the outfit result is not usable, set `session["error"]` and return early.
25. If usable, store it in `session["outfit_suggestion"]`.
26. Pass the same stored outfit and listing into `create_fit_card` by calling `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`.
27. Validate the fit card result by checking that it is a string and not empty after stripping whitespace.
28. Store the fit card in `session["fit_card"]` when usable. If it is not usable, set `session["error"]`.
29. Return the final session dict. On success, `session["error"]` is `None` and the selected listing, price comparison, style profile, style trend, outfit suggestion, and fit card are all available.

## State Management

The actual session structure is created by `_new_session(query, wardrobe)` in `agent.py`.

| State key | What it stores | When it is written | Later reader |
|---|---|---|---|
| `query` | The original user query string. | Written when `_new_session` is called. | The query parser in `run_agent`. |
| `style_profile` | The normalized saved style profile, possibly updated with current query preferences. | Written after profile load, extraction, and optional save. | `suggest_outfit`, the app profile output, and tests. |
| `style_profile_updated` | `True` when new current-query preferences were saved successfully, otherwise `False`. | Written during profile handling at the start of `run_agent`. | The app profile output and tests. |
| `style_profile_message` | A short status message such as loaded, updated, unavailable, or empty. | Written during profile handling at the start of `run_agent`. | The app profile output and tests. |
| `parsed` | A dict containing extracted `description`, `size`, and `max_price`. | Written after query parsing. | `search_listings` call arguments. |
| `search_results` | A list of listing dicts returned by `search_listings`. | Written right after `search_listings` returns. | The result check and selected item step. |
| `selected_item` | The top listing dict chosen from `search_results[0]`. | Written only if search results are not empty. | `compare_price`, `suggest_outfit`, and `create_fit_card`. |
| `price_comparison` | A dict returned by `compare_price` with price assessment, averages, differences, and comparable item summaries. | Written after `selected_item` is stored. | The app price output panel and tests. |
| `style_trend` | A dict returned by `get_style_trend` with the best matching trend or a documented empty result. | Written after `price_comparison`, before `suggest_outfit`. | `suggest_outfit`, the app trend insight panel, and tests. |
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
| Style profile storage | The profile file is missing. | `load_style_profile()` returns the empty normalized profile. | Continue normally and save a new runtime file only if the current query contains supported preferences. | `No saved style preferences yet.` | User can keep searching. New clear preferences in the request will create the profile. |
| Style profile storage | The profile file contains invalid JSON or unsupported fields. | `load_style_profile()` ignores invalid data and returns a normalized profile. | Continue the main workflow and avoid exposing raw file errors. | `Style profile was reset because saved data could not be read.` | I should keep the profile optional and avoid blocking search or styling. |
| Style profile storage | Saving or clearing the profile fails. | `save_style_profile()` or `clear_style_profile()` returns `False`. | Continue listing search, price comparison, outfit generation, and fit card generation. | `Style profile could not be saved, but the search can continue.` | User can still use all main outputs. I should check local file permissions. |
| `get_style_trend` | No trend matches the selected item, or `data/trends.json` is missing or invalid. | Returns the documented empty trend dict with `None` values and a clear `match_reason`. | Store the dict in `session["style_trend"]` and continue to `suggest_outfit`. | `No matching trend was found for this item. The outfit was generated without trend context.` | User can still use the listing, price check, outfit idea, and fit card. Trend context is optional. |
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
Style profile memory
  |
  | load saved profile, extract current preferences, save useful updates
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
get_style_trend(new_item=selected_item, size=parsed size)
  |
  | style_trend dict, no match continues
  v
Session state
  |
  | style_trend stored
  v
Wardrobe copy with style_profile and style_trend attached
  |
  | original wardrobe stays unchanged
  v
suggest_outfit(new_item=selected_item, wardrobe=wardrobe_with_profile)
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

### Phase 9: Add style profile memory

I will use the Style Profile Memory section, the storage approach, and the existing session structure. I will create `style_profile.py` with `load_style_profile`, `save_style_profile`, `update_style_profile`, `extract_style_preferences`, and `clear_style_profile`. I will store runtime data in ignored `data/style_profile.local.json`, load and update it at the start of `run_agent`, attach the normalized profile to a wardrobe copy before calling `suggest_outfit`, and add a compact profile display plus a clear control in the interface. Tests should verify helper behavior, prompt context, agent state flow, app output order, clear action, and the two-interaction memory proof. I will revise any part that stores unsupported data, mutates the original wardrobe, changes required tool signatures, blocks the main workflow on storage failure, or weakens price comparison.

### Phase 10: Add trend awareness stretch tool

I will use the Tool 5 specification, the curated `data/trends.json` snapshot, and the existing session structure. I will add `get_style_trend(new_item, size=None)` to `tools.py` as a small deterministic function that loads the trend snapshot, scores trends by shared category and style tags, uses size only as a small compatibility nudge, and returns the best matching trend or the documented empty result. It makes no network or model calls and does not mutate the selected item. I will call it in `run_agent` after the selected item is stored and before `suggest_outfit`, store the result in `session["style_trend"]`, and attach it to the same wardrobe copy that carries the style profile. I will extend the `suggest_outfit` prompt so it incorporates the trend styling note when one is present, without describing the trend as owned clothing. I will add one compact Trend Insight panel to the interface without redesigning the rest of the app. Tests should verify matching, fields, the empty result, safe failure, no mutation, determinism, agent state flow, prompt inclusion, and app display. I will review the implementation against the plan, run the test suite, confirm price comparison and style profile memory still work, and launch the app to confirm the trend visibly affects the outfit. The trend snapshot is curated by hand from public trend pages and does not update automatically. I will not add live scraping, scheduled jobs, a database, or retry fallback in this phase.

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
- Next conditional decision: continue to trend lookup even if the assessment is `"insufficient data"`.

**Step 5: Look up a style trend**
- Tool called: `get_style_trend`.
- Exact arguments: `new_item=session["selected_item"]`, `size=session["parsed"]["size"]`.
- Example return value:

```python
{
    "trend_name": "graphic tee layering",
    "styling_note": "layer the graphic tee over a fitted long sleeve top",
    "source_platform": "Pinterest Trends",
    "source_url": "https://trends.pinterest.com/",
    "checked_at": "2026-06-17",
    "match_reason": "Matched the tops category and the vintage style tag.",
}
```

- State key updated: `session["style_trend"]`.
- Next conditional decision: continue to outfit generation even if no trend matched.

**Step 6: Suggest an outfit**
- Tool called: `suggest_outfit`.
- Exact arguments: `new_item=session["selected_item"]`, `wardrobe=wardrobe_with_profile` (a copy carrying the style profile and the style trend).
- Example return value: `"Wear the Y2K Baby Tee with your baggy straight-leg jeans, chunky white sneakers, and black cropped zip hoodie. Add the black crossbody bag to keep the outfit casual and streetwear leaning."`
- State key updated: `session["outfit_suggestion"]`.
- Next conditional decision: because the outfit string is non-empty, call `create_fit_card`.

**Step 7: Create the fit card**
- Tool called: `create_fit_card`.
- Exact arguments: `outfit=session["outfit_suggestion"]`, `new_item=session["selected_item"]`.
- Example return value: `"Found this Y2K Baby Tee - Butterfly Print on depop for $18, and it is going straight into a relaxed weekend fit. I would wear it with baggy denim, chunky white sneakers, a cropped hoodie, and a black crossbody for a soft vintage streetwear look."`
- State key updated: `session["fit_card"]`.
- Next conditional decision: because the fit card is non-empty, return the final session.

**Final user output:**
The user sees the top listing details, the price assessment, the trend insight, the outfit suggestion, and the shareable fit card caption. The outfit visibly reflects the trend styling note. `session["error"]` remains `None`.

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

`compare_price`, `get_style_trend`, `suggest_outfit`, and `create_fit_card` are not called. `session["selected_item"]`, `session["price_comparison"]`, `session["style_trend"]`, `session["outfit_suggestion"]`, and `session["fit_card"]` remain `None`.

### Style profile memory two interaction walkthrough

**Interaction one query:** `"I usually wear neutral colors, oversized tops, baggy jeans, and chunky sneakers. Find me a vintage graphic tee under $30 in size M."`

**Interaction one profile handling**
- Tool called: none.
- Helper functions called: `load_style_profile()`, `extract_style_preferences(query)`, `update_style_profile(current_profile, new_preferences)`, and `save_style_profile(updated_profile)`.
- Example extracted preferences:

```python
{
    "preferred_colors": ["neutral"],
    "preferred_styles": [],
    "preferred_fits": ["oversized"],
    "preferred_shoes": ["chunky sneakers"],
    "preferred_bottoms": ["baggy jeans"],
    "preferred_layers": [],
}
```

- State keys updated: `session["style_profile"]`, `session["style_profile_updated"]`, and `session["style_profile_message"]`.
- Expected result: the runtime profile stores neutral colors, oversized fit, baggy jeans, and chunky sneakers.

**Interaction one outfit generation**
- `run_agent` attaches the updated profile to a wardrobe copy.
- `suggest_outfit` sees owned wardrobe items separately from saved preferences.
- The outfit prompt includes saved preferences and asks the outfit suggestion to use them without claiming they are owned clothing.

**Interaction two query:** `"Find me a denim jacket under $45 in size M."`

**Interaction two profile handling**
- Tool called: none.
- Helper functions called: `load_style_profile()` and `extract_style_preferences(query)`.
- Example extracted preferences:

```python
{
    "preferred_colors": [],
    "preferred_styles": [],
    "preferred_fits": [],
    "preferred_shoes": [],
    "preferred_bottoms": [],
    "preferred_layers": [],
}
```

- State keys updated: `session["style_profile"]`, `session["style_profile_updated"]`, and `session["style_profile_message"]`.
- Expected result: the saved profile loads without the user repeating neutral colors, oversized fit, baggy jeans, or chunky sneakers.

**Interaction two outfit generation**
- `run_agent` attaches the loaded profile to a wardrobe copy.
- `suggest_outfit` receives the saved preferences from interaction one.
- The second outfit suggestion can use neutral colors, oversized fit, baggy jeans, and chunky sneakers even though the second query only asks for a denim jacket.
