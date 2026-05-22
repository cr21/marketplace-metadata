"""Heuristic PII tagger based on column name patterns.

Matches against the column name only (data_type is accepted for future use but
not used in the heuristic — type alone is not a reliable PII signal).

Pattern list is documented in docs/m01-catalog-crawler.md.
"""

import re

# Each pattern is matched case-insensitively against the full column name.
# Patterns use word-boundary anchors where needed to avoid short-name false positives.
_PII_PATTERNS: list[str] = [
    # Contact / identity
    r"email",
    r"phone",
    r"mobile",
    r"ssn",
    r"social_security",
    # Dates of birth
    r"\bdob\b",
    r"date_of_birth",
    r"birth_date",
    r"birthday",
    # Personal names (specific compound forms only, to avoid "table_name" etc.)
    r"first_name",
    r"last_name",
    r"full_name",
    r"display_name",
    r"person_name",
    r"customer_name",
    r"contact_name",
    r"user_name",
    # Location
    r"address",
    r"postal_code",
    r"zip_code",
    r"\bzip\b",
    r"\bstreet\b",
    # Financial
    r"credit_card",
    r"card_number",
    r"card_num",
    r"\bcvv\b",
    r"\bcvc\b",
    r"account_number",
    # Government IDs
    r"passport",
    r"tax_id",
    r"\btin\b",
    r"\bnin\b",
    r"national_id",
    r"drivers_licen",
    r"license_number",
    # Network
    r"ip_address",
    r"ip_addr",
    # Sensitive attributes
    r"\bgender\b",
    r"ethnicity",
    r"\brace\b",
    r"\bsalary\b",
    r"\bincome\b",
    r"biometric",
    r"fingerprint",
]

_COMPILED: list[re.Pattern[str]] = [re.compile(p, re.IGNORECASE) for p in _PII_PATTERNS]


def is_pii(column_name: str, data_type: str = "") -> bool:  # noqa: ARG001
    """Return True if the column name matches any known PII pattern.

    Args:
        column_name: The column name to check.
        data_type: Accepted for API compatibility; not used in the heuristic.

    Returns:
        True if the column is likely PII, False otherwise.
    """
    return any(pattern.search(column_name) for pattern in _COMPILED)
