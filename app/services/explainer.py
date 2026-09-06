"""
AI chat assistant -- uses Groq's free tier.
Reads already-computed watchlist data and explains it in plain language.

The AI NEVER computes scores or decides what is meaningful.
signal_engine.py remains deterministic and unchanged.

The AI only explains/translates already-computed data. It never gives
investment advice, buy/sell recommendations, or price predictions.

"""

import os
from dotenv import load_dotenv
from groq import Groq

# Environment and Groq client setup

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY is not set. AI explanations will use fallback mode.")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


MODEL = "qwen/qwen3.8-27b"


def _format_money(value) -> str:
    """Format a number as rupees, handling missing values safely."""
    if value is None:
        return "N/A"

    try:
        return f"₹{float(value):.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_signed_rupees(value) -> str:
    """Format a gain/loss in rupees, handling missing values safely."""
    if value is None:
        return "N/A"

    try:
        value = float(value)
        sign = "+" if value >= 0 else "-"
        return f"{sign}₹{abs(value):.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _format_number(value) -> str:
    """Format volumes and other numeric values safely."""
    if value is None:
        return "N/A"

    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return str(value)


def _format_decimal(value, decimals: int = 2) -> str:
    """Format a decimal number safely."""
    if value is None:
        return "N/A"

    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def _build_data_summary(stocks: list[dict], only_symbol: str | None = None) -> str:

    lines = []

    for stock in stocks:
        if only_symbol and stock.get("symbol") != only_symbol:
            continue

        if stock.get("price") is None:
            continue

        symbol = stock.get("symbol", "Unknown")
        ltp = _format_money(stock.get("price"))
        change_rupees = _fmt_signed_rupees(stock.get("change_rupees"))
        change_percent = _format_decimal(stock.get("raw_pct_change", 0), 2)
        open_price = _format_money(stock.get("open_price"))
        previous_close = _format_money(stock.get("prev_close"))
        day_high = _format_money(stock.get("day_high"))
        day_low = _format_money(stock.get("day_low"))
        volume = _format_number(stock.get("volume"))
        relative_move = _format_decimal(stock.get("deviation_score"), 2)
        assessment = stock.get("reason_text") or "No assessment available."
        since_visit = stock.get("since_visit_text") or "N/A"

        lines.append(
            f"{symbol}: "
            f"LTP (Last Traded Price) {ltp}; "
            f"change today {change_rupees} ({change_percent}%); "
            f"open {open_price}; "
            f"previous close {previous_close}; "
            f"day high {day_high}; "
            f"day low {day_low}; "
            f"volume {volume}; "
            f"Relative Move {relative_move}x its normal daily range; "
            f"assessment: {assessment}; "
            f"since last visit: {since_visit}."
        )

    return "\n".join(lines) if lines else "No usable stock data is available right now."


MODE_INSTRUCTIONS = {
    "summary": (
        "Give a short, warm factual summary of the whole watchlist. Mention stocks, if any, "
        "with genuinely unusual movement and mention if the rest appear calm. Keep it to 3 to 5 "
        "short sentences. This is only a snapshot: do not define terms and do not explain what "
        "the moves mean for an investor."
    ),
    "terms": (
        "Write a beginner-friendly glossary. Explain each term once only: LTP or Last Traded "
        "Price, open price, previous close, day's high, day's low, volume, change in rupees, "
        "change in percentage, and Relative Move. Relative Move such as 3.0x shows how unusual "
        "today's movement is compared with that one stock's own normal daily movement. Use one "
        "real data example only if useful. Keep the entire answer to approximately 7 to 9 short "
        "sentences. Do not summarise the watchlist and do not evaluate any stock's movement here."
    ),
    "impact_all": (
        "Explain in simple factual terms whether this watchlist looks calm or eventful today. "
        "Mention only stocks that stand out based on their own historical behaviour. Explain "
        "what has already happened, not what may happen next. End by asking whether the user "
        "would like to inspect one specific stock. Do not give an investment recommendation."
    ),
    "impact_one": (
        "Explain this one stock only. State its LTP, its movement today, and whether that movement "
        "is unusual relative to this stock's own historical behaviour. Explain in simple language. "
        "Do not refer to any other stock and do not make predictions or recommendations."
    ),
}


def _fallback_summary(
    stocks: list[dict],
    only_symbol: str | None = None,
    mode: str | None = None,
) -> str:
    """
    Deterministic fallback used when the external AI service is unavailable.
    This guarantees the frontend still receives a useful response.
    """
    relevant = [
        stock
        for stock in stocks
        if stock.get("price") is not None
        and (only_symbol is None or stock.get("symbol") == only_symbol)
    ]

    if not relevant:
        return "No usable stock data is available right now."

    if mode == "terms":
        return (
            "LTP means Last Traded Price, or the most recent price at which the stock was traded. "
            "Open price is the price of the first trade of the day, while previous close is the "
            "final traded price from the previous trading day. Day high and day low are the "
            "highest and lowest prices reached today. Volume is the number of shares traded. "
            "Change in rupees and percentage show how far the LTP moved from the previous close. "
            "Relative Move compares today's move with the same stock's normal daily movement; "
            "a higher number means today's move is more unusual for that stock."
        )

    if mode == "impact_one" and relevant:
        stock = relevant[0]
        return (
            f"{stock.get('symbol', 'This stock')} has an LTP of "
            f"{_format_money(stock.get('price'))}. It changed "
            f"{_fmt_signed_rupees(stock.get('change_rupees'))} today "
            f"({_format_decimal(stock.get('raw_pct_change', 0), 2)}%). "
            f"Its Relative Move is {_format_decimal(stock.get('deviation_score'), 2)}x its "
            f"normal daily range. {stock.get('reason_text') or ''} "
            f"{stock.get('since_visit_text') or ''}"
        ).strip()

    unusual = [
        stock for stock in relevant
        if _safe_float(stock.get("deviation_score"), default=0) >= 2.0
    ]

    if mode == "impact_all":
        if unusual:
            symbols = ", ".join(stock.get("symbol", "Unknown") for stock in unusual[:5])
            return (
                f"The watchlist looks more eventful than usual because {len(unusual)} stock(s) "
                f"showed movement outside their typical range: {symbols}. "
                "These flags are based only on each stock's own historical movement, not on any "
                "comparison with other stocks. Would you like to inspect one specific stock?"
            )

        return (
            "The watchlist appears relatively calm based on the available data. No stock is "
            "showing a Relative Move of 2x or more compared with its own typical daily movement. "
            "Would you like to inspect one specific stock?"
        )

    # Default fallback: summary mode or unrecognised mode.
    highlighted = unusual[:5] if unusual else relevant[:5]
    entries = []

    for stock in highlighted:
        entries.append(
            f"{stock.get('symbol', 'Unknown')}: LTP {_format_money(stock.get('price'))}, "
            f"{_format_decimal(stock.get('raw_pct_change', 0), 2)}% today. "
            f"{stock.get('reason_text') or ''}".strip()
        )

    prefix = (
        "The AI explanation service is temporarily unavailable. "
        "Here is a factual summary from the computed watchlist data: "
    )

    return prefix + " ".join(entries)


def _safe_float(value, default: float = 0.0) -> float:
    """Convert a value to float without raising an exception."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def chat_response(
    stocks: list[dict],
    language: str,
    mode: str | None = None,
    user_message: str | None = None,
    symbol: str | None = None,
) -> str:
    """
    Generate a constrained plain-language explanation of already-computed data.
    The function always returns a string, including when Groq fails.
    """
    only_symbol = symbol if mode == "impact_one" else None
    data_summary = _build_data_summary(stocks, only_symbol=only_symbol)

    if mode and mode in MODE_INSTRUCTIONS:
        task = MODE_INSTRUCTIONS[mode]
    elif user_message:
        task = (
            f'The user asked: "{user_message}". Answer only what they asked, using only the '
            "provided data. Do not invent numbers. Do not give advice. Do not add an unrelated "
            "watchlist summary, glossary, or impact explanation unless the user asked for it."
        )
    else:
        task = "Give a brief, friendly factual summary of the watchlist."

    prompt = (
        f"You are explaining a stock watchlist to someone with no finance background. "
        f"Write entirely in {language}.\n\n"
        f"DATA: These values were already computed by the application. Do not recalculate, "
        f"modify, question, or invent any values.\n{data_summary}\n\n"
        f"TASK:\n{task}\n\n"
        f"STRICT RULES:\n"
        f"1. Stay strictly within the requested task.\n"
        f"2. Never provide investment advice, trading advice, buy or sell suggestions, "
        f"recommendations, or future price predictions.\n"
        f"3. Never mention sectors, industries, sector-relative movement, peers, or market-wide "
        f"comparisons. Every stock is assessed only against its own history.\n"
        f"4. Call the displayed latest price LTP or Last Traded Price, never current price.\n"
        f"5. Use only facts in DATA. If the data does not answer the question, say that plainly.\n"
        f"6. Use a warm, simple, plain-language tone suitable for a beginner.\n"
        f"7. Do not use Markdown: no headings, bullets, asterisks, tables, or bold formatting.\n"
        f"8. Be concise but complete."
    )

    if client is None:
        print("GROQ SKIPPED: GROQ_API_KEY is missing.")
        return _fallback_summary(stocks, only_symbol=only_symbol, mode=mode)

    try:
        print("\n========== GROQ CALL START ==========")
        print(f"Model      : {MODEL}")
        print(f"Language   : {language}")
        print(f"Mode       : {mode}")
        print(f"Symbol     : {symbol}")
        print(f"API Key Set: {bool(GROQ_API_KEY)}")
        print("=====================================\n")

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a safe, concise stock-watchlist explainer. "
                        "You never give investment advice, recommendations, or predictions. "
                        "You only explain supplied data in simple language."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.2,
            max_tokens=650,
        )

        reply = response.choices[0].message.content

        if not reply or not reply.strip():
            print("GROQ ERROR: Groq returned an empty response.")
            return _fallback_summary(stocks, only_symbol=only_symbol, mode=mode)

        print("GROQ CALL SUCCESSFUL")
        return reply.strip()

    except Exception as error:
        print("\n========== GROQ ERROR ==========")
        print(f"Error Type : {type(error).__name__}")
        print(f"Error Msg  : {error}")
        print("================================\n")

        return _fallback_summary(stocks, only_symbol=only_symbol, mode=mode)