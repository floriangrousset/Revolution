"""Voting and consensus logic."""
from .consensus import calculate_party_result, determine_final_result, VotingResult

__all__ = [
    "calculate_party_result",
    "determine_final_result",
    "VotingResult",
]
