"""Bounded exact spelling aliases shared by authoring and recognition."""

import json
import re


def validate_replacements(aliases):
    error = "ASR replacements must contain at most eight short alphabetic phrases"
    if not isinstance(aliases, dict) or len(aliases) > 8:
        raise ValueError(error)
    for alias, canonical in aliases.items():
        for phrase in (alias, canonical):
            if (
                not isinstance(phrase, str)
                or len(phrase) > 80
                or not 2 <= len(phrase.split(" ")) <= 4
                or not all(word.isalpha() for word in phrase.split(" "))
            ):
                raise ValueError(error)
    if len(json.dumps(aliases, ensure_ascii=False).encode()) > 2048:
        raise ValueError(error)
    # IGNORECASE also equates dotted/dotless I and the Unicode long-s/Kelvin forms.
    for index, alias in enumerate(aliases):
        if any(
            re.fullmatch(re.escape(alias), other, re.IGNORECASE) for other in list(aliases)[:index]
        ):
            raise ValueError(error)
    return aliases


def compile_replacements(raw):
    error = "ASR replacements must contain at most eight short alphabetic phrases"
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 2048:
        raise ValueError(error)
    try:
        aliases = validate_replacements(json.loads(raw))
    except (ValueError, TypeError):
        raise ValueError(error) from None
    # Longest exact phrase wins; one substitution pass cannot cascade mappings.
    ordered = sorted(aliases, key=len, reverse=True)
    patterns = [f"(?P<t{index}>{re.escape(alias)})" for index, alias in enumerate(ordered)]
    pattern = (
        re.compile(r"(?<!\w)(?:" + "|".join(patterns) + r")(?!\w)", re.IGNORECASE)
        if patterns
        else None
    )
    return pattern, {f"t{index}": aliases[alias] for index, alias in enumerate(ordered)}
