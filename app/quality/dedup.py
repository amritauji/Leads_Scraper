from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from . import fields as F

try:  # optional, better fuzzy matching if installed
    from rapidfuzz.fuzz import token_set_ratio as _ratio  # type: ignore

    def _similar(a: str, b: str) -> float:
        return _ratio(a, b) / 100.0
except Exception:  # stdlib fallback, no extra dependency
    from difflib import SequenceMatcher

    def _similar(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()


NAME_MATCH_THRESHOLD = 0.88


@dataclass
class DuplicateGroup:
    canonical_index: int
    member_indices: list[int]
    reason: str
    merged_fields: dict[str, int] = field(default_factory=dict)  # field -> source index it was filled from


def _key_website(lead: dict[str, Any]) -> str | None:
    return lead.get(F.WEBSITE)


def _key_email_domain(lead: dict[str, Any]) -> str | None:
    return lead.get("_norm", {}).get("email_domain")


def _key_company(lead: dict[str, Any]) -> str | None:
    return lead.get("_norm", {}).get("company_key")


def _same(a: dict[str, Any], b: dict[str, Any]) -> tuple[bool, str]:
    """Decide if two cleaned leads are the same entity, and why."""
    wa, wb = _key_website(a), _key_website(b)
    if wa and wb and wa == wb:
        return True, "same_website"

    ea, eb = _key_email_domain(a), _key_email_domain(b)
    if ea and eb and ea == eb and ea not in {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com"}:
        return True, "same_email_domain"

    ca, cb = _key_company(a), _key_company(b)
    if ca and cb:
        if ca == cb:
            return True, "same_company_name"
        if _similar(ca, cb) >= NAME_MATCH_THRESHOLD:
            # require a corroborating signal (same country) to avoid false merges
            la = (a.get(F.CITY_COUNTRY) or "").split(",")[-1].strip().lower()
            lb = (b.get(F.CITY_COUNTRY) or "").split(",")[-1].strip().lower()
            if not la or not lb or la == lb:
                return True, "fuzzy_company_name"
    return False, ""


def _completeness(lead: dict[str, Any]) -> int:
    return sum(1 for k in F.ALL_FIELDS if lead.get(k))


def detect_duplicates(
    leads: list[dict[str, Any]],
    score_of: Callable[[int], float] | None = None,
) -> tuple[list[DuplicateGroup], dict[int, int]]:
    """Cluster duplicate leads.

    Returns (groups, dup_to_canonical) where dup_to_canonical maps a duplicate
    member index to its canonical index. Non-duplicates form singleton groups.
    """
    n = len(leads)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    reasons: dict[frozenset[int], str] = {}
    for i in range(n):
        for j in range(i + 1, n):
            same, reason = _same(leads[i], leads[j])
            if same:
                union(i, j)
                reasons[frozenset((i, j))] = reason

    clusters: dict[int, list[int]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)

    def rank(idx: int) -> tuple[float, int]:
        s = score_of(idx) if score_of else 0.0
        return (s, _completeness(leads[idx]))

    groups: list[DuplicateGroup] = []
    dup_to_canonical: dict[int, int] = {}
    for members in clusters.values():
        canonical = max(members, key=rank)
        reason = "unique"
        if len(members) > 1:
            for m in members:
                if m != canonical:
                    r = reasons.get(frozenset((canonical, m))) or next(
                        (v for k, v in reasons.items() if m in k), "duplicate"
                    )
                    reason = r
                    dup_to_canonical[m] = canonical
        groups.append(DuplicateGroup(canonical_index=canonical, member_indices=sorted(members), reason=reason))
    return groups, dup_to_canonical


def merge_group(leads: list[dict[str, Any]], group: DuplicateGroup, score_of: Callable[[int], float] | None = None) -> dict[str, Any]:
    """Fill null fields on the canonical record from its duplicates (best-scored first)."""
    canonical = dict(leads[group.canonical_index])
    others = [i for i in group.member_indices if i != group.canonical_index]
    if score_of:
        others.sort(key=score_of, reverse=True)
    filled: dict[str, int] = {}
    for src in others:
        for k in F.ALL_FIELDS:
            if k in (F.LEAD_ID, F.DATE):
                continue
            if not canonical.get(k) and leads[src].get(k):
                canonical[k] = leads[src][k]
                filled[k] = src
    group.merged_fields = filled
    return canonical
