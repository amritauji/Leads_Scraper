from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from . import fields as F

_NULL_TOKENS = {"", "n/a", "na", "null", "none", "-", "--", "unknown", "not found", "tbd"}
_WS = re.compile(r"\s+")
_HONORIFICS = re.compile(r"^(mr|mrs|ms|dr|prof|sir)\.?\s+", re.IGNORECASE)
_YEAR = re.compile(r"(1[6-9]\d{2}|20\d{2})")
_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

_COUNTRY_CANON = {
    "india": "India", "in": "India", "bharat": "India",
    "usa": "USA", "us": "USA", "u.s.": "USA", "u.s.a.": "USA",
    "united states": "USA", "united states of america": "USA", "america": "USA",
    "uk": "UK", "u.k.": "UK", "united kingdom": "UK", "britain": "UK",
    "uae": "UAE", "united arab emirates": "UAE",
    "germany": "Germany", "deutschland": "Germany",
    "singapore": "Singapore", "sg": "Singapore",
    "canada": "Canada", "australia": "Australia", "france": "France",
    "japan": "Japan", "china": "China",
}

_REVENUE_MULT = {
    "k": 1_000, "thousand": 1_000,
    "m": 1_000_000, "mn": 1_000_000, "million": 1_000_000,
    "b": 1_000_000_000, "bn": 1_000_000_000, "billion": 1_000_000_000,
    "cr": 10_000_000, "crore": 10_000_000, "crores": 10_000_000,
    "lakh": 100_000, "lac": 100_000, "l": 100_000,
}
_CURRENCY_SYMBOL = {"$": "USD", "\u20b9": "INR", "\u20ac": "EUR", "\u00a3": "GBP", "\u00a5": "JPY"}
_CURRENCY_CODE = {"usd", "inr", "eur", "gbp", "jpy", "rs", "rs.", "inr."}


def _nullify(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        s = _WS.sub(" ", value).strip()
        return None if s.lower() in _NULL_TOKENS else s
    return value


def clean_text(value: Any) -> str | None:
    v = _nullify(value)
    return v if isinstance(v, str) else (None if v is None else str(v))


def clean_name(value: Any) -> str | None:
    v = _nullify(value)
    if not isinstance(v, str):
        return None
    v = _HONORIFICS.sub("", v).strip()
    return v or None


def clean_domain(value: Any) -> str | None:
    """Return a bare, lowercased registrable host: https://WWW.Foo.com/x -> foo.com"""
    v = _nullify(value)
    if not isinstance(v, str):
        return None
    raw = v.strip()
    if "://" not in raw:
        raw = "http://" + raw
    host = (urlparse(raw).netloc or "").lower().strip()
    if not host:
        return None
    host = host.split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None


def clean_email(value: Any) -> str | None:
    v = _nullify(value)
    if not isinstance(v, str):
        return None
    e = v.strip().lower()
    return e if _EMAIL.match(e) else e or None  # keep raw even if malformed; validation flags it


def clean_year(value: Any) -> str | None:
    v = _nullify(value)
    if v is None:
        return None
    m = _YEAR.search(str(v))
    return m.group(1) if m else None


def clean_linkedin(value: Any) -> str | None:
    v = _nullify(value)
    if not isinstance(v, str):
        return None
    raw = v.strip()
    if "linkedin.com" not in raw.lower():
        # a bare handle like "in/jane-doe" or "jane-doe"
        slug = raw.strip("/")
        if slug and "/" not in slug:
            return f"https://www.linkedin.com/in/{slug}"
        if slug.startswith(("in/", "company/", "pub/")):
            return f"https://www.linkedin.com/{slug}"
        return raw or None
    parsed = urlparse(raw if "://" in raw else "https://" + raw)
    path = parsed.path.rstrip("/")
    return f"https://www.linkedin.com{path}" if path else None


def clean_city_country(value: Any) -> str | None:
    v = _nullify(value)
    if not isinstance(v, str):
        return None
    parts = [p.strip() for p in v.split(",") if p.strip()]
    if not parts:
        return None
    tail = parts[-1]
    canon = _COUNTRY_CANON.get(tail.lower())
    if canon:
        parts[-1] = canon
    else:
        parts[-1] = tail.title()
    parts[:-1] = [p.title() for p in parts[:-1]]
    return ", ".join(parts)


def parse_revenue(value: Any) -> dict[str, Any] | None:
    """Return {'raw','amount','currency'} or None. amount may be None if unparseable."""
    v = _nullify(value)
    if not isinstance(v, str):
        return None
    raw = v.strip()
    low = raw.lower()

    currency = None
    for sym, code in _CURRENCY_SYMBOL.items():
        if sym in raw:
            currency = code
            break
    if currency is None:
        for code in _CURRENCY_CODE:
            if re.search(rf"\b{re.escape(code)}\b", low):
                currency = "INR" if code.startswith("rs") else code.upper()
                break

    num_match = re.search(r"([\d,]+(?:\.\d+)?)", low)
    amount: float | None = None
    if num_match:
        number = float(num_match.group(1).replace(",", ""))
        mult = 1
        for token, factor in _REVENUE_MULT.items():
            if re.search(rf"{re.escape(token)}\b", low[num_match.end():]) or re.search(
                rf"\b{re.escape(token)}\b", low
            ):
                mult = factor
                break
        amount = number * mult

    return {"raw": raw, "amount": amount, "currency": currency}


def clean_lead(lead: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with normalized values. Adds derived keys under '_norm'."""
    out = dict(lead)

    out[F.COMPANY_NAME] = clean_text(lead.get(F.COMPANY_NAME))
    out[F.CATEGORY] = clean_text(lead.get(F.CATEGORY))
    out[F.SEGMENT] = clean_text(lead.get(F.SEGMENT))
    out[F.INDUSTRY] = clean_text(lead.get(F.INDUSTRY))
    out[F.WEBSITE] = clean_domain(lead.get(F.WEBSITE))
    out[F.FOUNDED] = clean_year(lead.get(F.FOUNDED))
    out[F.CITY_COUNTRY] = clean_city_country(lead.get(F.CITY_COUNTRY))
    out[F.CEO_NAME] = clean_name(lead.get(F.CEO_NAME))
    out[F.MKT_NAME] = clean_name(lead.get(F.MKT_NAME))
    out[F.CEO_LINKEDIN] = clean_linkedin(lead.get(F.CEO_LINKEDIN))
    out[F.MKT_LINKEDIN] = clean_linkedin(lead.get(F.MKT_LINKEDIN))
    out[F.CONTACT_EMAIL] = clean_email(lead.get(F.CONTACT_EMAIL))

    rev = parse_revenue(lead.get(F.REVENUE))
    out[F.REVENUE] = rev["raw"] if rev else None

    out["_norm"] = {
        "revenue": rev,
        "email_domain": (out[F.CONTACT_EMAIL].split("@")[-1] if out.get(F.CONTACT_EMAIL) and "@" in out[F.CONTACT_EMAIL] else None),
        "company_key": _company_key(out.get(F.COMPANY_NAME)),
    }
    return out


def _company_key(name: str | None) -> str | None:
    if not name:
        return None
    s = name.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(
        r"\b(pvt|private|ltd|limited|llp|llc|inc|incorporated|corp|corporation|co|company|group|technologies|technology|tech|solutions|systems|india|global|international)\b",
        " ",
        s,
    )
    s = _WS.sub(" ", s).strip()
    return s or None
