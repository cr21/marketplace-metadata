"""Unit tests for the heuristic PII tagger."""

import pytest

from catalog_agent.catalog.pii import is_pii


@pytest.mark.parametrize(
    "column_name",
    [
        "email",
        "email_address",
        "user_email",
        "phone",
        "phone_number",
        "mobile_number",
        "ssn",
        "social_security_number",
        "dob",
        "date_of_birth",
        "birth_date",
        "birthday",
        "first_name",
        "last_name",
        "full_name",
        "address",
        "home_address",
        "street_address",
        "postal_code",
        "zip_code",
        "credit_card",
        "card_number",
        "cvv",
        "passport",
        "tax_id",
        "national_id",
        "ip_address",
        "ip_addr",
        "gender",
        "ethnicity",
        "salary",
        "income",
        "biometric",
        "fingerprint",
    ],
)
def test_is_pii_flags_sensitive_columns(column_name: str) -> None:
    assert is_pii(column_name) is True, f"Expected {column_name!r} to be flagged as PII"


@pytest.mark.parametrize(
    "column_name",
    [
        "id",
        "user_id",
        "order_id",
        "created_at",
        "updated_at",
        "amount",
        "quantity",
        "price",
        "total",
        "status",
        "is_active",
        "table_name",
        "column_name",
        "file_name",
        "description",
        "category",
        "region",
        "country_code",
        "currency",
        "event_type",
        "version",
    ],
)
def test_is_pii_does_not_flag_non_sensitive_columns(column_name: str) -> None:
    assert is_pii(column_name) is False, f"Expected {column_name!r} NOT to be flagged as PII"


def test_is_pii_case_insensitive() -> None:
    assert is_pii("EMAIL") is True
    assert is_pii("Email_Address") is True
    assert is_pii("PHONE_NUMBER") is True


def test_is_pii_data_type_ignored() -> None:
    # data_type parameter should not affect the result
    assert is_pii("amount", "STRING") is False
    assert is_pii("amount", "FLOAT64") is False
    assert is_pii("email", "STRING") is True
