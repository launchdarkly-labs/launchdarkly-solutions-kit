#!/usr/bin/env python3
"""
TeamManager - LaunchDarkly Team Management Tool

A CLI tool for analyzing and managing LaunchDarkly teams and their role assignments.
Provides insights into team coverage, role distribution, and optimization opportunities.
"""

import argparse
import json
import logging
import os
import sys
from dotenv import load_dotenv

from .team_manager import TeamManager


def setup_logging(debug: bool = False, log_file: str = None):
    """Setup logging configuration"""
    log_level = logging.DEBUG if debug else logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure root logger
    logging.basicConfig(level=log_level, format=log_format)
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)


def load_api_key() -> str:
    """Load LaunchDarkly API key from environment or .env file"""
    load_dotenv()
    
    api_key = os.getenv('LAUNCHDARKLY_API_KEY')
    if not api_key:
        print("Error: LAUNCHDARKLY_API_KEY environment variable not set")
        print("Please set it in your .env file or environment variables")
        sys.exit(1)
    
    return api_key


def print_coverage_summary(coverage_report: dict):
    """Print a formatted summary of team coverage"""
    summary = coverage_report['summary']
    roles = coverage_report['roles']
    
    print("\n" + "="*60)
    print("TEAM COVERAGE SUMMARY")
    print("="*60)
    
    print(f"Teams:")
    print(f"  Total Teams:           {summary['total_teams']}")
    print(f"  Teams with Roles:      {summary['teams_with_roles']}")
    print(f"  Teams without Roles:   {summary['teams_without_roles']}")
    print(f"  Coverage:              {summary['team_coverage_percentage']}%")
    
    print(f"\nRoles:")
    print(f"  Total Roles:           {roles['total_roles']}")
    print(f"  Assigned Roles:        {roles['assigned_roles']}")
    print(f"  Unassigned Roles:      {roles['unassigned_roles']}")
    print(f"  Utilization:           {roles['role_utilization_percentage']}%")
    
    if coverage_report['teams_without_roles']:
        print(f"\nTeams without roles:")
        for team in coverage_report['teams_without_roles'][:5]:  # Show first 5
            print(f"  - {team['name']} (key: {team['key']}, {team['member_count']} members, {team['project_count']} projects)")
        if len(coverage_report['teams_without_roles']) > 5:
            print(f"  ... and {len(coverage_report['teams_without_roles']) - 5} more")
    if coverage_report['teams_with_roles']:
        print(f"\nTeams with roles:")
        for team in coverage_report['teams_with_roles'][:5]:  # Show first 5
            print(f"  - {team['name']} (key: {team['key']}, {team['member_count']} members, {team['project_count']} projects)")
        if len(coverage_report['teams_with_roles']) > 5:
            print(f"  ... and {len(coverage_report['teams_with_roles']) - 5} more")
    
    if coverage_report['unassigned_roles']:
        print(f"\nUnassigned roles:")
        for role in coverage_report['unassigned_roles'][:10]:  # Show first 10
            print(f"  - {role}")
        if len(coverage_report['unassigned_roles']) > 10:
            print(f"  ... and {len(coverage_report['unassigned_roles']) - 10} more")


def main():
    """Main entry point for the TeamManager CLI"""
    parser = argparse.ArgumentParser(
        description="TeamManager - LaunchDarkly Team Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  team-manager --report                    # Generate and display team coverage report
  team-manager --export                    # Export detailed team report to file
  team-manager --teams-without-roles       # List teams that have no roles assigned
  team-manager --teams-with-roles          # List teams that have custom roles assigned
  team-manager --role-distribution         # Show role distribution across teams
  team-manager --suggestions               # Get role assignment suggestions
  team-manager --analyze-template template.json  # Analyze template for roleAttribute patterns
  team-manager --generate-patches template.json  # Generate patches for all teams with roles
  team-manager --generate-patches role-key --remote-template  # Generate patches using remote template
  team-manager --generate-patches template.json --teams team-1 team-2  # Generate patches for specific teams
  team-manager --generate-patches role-key --remote-template --teams team-1 --template-cache-dir custom/templates  # Remote template with custom cache
  team-manager --apply-patches team-1 team-2  # Apply patches to specific teams
  team-manager --apply-patches team-1 --patch-dir custom/patches --comment "Custom update"  # Apply with custom options
  team-manager --no-cache                  # Force fresh data fetch from API
        """
    )
    
    # Main operations
    parser.add_argument('--report', '-r', action='store_true',
                        help='Generate and display team coverage report')
    parser.add_argument('--export', '-e', action='store_true',
                        help='Export comprehensive team report to JSON file')
    parser.add_argument('--teams-without-roles', '-twor', action='store_true',
                        help='List teams that have no custom roles assigned')
    parser.add_argument('--teams-with-roles', '-twr', action='store_true',
                        help='List teams that have custom roles assigned')
    parser.add_argument('--role-distribution', '-rd', action='store_true',
                        help='Show role distribution statistics')
    parser.add_argument('--suggestions', '-s', action='store_true',
                        help='Get suggestions for role assignments')
    
    # Patch generation operations
    parser.add_argument('--analyze-template', '-at', metavar='TEMPLATE_FILE',
                        help='Analyze a template role file for roleAttribute patterns')
    parser.add_argument('--generate-patches', '-gp', metavar='TEMPLATE_FILE_OR_ROLE_KEY',
                        help='Generate patch files for teams based on template and their roles')
    parser.add_argument('--remote-template', '-rt', action='store_true',
                        help='Fetch template remotely by role key instead of using local file')
    parser.add_argument('--template-cache-dir', default='output/template',
                        help='Directory to cache remote templates (default: output/template)')
    parser.add_argument('--apply-patches', '-ap', nargs='+', metavar='TEAM_KEY',
                        help='Apply patch files to specified teams')
    parser.add_argument('--teams', '-t', nargs='+', 
                        help='Specify teams to process (for patch generation)')
    parser.add_argument('--patch-dir', default='output/patches',
                        help='Directory containing patch files (default: output/patches)')
    parser.add_argument('--comment', default='Applied patch via TeamManager',
                        help='Comment for the patch operation')
    
    # Options
    parser.add_argument('--no-cache', action='store_true',
                        help='Force fresh data fetch from API (ignore cache)')
    parser.add_argument('--output-dir', default='output/reports',
                        help='Directory for output files (default: output/reports)')
    parser.add_argument('--patch-output-dir', default='output/patches',
                        help='Directory for patch files (default: output/patches)')
    parser.add_argument('--output-file',
                        help='Custom filename for exported report')
    
    # Logging options
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--log-file',
                        help='Write logs to specified file in addition to console')
    
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.remote_template and not args.generate_patches:
        print("Error: --remote-template can only be used with --generate-patches")
        sys.exit(1)
    
    # If no specific action is provided, default to report
    if not any([args.report, args.export, args.teams_without_roles, args.teams_with_roles,
                args.role_distribution, args.suggestions, args.analyze_template, args.generate_patches,
                args.apply_patches]):
        args.report = True
    
    # Setup logging
    setup_logging(args.debug, args.log_file)
    logger = logging.getLogger(__name__)
    
    try:
        # Load API key
        api_key = load_api_key()
        logger.info("LD API key loaded successfully")
        
        # Initialize TeamManager
        team_manager = TeamManager(api_key)
        
        # Handle template analysis (doesn't need team data)
        if args.analyze_template:
            print("\n" + "="*60)
            print("TEMPLATE ANALYSIS")
            print("="*60)
            
            try:
                analysis = team_manager.analyze_template(args.analyze_template)
                
                print(f"Template File: {analysis['template_file']}")
                print(f"Role Key: {analysis['role_key']}")
                print(f"Role Name: {analysis['role_name']}")
                if analysis['description']:
                    print(f"Description: {analysis['description']}")
                print()
                
                print(f"Policy Statistics:")
                print(f"  Total Policy Statements: {analysis['total_policy_statements']}")
                print(f"  Total Resources: {analysis['total_resources']}")
                print(f"  Resources with roleAttribute: {len(analysis['roleAttribute_resources'])}")
                print()
                
                if analysis['unique_attributes']:
                    print(f"Unique roleAttribute types found:")
                    for attr in analysis['unique_attributes']:
                        pattern_count = len(analysis['attribute_patterns'].get(attr, []))
                        print(f"  • {attr} ({pattern_count} pattern(s))")
                    print()
                
                if analysis['roleAttribute_resources']:
                    print(f"Resources containing roleAttribute:")
                    for i, item in enumerate(analysis['roleAttribute_resources'][:10], 1):  # Show first 10
                        print(f"  {i}. {item['resource']}")
                        print(f"     Actions: {', '.join(item['actions'][:3])}{'...' if len(item['actions']) > 3 else ''}")
                        print(f"     Effect: {item['effect']}")
                        print()
                    if len(analysis['roleAttribute_resources']) > 10:
                        print(f"  ... and {len(analysis['roleAttribute_resources']) - 10} more")
                else:
                    print("No roleAttribute patterns found in template.")
                    
            except (FileNotFoundError, ValueError) as e:
                print(f"Error: {e}")
                sys.exit(1)
        
        # Handle patch generation
        if args.generate_patches:
            print("\n" + "="*60)
            print("PATCH GENERATION")
            print("="*60)
            
            try:
                results = team_manager.generate_team_patches(
                    template_file=args.generate_patches,
                    team_keys=args.teams,
                    output_dir=args.patch_output_dir,
                    is_remote_template=args.remote_template,
                    template_cache_dir=args.template_cache_dir
                )
                
                template_analysis = results['template_analysis']
                print(f"Template: {template_analysis['template_file']}")
                print(f"Template Role: {template_analysis['role_key']}")
                print(f"Unique Attributes: {', '.join(template_analysis['unique_attributes'])}")
                if results['remote_template_used']:
                    print(f"Remote Template: Yes (cached to {results['template_cache_directory']})")
                else:
                    print(f"Remote Template: No (local file)")
                print()
                
                print(f"Patch Generation Results:")
                print(f"  Teams Processed: {results['teams_processed']}")
                print(f"  Patches Generated: {results['patches_generated']}")
                print(f"  Failed Teams: {len(results['failed_teams'])}")
                print(f"  Output Directory: {results['output_directory']}")
                print()
                
                if results['generated_patches']:
                    print(f"Generated Patches:")
                    for patch in results['generated_patches']:
                        print(f"  • {patch['team_key']}: {patch['patch_file']}")
                        print(f"    Roles: {', '.join(patch['roles_analyzed'])}")
                        print(f"    Attributes: {', '.join(patch['attribute_types'])}")
                        # Check for missing attributes for this team
                        missing_attrs = []
                        for attr in template_analysis['unique_attributes']:
                            if attr not in patch['attribute_types']:
                                missing_attrs.append(attr)
                        for attr, values in patch['extracted_values'].items():
                            print(f"      {attr}: {values}")
                        if missing_attrs:
                            print(f"    ⚠️ Missing attributes for [{patch['team_key']}]: {', '.join(missing_attrs)}")
                        print()
                
                if results['failed_teams']:
                    print(f"Failed Teams:")
                    for team in results['failed_teams']:
                        print(f"  • {team}")
                    print()
                        
            except (FileNotFoundError, ValueError) as e:
                print(f"Error: {e}")
                sys.exit(1)
        
        # Handle patch application
        if args.apply_patches:
            print("\n" + "="*60)
            print("APPLY PATCHES")
            print("="*60)
            
            try:
                results = team_manager.apply_patches(
                    team_keys=args.apply_patches,
                    patch_dir=args.patch_dir,
                    comment=args.comment
                )
                
                print(f"Patch Application Results:")
                print(f"  Teams Requested: {len(results['teams_requested'])}")
                print(f"  Patch Files Found: {results['patches_found']}")
                print(f"  Patches Applied: {len(results['patches_applied'])}")
                print(f"  Failed Applications: {len(results['failed_patches'])}")
                print(f"  Skipped Teams: {len(results['skipped_teams'])}")
                print()
                
                # Show patch file selection details
                if results.get('patch_file_details'):
                    print(f"Patch File Selection Details:")
                    for team_key, details in results['patch_file_details'].items():
                        if details['total_files_found'] > 1:
                            print(f"  • {team_key}: {details['total_files_found']} files found, selected '{details['selected_file']}'")
                            print(f"    Available: {', '.join(details['all_files'])}")
                        else:
                            print(f"  • {team_key}: Using '{details['selected_file']}'")
                    print()
                
                if results['patches_applied']:
                    print(f"Successfully Applied Patches:")
                    for patch in results['patches_applied']:
                        print(f"  • {patch['team_key']}: {patch['patch_filename']}")
                        print(f"    Instructions Applied: {patch['instructions_applied']}")
                        print(f"    Instructions Details: {patch['instructions_details']}")
                        print()
                
                if results['failed_patches']:
                    print(f"Failed Patch Applications:")
                    for failure in results['failed_patches']:
                        print(f"  • {failure['team_key']}: {failure['error']}")
                        print(f"    Patch File: {failure.get('patch_filename', failure['patch_file'])}")
                        print()
                
                if results['skipped_teams']:
                    print(f"Skipped Teams (no patch files found):")
                    for team in results['skipped_teams']:
                        print(f"  • {team}")
                    print()
                        
            except (FileNotFoundError, ValueError) as e:
                print(f"Error: {e}")
                sys.exit(1)
        
        # Load data for other operations (skip if only doing template analysis or patch application)
        if not ((args.analyze_template or args.apply_patches) and not any([args.report, args.export, args.teams_without_roles, 
                                                  args.teams_with_roles, args.role_distribution, 
                                                  args.suggestions, args.generate_patches])):
            use_cache = not args.no_cache
            data = team_manager.load_team_data(use_cache=use_cache)
            
            if not data:
                logger.error("Failed to load team data")
                sys.exit(1)
        
            # Execute requested operations
            if args.teams_without_roles:
                print("\n" + "="*60)
                print("TEAMS WITHOUT ROLES")
                print("="*60)
                teams = team_manager.get_teams_without_roles(data)
                if teams:
                    for team in teams:
                        print(f"Team: {team['name']} (key: {team['key']})")
                        print(f"  Members: {team['member_count']}")
                        print(f"  Projects: {team['project_count']}")
                        print()
                else:
                    print("All teams have at least one role assigned!")

            if args.teams_with_roles:
                print("\n" + "="*60)
                print("TEAMS WITH ROLES")
                print("="*60)
                teams = team_manager.get_teams_with_roles(data)
                if teams:
                    for team in teams:
                        print(f"Team: {team['name']} (key: {team['key']})")
                        print(f"  Roles: {team['roles']}")
                        print(f"  Role Attributes: {team['roleAttributes']}")
                        print(f"  Members: {team['member_count']}")
                        print(f"  Projects: {team['project_count']}")
                        
                        print()
                else:
                    print("No teams found with roles!") 

            if args.role_distribution:
                print("\n" + "="*60)
                print("ROLE DISTRIBUTION")
                print("="*60)
                distribution = team_manager.get_role_distribution(data)
                for role_key, stats in distribution.items():
                    print(f"Role: {role_key}")
                    print(f"  Teams: {stats['total_teams']}")
                    print(f"  Members: {stats['total_members']}")
                    print(f"  Assigned: {'Yes' if stats['is_assigned'] else 'No'}")
                    print()
            
            if args.suggestions:
                print("\n" + "="*60)
                print("ROLE ASSIGNMENT SUGGESTIONS")
                print("="*60)
                suggestions = team_manager.suggest_role_assignments(data)
                
                if suggestions['teams_needing_roles']:
                    print(f"Teams with project access but no roles ({len(suggestions['teams_needing_roles'])}):")
                    for team in suggestions['teams_needing_roles']:
                        print(f"  - {team['name']} ({team['project_count']} projects, {team['member_count']} members)")
                    print()
                
                if suggestions['underutilized_roles']:
                    print(f"Unassigned roles ({len(suggestions['underutilized_roles'])}):")
                    for role in suggestions['underutilized_roles']:
                        print(f"  - {role}")
                    print()
                
                if suggestions['recommendations']:
                    print("Recommendations:")
                    for rec in suggestions['recommendations']:
                        print(f"  • {rec['message']}")
                    print()
            
            if args.report:
                coverage_report = team_manager.get_team_coverage_report(data)
                print_coverage_summary(coverage_report)
            
            if args.export:
                logger.info("=== Exporting team report ===")
                filepath = team_manager.export_team_report(
                    output_dir=args.output_dir,
                    filename=args.output_file
                )
                print(f"\nTeam report exported to: {filepath}")
        
        print("\n" + "="*60)
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.debug:
            raise
        sys.exit(1)


if __name__ == '__main__':
    main() 