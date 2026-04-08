"""Shared phone-number normalization helpers.

Lives in `common/` so both the applicants pipeline (write path, via serializers)
and the calls pipeline (dispatch path, via the AI screening service) can share
a single source of truth.
"""
import re

from django.conf import settings

# E.164: leading "+", then 1..15 digits, first digit 1..9.
E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")


def normalize_phone(phone) -> str:
    """
    Normalize a raw phone string to E.164 format.

    Steps:
    1. Strip whitespace, dashes, and parentheses.
    2. Convert a "00" international prefix into "+".
    3. If the number already starts with "+", validate as-is.
    4. Otherwise, strip a single leading "0" (trunk prefix used for local
       dialing in India/UK/etc.).
    5. If the resulting number already begins with the configured country
       code AND is long enough to be a fully-qualified number, just add "+".
       Otherwise, prepend the full country code (e.g. "+91").
    6. Validate the final result against the E.164 pattern.

    The length check in step 5 disambiguates cases like "9142982138" — a
    10-digit Indian mobile that starts with the digits "91" — from
    "919142982138", which is the same number with country code embedded.

    Raises ValueError if the result still isn't a valid E.164 number.
    """
    if phone is None:
        raise ValueError("Phone number is empty.")

    normalized = re.sub(r"[\s\-\(\)]", "", str(phone))
    if not normalized:
        raise ValueError("Phone number is empty.")

    # "00<cc>..." is the international dialing form — convert to "+<cc>..."
    if normalized.startswith("00"):
        normalized = "+" + normalized[2:]

    if not normalized.startswith("+"):
        country_code = getattr(settings, "DEFAULT_PHONE_COUNTRY_CODE", "+91") or "+91"
        if not country_code.startswith("+"):
            country_code = "+" + country_code
        cc_digits = country_code[1:]  # e.g. "91"

        local_length = getattr(settings, "DEFAULT_PHONE_LOCAL_LENGTH", 10) or 10
        fully_qualified_length = local_length + len(cc_digits)

        # Strip a single leading "0" (trunk prefix for local dialing).
        if normalized.startswith("0"):
            normalized = normalized.lstrip("0")

        # If the number is long enough AND starts with the country-code digits,
        # treat it as already country-coded — just prepend "+".
        if (
            cc_digits
            and normalized.startswith(cc_digits)
            and len(normalized) >= fully_qualified_length
        ):
            normalized = "+" + normalized
        else:
            normalized = country_code + normalized

    if not E164_PATTERN.match(normalized):
        raise ValueError(
            f"Phone number '{phone}' could not be normalized to E.164 format "
            f"(got '{normalized}'). Expected something like +14155552671."
        )
    return normalized
