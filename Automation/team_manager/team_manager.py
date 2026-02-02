import os
import json
import logging
import re
from typing import Dict, List, Optional, Set
from datetime import datetime

from api_client.client import LaunchDarklyAPI


class RoleAttributeExtractor:
    """Extracts roleAttribute values from role policies"""
    
    @staticmethod
    def discover_attribute_patterns(template_data: Dict) -> Dict[str, List[str]]:
        """Discover roleAttribute patterns from template and create extraction regex patterns"""
        
        attribute_patterns = {}
        policy = template_data.get('policy', [])
        
        for policy_statement in policy:
            resources = policy_statement.get('resources', [])
            
            for resource in resources:
                # Find all roleAttribute placeholders in this resource
                roleattr_matches = re.findall(r'\$\{roleAttribute/([^}]+)\}', resource)
                
                if not roleattr_matches:
                    continue 
                
                for attr_key in roleattr_matches:
                    # Create a regex that matches this resource but captures the specific attribute
                    pattern = resource
                    
                    # Replace the target attribute with a unique placeholder
                    target_placeholder = f'${{roleAttribute/{attr_key}}}'
                    pattern = pattern.replace(target_placeholder, '__CAPTURE_TARGET__')
                    
                    # Replace other roleAttribute placeholders with a regex pattern
                    pattern = re.sub(r'\$\{roleAttribute/[^}]+\}', '__OTHER_ATTR__', pattern)
                    
                    # Replace wildcards
                    pattern = pattern.replace('*', '__WILDCARD__')
                    
                    # Escape special regex characters carefully
                    # Only escape the literal parts, not our placeholders
                    escaped_chars = ['.', '^', '$', '+', '?', '|', '\\', '(', ')', '[', ']', '{', '}']
                    for char in escaped_chars:
                        pattern = pattern.replace(char, f'\\{char}')
                    
                    # Now replace placeholders with regex patterns
                    pattern = pattern.replace('__CAPTURE_TARGET__', '([^:]+)')
                    pattern = pattern.replace('__OTHER_ATTR__', '[^:]+')
                    pattern = pattern.replace('__WILDCARD__', '.*')
                    
                    # Store the pattern - allow multiple patterns per attribute
                    final_pattern = f'^{pattern}$'
                    if attr_key not in attribute_patterns:
                        attribute_patterns[attr_key] = []
                    
                    # Only add if this exact pattern doesn't already exist
                    if final_pattern not in attribute_patterns[attr_key]:
                        attribute_patterns[attr_key].append(final_pattern)
        
        return attribute_patterns

    @staticmethod
    def extract_from_role_with_patterns(role_data: Dict, attribute_patterns: Dict[str, List[str]]) -> Dict[str, Set[str]]:
        """Extract actual values from role resources using discovered patterns
        
        Checks both 'resources' and 'notResources' fields in policy statements.
        """
        
        attribute_values = {}
        policy = role_data.get('policy', [])
        
        # Initialize sets for all discovered attributes
        for attr_key in attribute_patterns:
            attribute_values[attr_key] = set()
        
        for policy_statement in policy:
            # Check both 'resources' and 'notResources' fields
            resources = policy_statement.get('resources', [])
            not_resources = policy_statement.get('notResources', [])
            all_resources = resources + not_resources
            
            if not all_resources:
                continue

            for resource in all_resources:
                for attr_key, patterns in attribute_patterns.items():
                    # Use a generator expression to find the first match quickly
                    for pattern in patterns:
                        try:
                            match = re.match(pattern, resource)
                        except re.error:
                            continue  # Skip invalid regex patterns
                        if match:
                            try:
                                value = match.group(1)
                            except IndexError:
                                continue  # Skip if group(1) doesn't exist
                            # Skip placeholder values and wildcards
                            if value and value != '*' and '${' not in value:
                                attribute_values[attr_key].add(value)
                            # Once matched, no need to check other patterns for this attr/resource
                            break
        # Remove empty sets
        return {k: v for k, v in attribute_values.items() if v}


class TeamManager:
    """
    TeamManager manages LaunchDarkly teams and their role assignments.
    
    This class provides high-level operations for:
    - Analyzing team role assignments
    - Managing team permissions
    - Generating team reports
    - Optimizing role distribution across teams
    
    Attributes:
        api_client (LaunchDarklyAPI): LaunchDarkly API client instance
        logger: Logger instance for this class
    """
    
    def __init__(self, api_key: str, cache_dir: str = "cache", cache_ttl: int = 24):
        """
        Initialize TeamManager with LaunchDarkly API access
        
        Args:
            api_key (str): LaunchDarkly API key
            cache_dir (str): Directory for caching API responses
            cache_ttl (int): Cache time-to-live in hours
        """
        self.api_client = LaunchDarklyAPI(api_key, cache_dir, cache_ttl=cache_ttl)
        self.logger = logging.getLogger(__name__)
        
    def load_team_data(self, use_cache: bool = True) -> Dict:
        """
        Load team data from cache or fetch from API
        
        Args:
            use_cache (bool): Whether to use cached data if available
            
        Returns:
            Dict: Enriched team and role data
        """
        if use_cache:
            cached_data = self.api_client.load_cached_data()
            if cached_data:
                self.logger.info("Using cached team data")
                return cached_data
        
        self.logger.info("Fetching fresh team data from LaunchDarkly")
        return self.api_client.fetch_and_cache_data()
    def get_teams_with_roles(self, data: Optional[Dict] = None) -> List[Dict]:
        """
        Find teams that have custom roles assigned
        """
        if data is None:
            data = self.load_team_data()
        
        teams_with_roles = []
        for team in data.get('teams', []):
            if team.get('roles', []):
                
                teams_with_roles.append({
                    'key': team['key'],
                    'name': team.get('name', team['key']),
                    'roles': team.get('roles', []),
                    'roleAttributes': team.get('roleAttributes', []),
                    'member_count': team.get('members', {}).get('totalCount',0),
                    'project_count': team.get('projects', {}).get('totalCount', 0)
                })
        
        return teams_with_roles
    
    def get_teams_without_roles(self, data: Optional[Dict] = None) -> List[Dict]:
        """
        Find teams that have no custom roles assigned
        
        Args:
            data (Dict, optional): Team data, will fetch if not provided
            
        Returns:
            List[Dict]: Teams without any custom role assignments
        """
        if data is None:
            data = self.load_team_data()
        
        teams_without_roles = []
        for team in data.get('teams', []):
            if not team.get('roles', []):
                teams_without_roles.append({
                    'key': team['key'],
                    'name': team.get('name', team['key']),
                    'member_count': team.get('members', {}).get('totalCount',0),
                    'project_count': team.get('projects', {}).get('totalCount', 0)
                })
        
        return teams_without_roles
    
    def get_role_distribution(self, data: Optional[Dict] = None) -> Dict:
        """
        Analyze how roles are distributed across teams
        
        Args:
            data (Dict, optional): Team data, will fetch if not provided
            
        Returns:
            Dict: Role distribution statistics
        """
        if data is None:
            data = self.load_team_data()
        
        role_stats = {}
        
        for role in data.get('roles', []):
            role_key = role['key']
            role_stats[role_key] = {
                'total_teams': role.get('total_teams', 0),
                'total_members': role.get('total_members', 0),
                'teams': role.get('teams', []),
                'members': role.get('members', []),
                'is_assigned': role.get('is_assigned', False)
            }
        
        return role_stats
    
    def get_team_coverage_report(self, data: Optional[Dict] = None) -> Dict:
        """
        Generate a comprehensive team coverage report
        
        Args:
            data (Dict, optional): Team data, will fetch if not provided
            
        Returns:
            Dict: Team coverage analysis
        """
        if data is None:
            data = self.load_team_data()
        
        total_teams = data.get('total_teams', 0)
        teams_with_roles = data.get('total_assigned_teams', 0)
        teams_without_roles = total_teams - teams_with_roles
        
        total_roles = data.get('total_roles', 0)
        assigned_roles = data.get('total_assigned_roles', 0)
        unassigned_roles = data.get('total_unassigned_roles', 0)
        
        coverage_report = {
            'summary': {
                'total_teams': total_teams,
                'teams_with_roles': teams_with_roles,
                'teams_without_roles': teams_without_roles,
                'team_coverage_percentage': round((teams_with_roles / total_teams * 100) if total_teams > 0 else 0, 2)
            },
            'roles': {
                'total_roles': total_roles,
                'assigned_roles': assigned_roles,
                'unassigned_roles': unassigned_roles,
                'role_utilization_percentage': round((assigned_roles / total_roles * 100) if total_roles > 0 else 0, 2)
            },
            'teams_without_roles': self.get_teams_without_roles(data),
            'teams_with_roles': self.get_teams_with_roles(data),
            'unassigned_roles': data.get('unassigned_roles', []),
            'generated_at': datetime.now().isoformat()
        }
        
        return coverage_report
    
    def suggest_role_assignments(self, data: Optional[Dict] = None) -> Dict:
        """
        Suggest potential role assignments based on team project access
        
        Args:
            data (Dict, optional): Team data, will fetch if not provided
            
        Returns:
            Dict: Suggested role assignments
        """
        if data is None:
            data = self.load_team_data()
        
        suggestions = {
            'teams_needing_roles': [],
            'underutilized_roles': [],
            'recommendations': []
        }
        
        # Find teams without roles that have project access
        teams_without_roles = self.get_teams_without_roles(data)
        for team in teams_without_roles:
            if team['project_count'] > 0:
                suggestions['teams_needing_roles'].append(team)
        
        # Find roles that are not assigned to any teams
        unassigned_roles = data.get('unassigned_roles', [])
        suggestions['underutilized_roles'] = unassigned_roles
        
        # Generate basic recommendations
        if suggestions['teams_needing_roles'] and suggestions['underutilized_roles']:
            suggestions['recommendations'].append({
                'type': 'assignment_opportunity',
                'message': f"Consider assigning roles from {len(unassigned_roles)} unassigned roles to {len(suggestions['teams_needing_roles'])} teams that have project access but no roles"
            })
        
        return suggestions
    
    def export_team_report(self, output_dir: str = "output/reports", filename: str = None) -> str:
        """
        Export a comprehensive team report to JSON file
        
        Args:
            output_dir (str): Directory to save the report
            filename (str): Custom filename, defaults to team_coverage_report.json
            
        Returns:
            str: Path to the exported report file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"team_coverage_report_{timestamp}.json"
        
        filepath = os.path.join(output_dir, filename)
        
        report_data = {
            'coverage_report': self.get_team_coverage_report(),
            'role_distribution': self.get_role_distribution(),
            'suggestions': self.suggest_role_assignments()
        }
        
        with open(filepath, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        self.logger.info(f"Team report exported to: {filepath}")
        return filepath

    def analyze_template(self, template_file: str) -> Dict:
        """
        Analyze a template role file for roleAttribute patterns
        
        Args:
            template_file (str): Path to the template role file
            
        Returns:
            Dict: Analysis results including discovered patterns and roleAttribute resources
        """
        try:
            with open(template_file, 'r') as f:
                template_data = json.load(f)
            
            # Discover attribute patterns
            attribute_patterns = RoleAttributeExtractor.discover_attribute_patterns(template_data)
            
            # Get roleAttribute resources
            role_attribute_resources = []
            policy = template_data.get('policy', [])
            
            for i, policy_statement in enumerate(policy):
                resources = policy_statement.get('resources', [])
                actions = policy_statement.get('actions', [])
                effect = policy_statement.get('effect', 'unknown')
                
                for resource in resources:
                    if 'roleAttribute' in resource:
                        role_attribute_resources.append({
                            'policy_index': i,
                            'resource': resource,
                            'actions': actions,
                            'effect': effect
                        })
            
            # Extract unique roleAttribute types
            role_attributes = set()
            for item in role_attribute_resources:
                resource = item['resource']
                matches = re.findall(r'\$\{roleAttribute/([^}]+)\}', resource)
                role_attributes.update(matches)
            
            return {
                'template_file': template_file,
                'role_key': template_data.get('key', 'unknown'),
                'role_name': template_data.get('name', 'unknown'),
                'description': template_data.get('description', ''),
                'total_policy_statements': len(policy),
                'total_resources': sum(len(stmt.get('resources', [])) for stmt in policy),
                'roleAttribute_resources': role_attribute_resources,
                'unique_attributes': sorted(list(role_attributes)),
                'attribute_patterns': attribute_patterns
            }
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Template file not found: {template_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in template file: {e}")

    def generate_team_patches_multi_template(self, template_files: List[str], team_keys: Optional[List[str]] = None, 
                                            output_dir: str = "output/patches", is_remote_template: bool = False,
                                            template_cache_dir: str = "output/template", use_cache: bool = True) -> Dict:
        """
        Generate consolidated patch files for teams based on multiple templates and their assigned roles
        
        Args:
            template_files (List[str]): List of template file paths or role keys (if is_remote_template=True)
            team_keys (List[str], optional): Specific teams to process, defaults to all teams with roles
            output_dir (str): Directory to save patch files
            is_remote_template (bool): Whether to fetch templates remotely by role key
            template_cache_dir (str): Directory to save remote templates
            use_cache (bool): Whether to use cached team data (default: True)
            
        Returns:
            Dict: Results of patch generation including generated files and statistics
        """
        if not template_files:
            raise ValueError("At least one template file must be provided")
        
        # Handle remote template fetching for all templates
        processed_template_files = []
        for template_file in template_files:
            if is_remote_template:
                processed_file = self._fetch_and_save_remote_template(template_file, template_cache_dir)
                processed_template_files.append(processed_file)
            else:
                processed_template_files.append(template_file)
        
        # Analyze all templates
        all_template_analyses = []
        all_attribute_patterns = {}
        all_template_role_keys = []
        
        for template_file in processed_template_files:
            template_analysis = self.analyze_template(template_file)
            all_template_analyses.append(template_analysis)
            all_template_role_keys.append(template_analysis['role_key'])
            
            # Merge attribute patterns from all templates
            template_patterns = template_analysis['attribute_patterns']
            for attr_key, patterns in template_patterns.items():
                if attr_key not in all_attribute_patterns:
                    all_attribute_patterns[attr_key] = []
                # Add patterns that don't already exist
                for pattern in patterns:
                    if pattern not in all_attribute_patterns[attr_key]:
                        all_attribute_patterns[attr_key].append(pattern)
        
        if not all_attribute_patterns:
            raise ValueError("No roleAttribute patterns found in any template files")
        
        # Load team data (refresh cache first if use_cache=False)
        data = self.load_team_data(use_cache=use_cache)
        
        # Determine teams to process
        if team_keys is None:
            teams_with_roles = self.get_teams_with_roles(data)
            team_keys = [team['key'] for team in teams_with_roles]
        
        # Get all custom roles for lookup
        all_roles = data.get('roles', [])
        roles_lookup = {role['key']: role for role in all_roles}
        
        generated_patches = []
        failed_teams = []  # Track failed teams with reasons
        skipped_teams = []  # Track skipped teams with reasons
        
        for team_key in team_keys:
            try:
                # Find team and its roles
                team_data = None
                for team in data.get('teams', []):
                    if team['key'] == team_key:
                        team_data = team
                        break
                
                if not team_data:
                    self.logger.warning(f"Team '{team_key}' not found")
                    failed_teams.append({
                        'team_key': team_key,
                        'reason': 'team_not_found',
                        'message': 'Team not found in LaunchDarkly (check team key spelling or refresh cache with --no-cache)'
                    })
                    continue
                
                team_roles = team_data.get('roles', [])
                if not team_roles:
                    self.logger.warning(f"Team '{team_key}' has no assigned roles")
                    skipped_teams.append({
                        'team_key': team_key,
                        'reason': 'no_assigned_roles',
                        'message': 'Team has no assigned roles to extract roleAttribute values from'
                    })
                    continue
                
                # Get full role data
                team_role_objects = []
                for role_key in team_roles:
                    if role_key in roles_lookup:
                        team_role_objects.append(roles_lookup[role_key])
                
                if not team_role_objects:
                    self.logger.warning(f"No role objects found for team '{team_key}'")
                    skipped_teams.append({
                        'team_key': team_key,
                        'reason': 'no_role_objects',
                        'message': 'Role data not found in cache for assigned roles'
                    })
                    continue
                
                # Extract roleAttribute values from team's roles using all patterns
                team_attribute_values = {}
                
                # Initialize attribute value sets for all discovered attributes
                for attr_key in all_attribute_patterns:
                    team_attribute_values[attr_key] = set()
                
                # Extract values from each role assigned to this team
                for role in team_role_objects:
                    role_values = RoleAttributeExtractor.extract_from_role_with_patterns(role, all_attribute_patterns)
                    
                    # Merge with team collection
                    for attr_type, values in role_values.items():
                        if attr_type not in team_attribute_values:
                            team_attribute_values[attr_type] = set()
                        team_attribute_values[attr_type].update(values)
                
                # Remove empty sets
                team_attribute_values = {k: v for k, v in team_attribute_values.items() if v}
                
                if not team_attribute_values:
                    self.logger.info(f"No roleAttribute values found for team '{team_key}', generating patch with template roles only")
                
                # Get team's existing roleAttributes
                existing_role_attributes = team_data.get('roleAttributes', {})
                
                # Create consolidated patch file with all templates
                patch_filepath = self._create_team_patch_file(
                    processed_template_files, all_template_role_keys, team_key, 
                    team_role_objects, team_attribute_values, output_dir,
                    existing_role_attributes=existing_role_attributes
                )
                
                generated_patches.append({
                    'team_key': team_key,
                    'patch_file': patch_filepath,
                    'roles_analyzed': [role.get('key', 'unknown') for role in team_role_objects],
                    'attribute_types': list(team_attribute_values.keys()),
                    'extracted_values': {k: sorted(list(v)) for k, v in team_attribute_values.items()},
                    'templates_used': all_template_role_keys
                })
                
            except Exception as e:
                self.logger.error(f"Failed to process team '{team_key}': {e}")
                failed_teams.append({
                    'team_key': team_key,
                    'reason': 'exception',
                    'message': str(e)
                })
        
        return {
            'template_analyses': all_template_analyses,
            'templates_processed': len(template_files),
            'teams_processed': len(team_keys),
            'patches_generated': len(generated_patches),
            'failed_teams': failed_teams,
            'skipped_teams': skipped_teams,
            'generated_patches': generated_patches,
            'output_directory': output_dir,
            'remote_template_used': is_remote_template,
            'template_files_used': processed_template_files,
            'template_cache_directory': template_cache_dir if is_remote_template else None,
            'combined_attribute_patterns': all_attribute_patterns
        }

    def generate_team_patches(self, template_file: str, team_keys: Optional[List[str]] = None, 
                             output_dir: str = "output/patches", is_remote_template: bool = False,
                             template_cache_dir: str = "output/template", use_cache: bool = True) -> Dict:
        """
        Generate patch files for teams based on a template and their assigned roles
        
        Args:
            template_file (str): Path to the template role file or role key (if is_remote_template=True)
            team_keys (List[str], optional): Specific teams to process, defaults to all teams with roles
            output_dir (str): Directory to save patch files
            is_remote_template (bool): Whether to fetch template remotely by role key
            template_cache_dir (str): Directory to save remote templates
            use_cache (bool): Whether to use cached team data (default: True)
            
        Returns:
            Dict: Results of patch generation including generated files and statistics
        """
        # Handle remote template fetching
        if is_remote_template:
            template_file = self._fetch_and_save_remote_template(
                template_file, template_cache_dir
            )
        
        # Analyze template
        template_analysis = self.analyze_template(template_file)
        attribute_patterns = template_analysis['attribute_patterns']
        
        if not attribute_patterns:
            raise ValueError("No roleAttribute patterns found in template file")
        
        # Load team data (refresh cache first if use_cache=False)
        data = self.load_team_data(use_cache=use_cache)
        
        # Determine teams to process
        if team_keys is None:
            teams_with_roles = self.get_teams_with_roles(data)
            team_keys = [team['key'] for team in teams_with_roles]
        
        # Get all custom roles for lookup
        all_roles = data.get('roles', [])
        roles_lookup = {role['key']: role for role in all_roles}
        
        generated_patches = []
        failed_teams = []  # Track failed teams with reasons
        skipped_teams = []  # Track skipped teams with reasons
        
        for team_key in team_keys:
            try:
                # Find team and its roles
                team_data = None
                for team in data.get('teams', []):
                    if team['key'] == team_key:
                        team_data = team
                        break
                
                if not team_data:
                    self.logger.warning(f"Team '{team_key}' not found")
                    failed_teams.append({
                        'team_key': team_key,
                        'reason': 'team_not_found',
                        'message': 'Team not found in LaunchDarkly (check team key spelling or refresh cache with --no-cache)'
                    })
                    continue
                
                team_roles = team_data.get('roles', [])
                if not team_roles:
                    self.logger.warning(f"Team '{team_key}' has no assigned roles")
                    skipped_teams.append({
                        'team_key': team_key,
                        'reason': 'no_assigned_roles',
                        'message': 'Team has no assigned roles to extract roleAttribute values from'
                    })
                    continue
                
                # Get full role data
                team_role_objects = []
                for role_key in team_roles:
                    if role_key in roles_lookup:
                        team_role_objects.append(roles_lookup[role_key])
                
                if not team_role_objects:
                    self.logger.warning(f"No role objects found for team '{team_key}'")
                    skipped_teams.append({
                        'team_key': team_key,
                        'reason': 'no_role_objects',
                        'message': 'Role data not found in cache for assigned roles'
                    })
                    continue
                
                # Extract roleAttribute values from team's roles
                team_attribute_values = {}
                
                # Initialize attribute value sets
                for attr_key in attribute_patterns:
                    team_attribute_values[attr_key] = set()
                
                # Extract values from each role assigned to this team
                for role in team_role_objects:
                    role_values = RoleAttributeExtractor.extract_from_role_with_patterns(role, attribute_patterns)
                    
                    # Merge with team collection
                    for attr_type, values in role_values.items():
                        if attr_type not in team_attribute_values:
                            team_attribute_values[attr_type] = set()
                        team_attribute_values[attr_type].update(values)
                
                # Remove empty sets
                team_attribute_values = {k: v for k, v in team_attribute_values.items() if v}
                
                if not team_attribute_values:
                    self.logger.info(f"No roleAttribute values found for team '{team_key}', generating patch with template roles only")
                
                # Get team's existing roleAttributes
                existing_role_attributes = team_data.get('roleAttributes', {})
                
                # Create patch file
                patch_filepath = self._create_team_patch_file(
                    [template_file], [template_analysis['role_key']], team_key, team_role_objects, 
                    team_attribute_values, output_dir,
                    existing_role_attributes=existing_role_attributes
                )
                
                generated_patches.append({
                    'team_key': team_key,
                    'patch_file': patch_filepath,
                    'roles_analyzed': [role.get('key', 'unknown') for role in team_role_objects],
                    'attribute_types': list(team_attribute_values.keys()),
                    'extracted_values': {k: sorted(list(v)) for k, v in team_attribute_values.items()}
                })
                
            except Exception as e:
                self.logger.error(f"Failed to process team '{team_key}': {e}")
                failed_teams.append({
                    'team_key': team_key,
                    'reason': 'exception',
                    'message': str(e)
                })
        
        return {
            'template_analysis': template_analysis,
            'teams_processed': len(team_keys),
            'patches_generated': len(generated_patches),
            'failed_teams': failed_teams,
            'skipped_teams': skipped_teams,
            'generated_patches': generated_patches,
            'output_directory': output_dir,
            'remote_template_used': is_remote_template,
            'template_file_used': template_file,
            'template_cache_directory': template_cache_dir if is_remote_template else None
        }

    def _create_team_patch_file(self, template_sources: List[str], template_role_keys: List[str], 
                               team_key: str, team_roles: List[Dict], 
                               team_attribute_values: Dict[str, Set[str]], 
                               output_dir: str, existing_role_attributes: Optional[Dict] = None) -> str:
        """
        Create and save patch file for a specific team
        
        Args:
            template_sources (List[str]): List of source template files used
            template_role_keys (List[str]): List of template role keys to add
            team_key (str): Team identifier
            team_roles (List[Dict]): Team's role objects
            team_attribute_values (Dict): Extracted attribute values
            output_dir (str): Output directory
            existing_role_attributes (Dict, optional): Team's existing roleAttributes
            
        Returns:
            str: Path to created patch file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Default to empty dict if not provided
        if existing_role_attributes is None:
            existing_role_attributes = {}
        
        # Create patch data for this team
        patch_data = {
            "team_key": team_key,
            "template_sources": template_sources,  # Changed to list
            "type": "team_roleAttribute_patch",
            "created_at": datetime.now().isoformat(),
            "roles_analyzed": [role.get('key', 'unknown') for role in team_roles],
            "extracted_values": {k: sorted(list(v)) for k, v in team_attribute_values.items()},
            "existing_role_attributes": existing_role_attributes,
            "instructions": []
        }
        
        # Add all template role keys to addCustomRoles instruction
        if template_role_keys:
            patch_data["instructions"].append({
                "kind": "addCustomRoles",
                "values": sorted(list(set(template_role_keys)))  # Remove duplicates and sort
            })
            
        # Create add/update RoleAttribute instructions for each discovered attribute
        for attribute in team_attribute_values:
            # Check if this attribute already exists in the team's roleAttributes
            if attribute in existing_role_attributes:
                kind = "updateRoleAttribute"
            else:
                kind = "addRoleAttribute"
            
            patch_data["instructions"].append({
                "kind": kind,
                "key": attribute,
                "values": sorted(list(team_attribute_values[attribute]))
            })
        
        # Save patch file with team-specific naming
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        patch_filename = f"{team_key}_{timestamp}_patch.json"
        patch_filepath = os.path.join(output_dir, patch_filename)
        
        with open(patch_filepath, 'w') as f:
            json.dump(patch_data, f, indent=2)
        
        self.logger.info(f"Generated patch for team '{team_key}': {patch_filepath}")
        return patch_filepath

    def _fetch_and_save_remote_template(self, role_key: str, template_cache_dir: str) -> str:
        """
        Fetch a remote template (custom role) from LaunchDarkly API and save it locally
        
        Args:
            role_key (str): The key of the custom role to fetch as template
            template_cache_dir (str): Directory to save the template
            
        Returns:
            str: Path to the saved template file
            
        Raises:
            Exception: If the role cannot be fetched or saved
        """
        try:
            # Create template cache directory if it doesn't exist
            os.makedirs(template_cache_dir, exist_ok=True)
            
            # Fetch the custom role from API
            self.logger.info(f"Fetching remote template role: {role_key}")
            role_data = self.api_client.get_custom_role(role_key)
            
            # Generate filename with timestamp for uniqueness
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            template_filename = f"{role_key}_{timestamp}.json"
            template_filepath = os.path.join(template_cache_dir, template_filename)
            
            # Save template to file
            with open(template_filepath, 'w') as f:
                json.dump(role_data, f, indent=2)
            
            self.logger.info(f"Remote template saved to: {template_filepath}")
            return template_filepath
            
        except Exception as e:
            self.logger.error(f"Failed to fetch and save remote template '{role_key}': {e}")
            raise Exception(f"Unable to fetch remote template '{role_key}': {e}")

    def apply_patches(self, team_keys: List[str], patch_dir: str = "output/patches", 
                     comment: str = "Applied patch via TeamManager") -> Dict:
        """
        Apply patch files to specified teams via LaunchDarkly API
        
        Args:
            team_keys (List[str]): Team keys to apply patches for
            patch_dir (str): Directory containing patch files
            comment (str): Comment for the patch operation
            
        Returns:
            Dict: Results of patch application including successes and failures
        """
        if not os.path.exists(patch_dir):
            raise FileNotFoundError(f"Patch directory not found: {patch_dir}")
        
        # Find patch files for specified teams and track all files per team
        all_patch_files = {}  # Track all files per team
        selected_patch_files = {}  # Final selected file per team
        
        for filename in os.listdir(patch_dir):
            if filename.endswith('_patch.json'):
                # Extract team key from filename (format: {team_key}_{timestamp}_patch.json)
                team_key_parts = filename.split('_')
                if len(team_key_parts) >= 3:  # Ensure proper format
                    team_key = team_key_parts[0]
                    if team_key in team_keys:
                        filepath = os.path.join(patch_dir, filename)
                        
                        # Track all patch files for this team
                        if team_key not in all_patch_files:
                            all_patch_files[team_key] = []
                        all_patch_files[team_key].append({
                            'filename': filename,
                            'filepath': filepath
                        })
                        
                        # Select the most recent patch file for each team (latest timestamp)
                        if team_key not in selected_patch_files or filename > selected_patch_files[team_key]['filename']:
                            selected_patch_files[team_key] = {
                                'filepath': filepath,
                                'filename': filename
                            }
        
        # Log patch file selection details
        self._log_patch_file_selection(all_patch_files, selected_patch_files, team_keys)
        
        if not selected_patch_files:
            raise ValueError(f"No patch files found for teams: {team_keys}")
        
        results = {
            'teams_requested': team_keys,
            'patches_found': len(selected_patch_files),
            'patches_applied': [],
            'failed_patches': [],
            'skipped_teams': [],
            'patch_file_details': {}  # Add details about which files were used
        }
        
        # Find teams without patch files
        teams_with_patches = set(selected_patch_files.keys())
        requested_teams = set(team_keys)
        results['skipped_teams'] = list(requested_teams - teams_with_patches)
        
        # Apply patches for each team
        for team_key, patch_info in selected_patch_files.items():
            try:
                # Log which patch file is being used
                self.logger.info(f"Applying patch for team '{team_key}' using file: {patch_info['filename']}")
                
                # Read patch file
                with open(patch_info['filepath'], 'r') as f:
                    patch_data = json.load(f)
                
                # Validate patch file structure
                if 'instructions' not in patch_data:
                    self.logger.error(f"Invalid patch file format for team '{team_key}': missing instructions")
                    results['failed_patches'].append({
                        'team_key': team_key,
                        'error': 'Invalid patch file format: missing instructions',
                        'patch_file': patch_info['filepath']
                    })
                    continue
                
                # Prepare API payload
                payload = {
                    "instructions": patch_data['instructions'],
                    "comment": comment
                }
                
                # Apply patch via API
                response = self.api_client.apply_team_patch(team_key, payload)
                
                # Store patch file details in results
                results['patch_file_details'][team_key] = {
                    'selected_file': patch_info['filename'],
                    'total_files_found': len(all_patch_files.get(team_key, [])),
                    'all_files': [f['filename'] for f in all_patch_files.get(team_key, [])]
                }
                
                if response.get('success', False):
                    results['patches_applied'].append({
                        'team_key': team_key,
                        'patch_file': patch_info['filepath'],
                        'patch_filename': patch_info['filename'],
                        'instructions_applied': len(patch_data['instructions']),
                        'instructions_details': patch_data['instructions'],
                        'response': response
                    })
                    self.logger.info(f"Successfully applied patch for team '{team_key}' from {patch_info['filename']}")
                else:
                    results['failed_patches'].append({
                        'team_key': team_key,
                        'error': response.get('error', 'Unknown API error'),
                        'patch_file': patch_info['filepath'],
                        'patch_filename': patch_info['filename']
                    })
                    self.logger.error(f"Failed to apply patch for team '{team_key}' from {patch_info['filename']}: {response.get('error')}")
            except Exception as e:
                results['failed_patches'].append({
                    'team_key': team_key,
                    'error': str(e),
                    'patch_file': patch_info['filepath'],
                    'patch_filename': patch_info['filename']
                })
                self.logger.error(f"Error applying patch for team '{team_key}' from {patch_info['filename']}: {e}")
        
        return results

    def _log_patch_file_selection(self, all_patch_files: Dict, selected_patch_files: Dict, 
                                 requested_teams: List[str]):
        """
        Log detailed information about patch file selection process
        
        Args:
            all_patch_files (Dict): All patch files found per team
            selected_patch_files (Dict): Selected patch files per team
            requested_teams (List[str]): Teams that were requested
        """
        self.logger.info(f"=== Patch File Selection Summary ===")
        
        for team_key in requested_teams:
            if team_key in all_patch_files:
                team_files = all_patch_files[team_key]
                selected_file = selected_patch_files[team_key]['filename']
                
                if len(team_files) == 1:
                    self.logger.info(f"Team '{team_key}': Found 1 patch file - {selected_file}")
                else:
                    # Sort files by timestamp (filename) for better display
                    sorted_files = sorted([f['filename'] for f in team_files])
                    self.logger.info(f"Team '{team_key}': Found {len(team_files)} patch files")
                    self.logger.info(f"  Available files: {', '.join(sorted_files)}")
                    self.logger.info(f"  Selected latest: {selected_file}")
            else:
                self.logger.warning(f"Team '{team_key}': No patch files found")
        
        self.logger.info(f"=== End Patch File Selection Summary ===")
        self.logger.info(f"Total teams with patches: {len(selected_patch_files)}/{len(requested_teams)}") 