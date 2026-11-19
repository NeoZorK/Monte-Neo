"""Honest strategy search: a fixed split, a ledger of every variant, pre-registered batches and one sealed holdout."""

from monte_neo.research.breadth import breadth_report, breadth_row, cross_sectional_ic, effective_breadth
from monte_neo.research.candidate import Candidate
from monte_neo.research.family import family_rows, family_stats, search_cost
from monte_neo.research.funnel import funnel, funnel_text
from monte_neo.research.project import ResearchProject
from monte_neo.research.splits import Splits

__all__ = ["Candidate", "ResearchProject", "Splits", "breadth_report", "breadth_row", "cross_sectional_ic", "effective_breadth", "family_rows",
           "family_stats", "funnel", "funnel_text", "search_cost"]
