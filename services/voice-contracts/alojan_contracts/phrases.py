"""Bounded Turkish speech chunks without splitting decimals or common titles."""

import re

from alojan_contracts.configuration import SPEECH_ABBREVIATIONS as ABBREVIATIONS


def phrase_end(text, max_chars=240):
    for match in re.finditer(r"[.!?,;]", text[:max_chars]):
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
    if len(text) >= max_chars:
        space = text.rfind(" ", 0, max_chars)
        return space if space > 0 else max_chars
    return None
