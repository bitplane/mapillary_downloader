"""Build query-variant lists for Mapillary location search.

Given an OSMNames row (dict with ``name``, ``alternative_names``, ``wikipedia``),
produce an ordered list of query strings to try in sequence. Mapillary's search
is multilingual but patchy — mainland Chinese Hanzi returns nothing, while the
corresponding English endonym ("Beijing", "Shanghai") reliably hits. A simple
"first alphabetical Latin alt" heuristic yields garbage like ``Šangaj`` or
``IMoskwa``; we instead pick the strongest candidate from each of a few tiers.
"""

import unicodedata


def _is_latin_script(s):
    """True if every alphabetic character in s is Latin-script."""
    for ch in s:
        if ch.isalpha() and not unicodedata.name(ch, "").startswith("LATIN"):
            return False
    return True


def _is_clean_ascii(s):
    """Pure ASCII letters with optional space, hyphen, apostrophe, or period, capitalised."""
    if not s or not s[0].isupper():
        return False
    if not s.isascii():
        return False
    stripped = s
    for ch in " -'.":
        stripped = stripped.replace(ch, "")
    return bool(stripped) and stripped.isalpha()


def _has_non_ascii(s):
    return any(ord(c) > 127 for c in s)


def get_variants(row):
    """Return an ordered list of query variants for an OSMNames city row.

    Args:
        row: dict with keys ``name``, ``alternative_names``, ``wikipedia``.
             Missing values treated as empty strings.

    Returns:
        List of query strings in priority order, deduplicated case-insensitively.
        Max length 4. Native name is always first.
    """
    name = (row.get("name") or "").strip()
    wiki = (row.get("wikipedia") or "").strip()
    alts_raw = (row.get("alternative_names") or "").strip()

    variants = []
    seen = set()

    def add(candidate):
        if not candidate:
            return
        key = candidate.lower()
        if key in seen:
            return
        seen.add(key)
        variants.append(candidate)

    add(name)

    if wiki.startswith("en:"):
        add(wiki[3:].strip())

    alts = [a.strip() for a in alts_raw.split(",") if a.strip()] if alts_raw else []
    latin_alts = [a for a in alts if _is_latin_script(a)]

    clean_ascii = next((a for a in latin_alts if _is_clean_ascii(a)), None)
    if clean_ascii:
        add(clean_ascii)

    with_diacritics = next((a for a in latin_alts if _has_non_ascii(a)), None)
    if with_diacritics:
        add(with_diacritics)

    return variants
