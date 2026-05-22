"""Thin wrapper over google.cloud.datacatalog_lineage_v1.

Handles region-scoped client construction and translates library types into
plain Python dicts so the rest of the codebase does not import the library directly.
"""

from __future__ import annotations

import structlog
from google.api_core import exceptions as gcp_exceptions
from google.cloud import datacatalog_lineage_v1

logger = structlog.get_logger(__name__)


def make_asset_fqn(project_id: str, dataset_id: str, asset: str) -> str:
    """Return the FQN format accepted by the Data Lineage API.

    Example: ``bigquery:my-project.my_dataset.my_table``
    """
    return f"bigquery:{project_id}.{dataset_id}.{asset}"


class LineageApiClient:
    """Region-scoped wrapper over the Data Lineage API.

    Args:
        project_id: GCP project to query lineage for.
        location: API region (e.g. ``"us"``). Must match the dataset region.
        credentials: Optional explicit credentials. When ``None``, uses ADC.
    """

    def __init__(
        self,
        project_id: str,
        location: str = "us",
        credentials: object | None = None,
    ) -> None:
        self._project_id = project_id
        self._location = location
        client_options = {"api_endpoint": f"{location}-datalineage.googleapis.com"}
        self._client = datacatalog_lineage_v1.LineageClient(
            credentials=credentials,  # type: ignore[arg-type]
            client_options=client_options,
        )
        self._parent = f"projects/{project_id}/locations/{location}"

    def search_links(self, asset_fqn: str, direction: str) -> list[datacatalog_lineage_v1.Link]:
        """Call SearchLinks for one asset in one direction.

        Args:
            asset_fqn: Fully-qualified name, e.g. ``bigquery:proj.ds.table``.
            direction: ``"UPSTREAM"`` or ``"DOWNSTREAM"``.

        Returns:
            List of Link objects. Empty list if none found or API unavailable.
        """
        if direction == "UPSTREAM":
            target = datacatalog_lineage_v1.EntityReference(fully_qualified_name=asset_fqn)
            request = datacatalog_lineage_v1.SearchLinksRequest(parent=self._parent, target=target)
        else:
            source = datacatalog_lineage_v1.EntityReference(fully_qualified_name=asset_fqn)
            request = datacatalog_lineage_v1.SearchLinksRequest(parent=self._parent, source=source)

        try:
            links = list(self._client.search_links(request=request))
            logger.debug(
                "lineage_api_search_links",
                asset_fqn=asset_fqn,
                direction=direction,
                count=len(links),
            )
            return links
        except gcp_exceptions.NotFound:
            logger.debug("lineage_api_not_found", asset_fqn=asset_fqn, direction=direction)
            return []
        except gcp_exceptions.PermissionDenied as exc:
            logger.warning(
                "lineage_api_permission_denied",
                asset_fqn=asset_fqn,
                direction=direction,
                error=str(exc),
            )
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "lineage_api_error",
                asset_fqn=asset_fqn,
                direction=direction,
                error=str(exc),
            )
            return []

    def batch_search_link_processes(
        self, links: list[datacatalog_lineage_v1.Link]
    ) -> list[datacatalog_lineage_v1.ProcessLinks]:
        """Fetch process details (including OpenLineage facets) for a list of links.

        Column-level lineage lives inside the ``links`` facets of each Process
        returned here. Returns empty list if no links provided or on error.
        """
        if not links:
            return []

        link_names = [lnk.name for lnk in links]
        request = datacatalog_lineage_v1.BatchSearchLinkProcessesRequest(
            parent=self._parent, links=link_names
        )
        try:
            result = list(self._client.batch_search_link_processes(request=request))
            logger.debug("lineage_api_batch_processes", count=len(result))
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("lineage_api_batch_error", error=str(exc))
            return []
