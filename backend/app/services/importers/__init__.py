"""L3.7 — Importer registry.

Future entity importers (COI, loss-run, producer-license) plug in here
by adding a single dict entry. The orchestrator never imports concrete
importers — it asks the registry.
"""

from __future__ import annotations

from app.models.import_job import ImportEntityType
from app.services.importers.base import BaseImporter
from app.services.importers.supplier_importer import SupplierImporter

__all__ = ["IMPORTERS", "get_importer", "register_importer"]


IMPORTERS: dict[ImportEntityType, type[BaseImporter]] = {
    ImportEntityType.SUPPLIER: SupplierImporter,
    # Plug-points for future drops — concrete implementations will land
    # alongside their model owners. See ``docs/IMPORTS.md`` §"Adding a
    # new importer".
    # ImportEntityType.COI: CoiImporter,
    # ImportEntityType.LOSS_RUN: LossRunImporter,
    # ImportEntityType.PRODUCER_LICENSE: ProducerLicenseImporter,
}


def get_importer(entity_type: ImportEntityType) -> BaseImporter:
    cls = IMPORTERS.get(entity_type)
    if cls is None:
        raise ValueError(f"No importer registered for {entity_type.value!r}")
    return cls()


def register_importer(
    entity_type: ImportEntityType, importer_cls: type[BaseImporter]
) -> None:
    """Add (or replace) an importer at runtime — used by tests."""

    IMPORTERS[entity_type] = importer_cls
