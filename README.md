# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
fitfindr/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   ├── trends.json            # small curated trend snapshot (bonus)
│   └── wardrobe_schema.json   # wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # helper functions for loading the data
├── tools.py                   # the tools: search, outfit, fit card, price, trend
├── style_profile.py           # local style preference memory helpers (bonus)
├── agent.py                   # run_agent planning loop and state management
├── app.py                     # Gradio interface
├── tests/                     # pytest suite for tools, agent, app, profile
├── planning.md                # design doc and source of truth
├── demo_script.md             # recording plan for the demo video
└── requirements.txt           # Python dependencies
```

The runtime style profile is written to `data/style_profile.local.json` at runtime and is gitignored, so personal test data is never committed.

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.

## Running the App and Tests

Run the interface:
```bash
python app.py
```
Then open the localhost URL printed in your terminal (usually http://localhost:7860).

Run the full test suite:
```bash
pytest -v
```

The tests mock the Groq client, so they do not require an API key or a network connection.

## Tools

FitFindr is built from small single purpose tools. The three required tools come first, then the bonus tools.

### search_listings

Purpose:
Searches the mock thrift dataset for listings that match the user constraints.

Inputs:

description (str):
Natural language item description such as `"vintage graphic tee"`.

size (str | None):
Requested clothing size such as `"M"`. When `None`, size filtering is skipped.

max_price (float | None):
Maximum item price. When `None`, price filtering is skipped.

Returns:

`list[dict]` of matching listings, sorted by relevance with the best match first.

Each dictionary includes the dataset fields:

```
id, title, description, category, style_tags,
size, condition, price, colors, brand, platform
```

Failure:

If nothing matches, it returns an empty list rather than raising. The agent checks this state and triggers the retry fallback, and if the relaxed search still finds nothing it gives the user a specific suggestion to broaden the request.

### suggest_outfit

Purpose:
Turns a selected listing plus the user context into one or two complete outfit ideas.

Inputs:

new_item (dict):
The selected listing dictionary stored as `selected_item`.

wardrobe (dict):
A wardrobe dictionary with an `items` list. The agent passes a copy that also carries optional `style_profile` and `style_trend` context.

Returns:

`str` with the outfit suggestion. With a populated wardrobe it references named closet pieces. With an empty wardrobe it gives general styling advice instead of inventing owned items.

Failure:

If the listing is missing, the API key is not set, or the model request fails, it returns a clear message string instead of raising. The agent treats that message as a failure and stops before the fit card.

### create_fit_card

Purpose:
Writes a short shareable caption for the styled thrift find.

Inputs:

outfit (str):
The outfit suggestion string stored as `outfit_suggestion`.

new_item (dict):
The same selected listing dictionary stored as `selected_item`.

Returns:

`str` with a two to four sentence caption that mentions the item name, price, and platform once each and captures the outfit vibe.

Failure:

If the outfit is empty or the listing is missing, it returns a descriptive error string and does not call the model. If the model request fails, it returns a clear fallback message and the agent preserves the completed outfit state.

### compare_price (bonus)

Purpose:
Estimates whether a listing is a good deal by comparing it against similar listings in the dataset.

Inputs:

new_item (dict):
The selected listing dictionary.

listings (list[dict] | None):
Optional comparison pool. When `None`, all mock listings load from the dataset.

Returns:

`dict` with `item_price`, `comparable_count`, `average_price`, `median_price`, `price_difference`, `percentage_difference`, `assessment`, `reason`, and `comparable_items`. The `assessment` is `"good deal"`, `"fair price"`, or `"above average"`.

Failure:

If the item has no usable price, listings cannot load, or there are no comparable listings, it returns a structured dict with `assessment` set to `"insufficient data"` and a clear `reason`. The workflow continues to styling because price context is optional.

### get_style_trend (bonus)

Purpose:
Matches the selected listing against a small curated trend snapshot so the outfit can reflect a current trend.

Inputs:

new_item (dict):
The selected listing dictionary.

size (str | None):
The parsed request size, used only as a light compatibility nudge.

Returns:

`dict` with `trend_name`, `styling_note`, `source_platform`, `source_url`, `checked_at`, and `match_reason`. When nothing matches, every field except `match_reason` is `None`.

Failure:

If the item is invalid or `data/trends.json` is missing or unreadable, it returns the documented empty trend dict. The workflow continues without trend context. It never calls the network or the model.

### style profile helpers (bonus)

`style_profile.py` stores fashion preferences locally so later requests can reuse them. Key functions:

```
load_style_profile() -> dict        # read the saved profile, or an empty one
extract_style_preferences(query)    # pull supported colors, fits, shoes, etc.
update_style_profile(current, new)  # merge without duplicates, refresh timestamp
save_style_profile(profile) -> bool # atomic write to the runtime file
clear_style_profile() -> bool       # reset the saved profile
```

Failure:
A missing file, invalid JSON, or a failed write never raises into the workflow. The loader returns an empty normalized profile, and the search continues even if saving fails.

### retry fallback logic (bonus)

This is planning logic inside `run_agent`, not a tool with its own signature. When the first `search_listings` call returns an empty list, the agent loosens exactly one constraint and retries once. It prefers dropping the size filter, and otherwise raises `max_price` by twenty percent. It never retries more than once.

## Agent Planning Loop

`run_agent(query, wardrobe)` runs one interaction with conditional logic. It does not call every tool unconditionally.

First it loads and updates the style profile, parses the query into `description`, `size`, and `max_price`, and calls `search_listings`.

The agent then checks whether `search_results` contains listings.

If `search_results` is empty:

1. The retry fallback is triggered.
2. The agent loosens one constraint, preferring to remove the size filter, otherwise raising the budget.
3. If the retry succeeds, the workflow continues with the fallback results.
4. If the retry fails, `session["error"]` is set and the later tools are skipped.

If `search_results` contains items:

1. `selected_item` is stored as the top result.
2. `compare_price` runs on the stored item.
3. `get_style_trend` runs on the stored item.
4. `suggest_outfit` receives the stored item plus the wardrobe copy carrying the profile and trend.
5. `create_fit_card` receives the stored outfit string and the stored item.

```
User Query
|
search_listings
|
results?
|
+ no
|   retry fallback (loosen one constraint, once)
|     |
|     + still no  -> set error, skip later tools
|     + yes       -> continue
|
+ yes
store selected item
|
compare_price
|
get_style_trend
|
suggest_outfit
|
store outfit
|
create_fit_card
```

## State Management

The session dictionary is the single source of truth for one interaction. Key fields:

- `query`: the original user request string.
- `search_results`: the list returned by `search_listings`, replaced by the fallback results when a retry runs.
- `selected_item`: the exact top listing dictionary, reused by every later tool.
- `price_comparison`: the dict returned by `compare_price`.
- `style_profile`: the saved and updated style preferences.
- `style_trend`: the dict returned by `get_style_trend`.
- `outfit_suggestion`: the string returned by `suggest_outfit`.
- `fit_card`: the caption returned by `create_fit_card`.
- `error`: `None` on success, or a user facing message when the workflow stops early.

The retry adds `retry_attempted`, `retry_reason`, `original_search_parameters`, `final_search_parameters`, and `fallback_message`.

Flow:

`search_listings` returns a listing. The agent stores that exact dictionary as `selected_item`. The stored `selected_item` is passed into `compare_price`, `get_style_trend`, and `suggest_outfit`. The outfit string returned by `suggest_outfit` is stored as `outfit_suggestion`. The stored `outfit_suggestion` and the same `selected_item` are passed into `create_fit_card`. The user never manually reenters any intermediate result.

## Error Handling

| Tool | Failure | Detection | Agent Response |
|---|---|---|---|
| search_listings | No matching listings. | The returned list is empty. | Retries once with one relaxed constraint. If the retry also fails, it tells the user to broaden the search or raise the budget and skips later tools. |
| suggest_outfit | Missing selected item, missing API key, or generation failure. | The returned string is empty or contains a known failure phrase. | Stops before creating a fit card and explains what needs fixing, such as configuring the API key. |
| create_fit_card | Missing outfit or generation failure. | The returned string is empty or contains a known failure phrase. | Preserves the completed listing and outfit state and explains that the fit card could not be created. |
| compare_price | No usable price, listings cannot load, or no comparable items. | `assessment` is `"insufficient data"`. | Stores the result and continues to styling, since price context is optional. |
| get_style_trend | No trend matches, or `data/trends.json` is missing or invalid. | `trend_name` is `None`. | Stores the empty trend result and continues. The interface notes that no trend was found. |
| style profile storage | Missing file, invalid JSON, or a failed write. | Load returns an empty profile, or save returns `False`. | Continues the workflow and shows a short status message. Storage never blocks the search. |

## Example Workflow

Query:
`"I usually wear neutral colors and oversized fits. Find me a vintage graphic tee under $30 in size M."`

Step 1:
Style profile memory extracts and stores `neutral` colors and `oversized` fits, so later requests can reuse them.

Step 2:
`search_listings` finds matching listings and the top result is stored as `selected_item`.

Step 3:
`compare_price` compares the item against similar listings and reports whether it is a good deal.

Step 4:
`get_style_trend` finds matching trend context, for example a graphic tee layering trend.

Step 5:
`suggest_outfit` builds an outfit using the selected item, the wardrobe, the saved style profile, and the trend context.

Step 6:
`create_fit_card` writes the final shareable caption from the outfit and the item.

## Bonus Features

### Price Comparison

1. Compares the selected listing against other listings in the dataset.
2. Matches on category and style tags, with smaller weight for size, brand, condition, and colors.
3. Calculates the average and median comparable price and the difference from the item price.
4. Returns an assessment of `good deal`, `fair price`, or `above average` with a plain reason.

### Style Profile Memory

1. Stores supported preferences locally in `data/style_profile.local.json`.
2. Loads them at the start of every interaction.
3. A later request reuses saved preferences without the user repeating them.

Interaction 1:
`"I like neutral colors and oversized clothing."`
The profile saves neutral colors and an oversized fit.

Interaction 2:
`"Find me a denim jacket."`
The agent loads the saved profile, so the outfit for the denim jacket still reflects neutral colors and an oversized fit even though interaction 2 never mentions them.

### Trend Awareness

1. Uses a small curated trend snapshot in `data/trends.json`.
2. Shows the data source, such as Pinterest Trends or Google Trends, along with the date it was checked.
3. Adds the trend styling note to outfit generation so the suggestion reflects a current trend.

### Retry Fallback

1. The original search returns no results.
2. The agent loosens one constraint, preferring to drop the size filter, otherwise raising the budget.
3. The interface tells the user exactly what changed, for example that the size filter was removed.

## Spec Reflection

One way the specification helped:

The required tool interfaces kept each part of the app separated. `search_listings` only handles retrieval, `suggest_outfit` only handles styling, and `create_fit_card` only handles the final caption. Because each tool had a fixed signature, I could build and test them one at a time, and the planning loop just moved state between them. When I added the bonus features, the fixed signatures meant I passed extra context through a wardrobe copy instead of changing the tools, which kept the older tests valid.

One divergence and why:

My first design only stopped the workflow when a search failed and told the user to try again. While testing I noticed that a single strict filter, like an exact size, ended the interaction too often even when good listings existed. So I added one controlled retry that loosens a single constraint and explains what it changed. I kept it to exactly one retry so the behavior stays predictable and the loop can never run forever.

## AI Usage

I used AI assistance during this project, and I directed, tested, and verified all of the work myself.

Instance 1: Planning and architecture

I used AI assistance to break the project rubric into smaller implementation milestones. I directed it to help organize the required tools, the planning loop, the state flow, and the testing checklist before I wrote code.

What I reviewed:
I checked the generated plan against the project requirements and revised the parts where the design added unnecessary complexity.

Instance 2: Tool implementation support

I used AI assistance while implementing `search_listings`, `suggest_outfit`, and `create_fit_card`. I directed it to follow my planned interfaces, my error handling requirements, and my testing goals.

What I reviewed:
I checked the function signatures, the state passing behavior, the test cases, and the failure handling. I revised generated code that did not match the expected workflow.

Instance 3: Testing and debugging

I used AI assistance to find missing test cases and edge conditions.

What I reviewed:
I ran the tests myself, inspected the failures, and updated the implementation to match the assignment specification.
