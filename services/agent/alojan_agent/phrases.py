"""Bounded Turkish speech chunks without splitting decimals or common titles."""

import re

ABBREVIATIONS = {"dr", "prof", "doç", "av", "sn", "no", "vb", "vs", "örn"}


def phrase_end(text):
    for match in re.finditer(r"[.!?,;]", text[:240]):
        at = match.start()
        mark = match.group()
        before, after = text[:at], text[at + 1 :]
        if mark in "!?":
            if not after or after[0].isspace():
                return at + 1
        elif mark == ".":
            if after and not after[0].isspace():
                continue
            word = before.rsplit(maxsplit=1)[-1].casefold() if before.strip() else ""
            # Numeric periods can become decimals/ordinals in the next delta.
            if word in ABBREVIATIONS or (before and before[-1].isdigit()):
                continue
            return at + 1
        elif after and after[0].isspace() and len(before.strip()) >= 40:
            if len(before.split()) >= 4:
                return at + 1
    if len(text) >= 240:
        space = text.rfind(" ", 0, 240)
        return space if space > 0 else 240
    return None
