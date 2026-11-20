"""Territorial evaluation of activity chains for eqasim synthetic populations."""

from .chains import chains_from_hts, chains_from_activities, add_indicators, PURPOSE_CODES
from .weighted import weighted_share, weighted_mean, kish_effective_size, bootstrap_ci
from .compare import (
    distribution, hellinger, jensen_shannon, stratified_fidelity,
    contrast_matrix, contrast_retention, standardised_gap,
)
from .simulation import (
    read_table, attach_home, mode_shares, travel_per_resident, convergence,
    unfinished_agents, missing_trips,
)

__version__ = "0.1.0"

__all__ = [
    "chains_from_hts", "chains_from_activities", "add_indicators", "PURPOSE_CODES",
    "weighted_share", "weighted_mean", "kish_effective_size", "bootstrap_ci",
    "distribution", "hellinger", "jensen_shannon", "stratified_fidelity",
    "contrast_matrix", "contrast_retention", "standardised_gap",
    "read_table", "attach_home", "mode_shares", "travel_per_resident", "convergence",
    "unfinished_agents", "missing_trips",
]
