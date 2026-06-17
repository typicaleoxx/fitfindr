"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import run_agent
from style_profile import clear_style_profile, empty_style_profile
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# query handler

def _format_listing(listing: dict | None) -> str:
    """Format a selected listing for the first output panel."""
    if not isinstance(listing, dict):
        return "No listing is available."

    lines = [listing.get("title") or "Untitled listing"]

    if listing.get("price") is not None:
        lines.append(f"Price: ${listing['price']:.2f}")
    if listing.get("size"):
        lines.append(f"Size: {listing['size']}")
    if listing.get("platform"):
        lines.append(f"Platform: {str(listing['platform']).title()}")
    if listing.get("condition"):
        lines.append(f"Condition: {str(listing['condition']).title()}")
    if listing.get("brand"):
        lines.append(f"Brand: {listing['brand']}")
    if listing.get("colors"):
        lines.append(f"Colors: {', '.join(listing['colors'])}")
    if listing.get("style_tags"):
        lines.append(f"Style: {', '.join(listing['style_tags'])}")

    return "\n".join(lines)


def _format_price_comparison(price_comparison: dict | None) -> str:
    """Format the selected listing's price comparison for the output panel."""
    if not isinstance(price_comparison, dict):
        return "Price comparison is not available."

    assessment = price_comparison.get("assessment") or "insufficient data"
    lines = [f"Assessment: {assessment.title()}"]

    item_price = price_comparison.get("item_price")
    average_price = price_comparison.get("average_price")
    median_price = price_comparison.get("median_price")
    comparable_count = price_comparison.get("comparable_count", 0)
    percentage_difference = price_comparison.get("percentage_difference")

    if item_price is not None:
        lines.append(f"Item price: ${item_price:.2f}")
    if average_price is not None:
        lines.append(f"Average comparable price: ${average_price:.2f}")
    if median_price is not None:
        lines.append(f"Median comparable price: ${median_price:.2f}")
    lines.append(f"Comparable listings: {comparable_count}")
    if percentage_difference is not None:
        lines.append(f"Difference from average: {percentage_difference:+.2f}%")

    reason = (price_comparison.get("reason") or "").strip()
    if reason:
        lines.append("")
        lines.append(reason)

    return "\n".join(lines)


def _format_trend_insight(style_trend: dict | None) -> str:
    """Format the matched trend for the trend insight panel."""
    # show a plain fallback line when no trend matched the selected item
    if not isinstance(style_trend, dict) or not style_trend.get("trend_name"):
        return (
            "No matching trend was found for this item. "
            "The outfit was generated without trend context."
        )

    lines = [f"Trend: {style_trend['trend_name']}"]
    if style_trend.get("styling_note"):
        lines.append(f"Styling note: {style_trend['styling_note']}")
    # show the source so the trend result can be verified
    if style_trend.get("source_platform"):
        lines.append(f"Source: {style_trend['source_platform']}")
    if style_trend.get("checked_at"):
        lines.append(f"Checked: {style_trend['checked_at']}")
    if style_trend.get("match_reason"):
        lines.append(f"Why: {style_trend['match_reason']}")

    return "\n".join(lines)


def _format_style_profile(
    style_profile: dict | None,
    updated: bool = False,
    message: str = "",
) -> str:
    """Format saved style preferences for the profile output panel."""
    labels = [
        ("Colors", "preferred_colors"),
        ("Styles", "preferred_styles"),
        ("Fits", "preferred_fits"),
        ("Shoes", "preferred_shoes"),
        ("Bottoms", "preferred_bottoms"),
        ("Layers", "preferred_layers"),
    ]
    profile = style_profile if isinstance(style_profile, dict) else {}
    lines = ["Saved style profile"]
    has_values = False

    for label, field in labels:
        values = [
            str(value).strip()
            for value in profile.get(field, [])
            if str(value).strip()
        ]
        if values:
            has_values = True
            lines.append(f"{label}: {', '.join(values)}")
        else:
            lines.append(f"{label}: none")

    if not has_values:
        lines.append("")
        lines.append("No saved preferences yet.")

    lines.append("")
    lines.append(f"Updated this request: {'yes' if updated else 'no'}")
    if message:
        lines.append(message)

    return "\n".join(lines)


def handle_clear_style_profile() -> tuple[str, str]:
    # clear the saved profile without touching other application data
    if clear_style_profile():
        return (
            _format_style_profile(
                empty_style_profile(),
                updated=False,
                message="Style profile cleared.",
            ),
            "Style profile cleared.",
        )

    return (
        _format_style_profile(
            empty_style_profile(),
            updated=False,
            message="Style profile could not be cleared.",
        ),
        "Style profile could not be cleared.",
    )


def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str, str, str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:     The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".

    Returns:
        A tuple of five strings:
            (listing_text, style_profile, price_comparison, outfit_suggestion, fit_card)
        Each string maps to one of the five output panels in the UI.

    TODO:
        1. Guard against an empty query (return early with an error message).
        2. Select the wardrobe based on wardrobe_choice.
        3. Call run_agent() with the query and selected wardrobe.
        4. If session["error"] is set, return the error in the first panel
           and empty strings for the other two.
        5. Otherwise, format session["selected_item"] into a readable listing_text
           string and return it along with session["outfit_suggestion"] and
           session["fit_card"].
    """
    # reject an empty request before starting the agent workflow
    query = (user_query or "").strip()
    if not query:
        return (
            "Enter a clothing request before starting the search. Include "
            "details such as the item, size, or maximum price.",
            "",
            "",
            "",
            "",
            "",
            "",
        )

    # choose the starter wardrobe state from the existing radio options
    if wardrobe_choice == "Empty wardrobe (new user)":
        wardrobe = get_empty_wardrobe()
    else:
        wardrobe = get_example_wardrobe()

    session = run_agent(query=query, wardrobe=wardrobe)
    listing_text = _format_listing(session.get("selected_item"))
    profile_text = _format_style_profile(
        session.get("style_profile"),
        updated=bool(session.get("style_profile_updated")),
        message=(session.get("style_profile_message") or "").strip(),
    )
    price_text = _format_price_comparison(session.get("price_comparison"))
    trend_text = _format_trend_insight(session.get("style_trend"))
    outfit_text = (session.get("outfit_suggestion") or "").strip()
    fit_card_text = (session.get("fit_card") or "").strip()
    error_text = (session.get("error") or "").strip()
    # show the retry explanation only when a fallback search actually ran
    status_text = (session.get("fallback_message") or "").strip()

    # clear later outputs when the agent stops on an earlier failure
    if error_text:
        if not session.get("selected_item"):
            return error_text, profile_text, "", "", "", "", status_text
        if not fit_card_text:
            if "fit card" in error_text.lower():
                return listing_text, profile_text, price_text, outfit_text, error_text, trend_text, status_text
            return listing_text, profile_text, price_text, error_text, "", trend_text, status_text
        if not outfit_text:
            return listing_text, profile_text, price_text, error_text, "", trend_text, status_text
        if "fit card" in error_text.lower():
            return listing_text, profile_text, price_text, outfit_text, error_text, trend_text, status_text

    # return values in the same order as the gradio output components
    return (
        listing_text,
        profile_text,
        price_text,
        outfit_text or "No outfit suggestion is available.",
        fit_card_text or "No fit card is available.",
        trend_text,
        status_text,
    )


# interface

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")
        clear_profile_btn = gr.Button("Clear Style Profile")

        search_status_output = gr.Textbox(
            label="🔁 Search status",
            lines=2,
            interactive=False,
        )

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=8,
                interactive=False,
            )
            profile_output = gr.Textbox(
                label="Saved style profile",
                lines=8,
                interactive=False,
            )
            price_output = gr.Textbox(
                label="Price check",
                lines=8,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=8,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=8,
                interactive=False,
            )
            trend_output = gr.Textbox(
                label="📈 Trend insight",
                lines=8,
                interactive=False,
            )
        clear_status = gr.Textbox(
            label="Style profile status",
            lines=1,
            interactive=False,
        )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[
                listing_output,
                profile_output,
                price_output,
                outfit_output,
                fitcard_output,
                trend_output,
                search_status_output,
            ],
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[
                listing_output,
                profile_output,
                price_output,
                outfit_output,
                fitcard_output,
                trend_output,
                search_status_output,
            ],
        )
        clear_profile_btn.click(
            fn=handle_clear_style_profile,
            inputs=[],
            outputs=[profile_output, clear_status],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
