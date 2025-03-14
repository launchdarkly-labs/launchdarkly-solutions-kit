"""
LaunchDarkly API Client

This module provides a client for interacting with the LaunchDarkly API.
It handles authentication, caching, and provides methods for fetching
custom roles, teams, members, and projects.

Classes:
    LaunchDarklyAPI: Client for interacting with the LaunchDarkly API
"""

from .client import LaunchDarklyAPI

__all__ = ['LaunchDarklyAPI'] 