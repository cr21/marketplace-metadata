"""Unit tests for the LLM enricher.

OpenAI calls are fully mocked — no API key required.
"""

import json
from unittest.mock import MagicMock

from catalog_agent.catalog.llm_enricher import enrich_catalog_row
from catalog_agent.catalog.models import CatalogRow, ColumnRecord


def _make_row(
    asset: str = "users",
    asset_type: str = "TABLE",
    table_description: str = "",
    columns: list[ColumnRecord] | None = None,
) -> CatalogRow:
    return CatalogRow(
        project_id="proj",
        dataset_id="ds",
        asset=asset,
        asset_type=asset_type,
        table_metadata={"description": table_description},
        columns=columns or [],
    )


def _mock_openai(response_json: dict) -> MagicMock:
    """Build a mock OpenAI client whose chat.completions.create returns response_json."""
    message = MagicMock()
    message.content = json.dumps(response_json)
    choice = MagicMock()
    choice.message = message
    completion = MagicMock()
    completion.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client


def test_enriches_missing_column_description() -> None:
    row = _make_row(
        columns=[
            ColumnRecord(name="email", data_type="STRING", description=""),
            ColumnRecord(name="id", data_type="INT64", description="Primary key"),
        ]
    )
    llm_response = {
        "table_description": "",
        "columns": [
            {
                "name": "email",
                "description": "Customer email address",
                "is_pii": True,
                "pii_rationale": "Email is a personal identifier",
            }
        ],
    }
    client = _mock_openai(llm_response)
    result = enrich_catalog_row(row, client, "gpt-4o-mini")

    col_map = {c.name: c for c in result.columns}
    assert col_map["email"].description == "Customer email address"
    assert col_map["email"].is_pii is True
    # Column with existing description is unchanged
    assert col_map["id"].description == "Primary key"


def test_skips_columns_that_already_have_descriptions() -> None:
    row = _make_row(
        table_description="Already documented",
        columns=[
            ColumnRecord(name="id", data_type="INT64", description="Primary key"),
            ColumnRecord(name="amount", data_type="FLOAT64", description="Order total"),
        ],
    )
    client = _mock_openai({})
    result = enrich_catalog_row(row, client, "gpt-4o-mini")

    # No LLM call should be made — both columns already have descriptions
    client.chat.completions.create.assert_not_called()
    assert result is row  # same object returned


def test_generates_table_description_when_missing() -> None:
    row = _make_row(table_description="")
    llm_response = {
        "table_description": "Stores user account information",
        "columns": [],
    }
    client = _mock_openai(llm_response)
    result = enrich_catalog_row(row, client, "gpt-4o-mini")

    assert result.table_metadata["description"] == "Stores user account information"


def test_does_not_overwrite_existing_table_description() -> None:
    row = _make_row(
        table_description="Existing description",
        columns=[ColumnRecord(name="id", data_type="INT64", description="")],
    )
    llm_response = {
        "table_description": "LLM description",
        "columns": [
            {"name": "id", "description": "Primary key", "is_pii": False, "pii_rationale": ""}
        ],
    }
    client = _mock_openai(llm_response)
    result = enrich_catalog_row(row, client, "gpt-4o-mini")

    # table_description was already set — must NOT be overwritten
    assert result.table_metadata["description"] == "Existing description"


def test_pii_rationale_stored_in_table_metadata() -> None:
    row = _make_row(
        columns=[ColumnRecord(name="ssn", data_type="STRING", description="")],
    )
    llm_response = {
        "table_description": "Tax records",
        "columns": [
            {
                "name": "ssn",
                "description": "Social security number",
                "is_pii": True,
                "pii_rationale": "SSN is a government ID",
            }
        ],
    }
    client = _mock_openai(llm_response)
    result = enrich_catalog_row(row, client, "gpt-4o-mini")

    assert result.table_metadata.get("pii_rationale", {}).get("ssn") == "SSN is a government ID"


def test_llm_failure_returns_original_row() -> None:
    row = _make_row(columns=[ColumnRecord(name="email", data_type="STRING", description="")])
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("API unavailable")

    result = enrich_catalog_row(row, client, "gpt-4o-mini")

    # Must return the original row unchanged — crawl never fails due to LLM errors
    assert result.columns[0].description == ""
    assert result is row


def test_no_llm_call_when_nothing_to_enrich() -> None:
    """If all columns have descriptions and table has a description, skip the LLM."""
    row = _make_row(
        table_description="Already documented",
        columns=[
            ColumnRecord(name="id", data_type="INT64", description="Primary key"),
        ],
    )
    client = _mock_openai({})
    enrich_catalog_row(row, client, "gpt-4o-mini")
    client.chat.completions.create.assert_not_called()
