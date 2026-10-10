"""
Input sanitization applied before anything is stored.

We strip control characters (incl. NULs) and trim. We deliberately do NOT
HTML-escape at storage time or alter Unicode (emoji must reach the model
untouched); the frontend renders everything via textContent, so output
encoding happens at display time.
"""
import re

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(value: str) -> str:
    return _CONTROL_CHARS.sub("", value).strip()
