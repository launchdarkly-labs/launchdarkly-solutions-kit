"""
LaunchDarkly Policy Similarity Analysis

This module provides services for analyzing similarities between LaunchDarkly
custom role policies. It converts policies to human-readable text and uses
semantic embeddings to find similar policies.

The module uses ChromaDB for storing and querying embeddings, with options
for persistent storage and force refresh of the collection.

Classes:
    LaunchDarklyPolicySimilarityService: Service for analyzing policy similarities
    
Functions:
    validate_policies: Validates custom role policies against official LaunchDarkly resource actions
"""

from .service import LaunchDarklyPolicySimilarityService
from .policy_validator import validate_policies, get_invalid_actions, load_resource_actions

__all__ = ['LaunchDarklyPolicySimilarityService', 'validate_policies', 'get_invalid_actions', 'load_resource_actions'] 