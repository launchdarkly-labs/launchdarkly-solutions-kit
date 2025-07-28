"""
TeamManager - LaunchDarkly Team Management Tool

A CLI tool for analyzing and managing LaunchDarkly teams and their role assignments.
Provides insights into team coverage, role distribution, optimization opportunities, 
template analysis, and patch generation capabilities.
"""

from .team_manager import TeamManager, RoleAttributeExtractor

__version__ = "1.0.0"
__author__ = "LaunchDarkly-Labs"
__description__ = "LaunchDarkly Team Management Tool"

__all__ = [
    'TeamManager', 
    'RoleAttributeExtractor',
    '__version__',
    '__author__',
    '__description__'
] 