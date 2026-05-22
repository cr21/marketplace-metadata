"""BigQuery client factory."""

import json

from google.cloud import bigquery
from google.oauth2 import service_account

from catalog_agent.config import Settings


def get_bq_client(settings: Settings) -> bigquery.Client:
    """Return an authenticated BigQuery client.

    Uses a service-account JSON when GOOGLE_APPLICATION_CREDENTIALS points to
    a file with type "service_account"; otherwise falls back to Application
    Default Credentials (which also respects GOOGLE_APPLICATION_CREDENTIALS for
    ADC-format files like those created by `gcloud auth application-default login`).
    """
    if settings.google_application_credentials:
        try:
            with open(settings.google_application_credentials) as f:
                cred_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            cred_data = {}

        if cred_data.get("type") == "service_account":
            credentials = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                settings.google_application_credentials,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            return bigquery.Client(project=settings.gcp_project_id, credentials=credentials)

    return bigquery.Client(project=settings.gcp_project_id)
