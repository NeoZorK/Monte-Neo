"""Validation dossier: a certificate turned into the folder a model-risk committee reads (``validation-dossier/1``)."""

from __future__ import annotations

from monte_neo.dossier.build import DOSSIER_SCHEMA_ID, build_dossier, write_dossier
from monte_neo.dossier.frameworks import FRAMEWORKS, framework_map

__all__ = ["DOSSIER_SCHEMA_ID", "FRAMEWORKS", "build_dossier", "framework_map", "write_dossier"]
