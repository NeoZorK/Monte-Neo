"""Strategy-type profiles: which checks matter for which kind of strategy.

One machine-readable file (``profiles_v1.json``) is the source of truth; the documentation page is generated from it.
A profile never raises a verdict: it reports which required checks ran, which did not and what is not assessed.
"""

from monte_neo.profiles.apply import profile_block
from monte_neo.profiles.registry import PROFILE_IDS, get_profile, load_profiles
from monte_neo.profiles.suggest import suggest_profiles

__all__ = ["PROFILE_IDS", "get_profile", "load_profiles", "profile_block", "suggest_profiles"]
