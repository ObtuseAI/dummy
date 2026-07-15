"""DUMMY vNext resource accounting and marginal information economics."""

from .allocation import allocation_recommendation
from .cost_model import estimate_costs
from .information_gain import estimate_information_gain_proxy
from .ledger import account_messages
from .marginal_utility import calculate_marginal_utility
from .models import (
    CostEstimate,
    InformationGainEstimate,
    MarginalUtility,
    MetabolismValidationError,
    ResourceBudget,
    ResourceUsage,
    UtilityStatus,
)
from .starvation import starvation_state

__all__ = [
    "CostEstimate",
    "InformationGainEstimate",
    "MarginalUtility",
    "MetabolismValidationError",
    "ResourceBudget",
    "ResourceUsage",
    "UtilityStatus",
    "account_messages",
    "allocation_recommendation",
    "calculate_marginal_utility",
    "estimate_costs",
    "estimate_information_gain_proxy",
    "starvation_state",
]
