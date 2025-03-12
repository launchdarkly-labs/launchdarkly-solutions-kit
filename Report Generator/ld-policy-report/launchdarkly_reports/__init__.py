"""
LaunchDarkly Reports

This module provides report generation capabilities for LaunchDarkly policy analysis.
It creates interactive HTML reports that visualize policy similarities, role assignments,
and team access patterns.

The module includes CSS and JavaScript files for styling and interactivity,
which are automatically copied to the output directory when generating a report.

Classes:
    SimilarityReport: Generates HTML reports comparing LaunchDarkly custom role policies
"""

from .similarity_report import SimilarityReport

__all__ = ['SimilarityReport'] 