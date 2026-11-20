"""Strategy catalog labelling (``catalog-rules/1``, provisional): category, tags, type mask and readable type tag.

The label is derived by deterministic rules from the specification and the measured positions, never written by hand.
"""

from monte_neo.catalog.classify import SCHEMA_ID, classify, spec_hash
from monte_neo.catalog.mask import categories, decode, encode, readable_tag, similarity
from monte_neo.catalog.measure import measure

__all__ = ["SCHEMA_ID", "categories", "classify", "decode", "encode", "measure", "readable_tag", "similarity", "spec_hash"]
