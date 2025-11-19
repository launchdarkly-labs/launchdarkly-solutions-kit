#!/usr/bin/env python3

import requests
import json
import sys
import csv
from datetime import datetime, timedelta
import os
from typing import Dict, List, Optional
import argparse
from tqdm import tqdm
from dotenv import load_dotenv
from pathlib import Path
import time
from requests.exceptions import RequestException



class LaunchDarklyAPI:
    """
    A client for interacting with the LaunchDarkly API to fetch and analyze feature flag data.

    This class provides methods to fetch projects, environments, feature flags, and their usage metrics
    from LaunchDarkly. It implements caching to reduce API calls and handles rate limiting with
    exponential backoff.

    Attributes:
        api_key (str): LaunchDarkly API key for authentication
        base_url (str): Base URL for LaunchDarkly API (https://app.launchdarkly.com/api/v2)
        cache_dir (str): Directory path for storing cache files (default: "cache")
        cache_file (str): Path to the main cache file within cache_dir
        cache_ttl (int): Time-to-live for cached data in hours
        headers (dict): Standard HTTP headers including authentication
        beta_headers (dict): Headers for beta API endpoints

    Example:
        ```python
        # Initialize with default cache directory
        api = LaunchDarklyAPI("your-api-key", cache_ttl=24)
        
        # Or specify custom cache directory
        api = LaunchDarklyAPI("your-api-key", cache_dir="/path/to/cache")
        
        # Fetch all projects
        projects = api.get_all_projects()
        
        # Get feature flags for a specific project
        flags = api.get_feature_flags("project-key")
        
        # Get evaluation metrics
        metrics = api.get_flag_evaluations("project-key", "env-key", "flag-key")
        ```

    Note:
        - Uses caching by default to minimize API calls
        - Cache files are stored in the specified cache directory
        - Implements automatic retry with exponential backoff
        - Handles rate limiting according to LaunchDarkly's guidelines
        - Supports both standard and beta API endpoints
    """
    def __init__(self, api_key: str, cache_dir: str = "cache", cache_file: str = "ldc_cache_data.json", cache_ttl: int = 24):
        """
        Initialize LaunchDarkly API client
        
        Args:
            api_key: LaunchDarkly API key
            cache_dir: Directory to store cache files (default: "cache")
            cache_file: Name of main cache file (default: "ldc_cache_data.json")
            cache_ttl: Cache time-to-live in hours (default: 24)
        """
        self.api_key = api_key
        self.base_url = "https://app.launchdarkly.com/api/v2"
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(self.cache_dir, cache_file)
        self.cache_ttl = cache_ttl
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
        self.beta_headers = {
            **self.headers,
            "LD-API-Version": "beta"
        }
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)

    def _nextPage(self, response: dict) -> str:
        links = response.get("_links", {})
        next_link = links.get("next", {}).get("href")
        
        if not next_link:
            return None
        
        if '/api/v2/' in next_link:
            next_page = next_link.split("/api/v2/")[1]
        else:
            next_page = next_link

        return next_page

    def _make_request_with_backoff(self, endpoint: str, params: Optional[Dict] = None, 
                                 max_retries: int = 5, initial_delay: float = 1.0,
                                 use_beta: bool = False) -> dict:
        """
        Make a GET request with exponential backoff retry logic
        
        Handles rate limiting and retries with exponential backoff.
        For paginated endpoints, follows the _links pattern from LaunchDarkly API.
        
        Args:
            endpoint: API endpoint (path after /api/v2/)
            params: Optional query parameters
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            use_beta: Whether to use beta API headers
            
        Returns:
            dict: API response as dictionary
            
        Raises:
            RequestException: If all retries fail
            
        Note:
            - Handles 429 rate limit responses
            - Uses exponential backoff for retries
            - Supports beta API endpoints
        """
        delay = initial_delay
        last_exception = None
        headers = self.beta_headers if use_beta else self.headers

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    params=params
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', delay))
                    print(f"\nRate limit reached. Waiting {retry_after} seconds.")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except RequestException as e:
                last_exception = e
                if attempt < max_retries - 1:
                    sleep_time = delay * (2 ** attempt)
                    print(f"\nRequest failed: {str(e)}")
                    print(f"Retrying in {sleep_time:.1f} seconds. (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(sleep_time)
                    continue
                raise

        raise last_exception

    def get_project_environments(self, project_key: str, limit: int = 20) -> List[dict]:
        """
        Fetch environments for a specific project with pagination
        
        Uses LaunchDarkly's pagination pattern by following _links in the response.
        Handles partial results if errors occur during pagination.
        
        Args:
            project_key: Project identifier
            limit: Number of items per page (default: 20)
        
        Returns:
            List[dict]: List of environment dictionaries with the following structure:
            {
                "key": str,           # Environment identifier
                "name": str,          # Display name
                "color": str,         # Color code
                "defaultTtl": int,    # Default TTL
                "secureMode": bool,   # Secure mode enabled
                "defaultTrackEvents": bool,  # Event tracking
                "requireComments": bool,     # Comment requirement
                "confirmChanges": bool,      # Change confirmation
                "tags": List[str],          # Environment tags
                "critical": bool,           # Critical environment
                "apiKey": str,             # SDK key
                "mobileKey": str           # Mobile key
            }
            
        Note:
            Will return partial results if some pages fail but initial fetch succeeds
        """
        all_environments = []
        next_page = f"projects/{project_key}/environments"
        params = {"limit": limit}
        
        try:
            while next_page:
                try:
                    response = self._make_request_with_backoff(next_page, params)
                    environments = response.get("items", [])
                    
                    if not environments:
                        break
                        
                    # Extract relevant environment data
                    processed_environments = []
                    for env in environments:
                        processed_env = {
                            "key": env["key"],
                            "name": env["name"],
                            "color": env["color"],
                            "defaultTtl": env["defaultTtl"],
                            "secureMode": env["secureMode"],
                            "defaultTrackEvents": env["defaultTrackEvents"],
                            "requireComments": env["requireComments"],
                            "confirmChanges": env["confirmChanges"],
                            "tags": env.get("tags", []),
                            "critical": env.get("critical", False),
                            "apiKey": env["apiKey"],
                            "mobileKey": env["mobileKey"],  
                            "approvalRequired": env["approvalSettings"]["required"],
                            "bypassApprovalsForPendingChanges": env["approvalSettings"]["bypassApprovalsForPendingChanges"],
                            "minNumApprovals": env["approvalSettings"]["minNumApprovals"],
                            "canReviewOwnRequest": env["approvalSettings"]["canReviewOwnRequest"],
                            "canApplyDeclinedChanges": env["approvalSettings"]["canApplyDeclinedChanges"],
                            "serviceKind": env["approvalSettings"]["serviceKind"],
                            "requiredApprovalTags": env["approvalSettings"]["requiredApprovalTags"],
                        }
                        processed_environments.append(processed_env)
                    
                    all_environments.extend(processed_environments)
                    
                    next_page = self._nextPage(response)

                    params = {}  # Clear params as they're included in the URL

                except RequestException as e:
                    print(f"\nError fetching environments page for project {project_key}: {e}")
                    if not all_environments:  # If we haven't fetched any environments yet
                        raise
                    print("Returning partially fetched environments.")
                    break
                    
        except RequestException as e:
            print(f"\nError fetching environments for project {project_key}: {e}")
            return []
        
        return all_environments

    def get_all_projects(self, tags: Optional[List[str]] = None, limit: int = 20) -> List[dict]:
        """
        Fetch all projects from LaunchDarkly API with optional tag filtering
        
        Uses LaunchDarkly's pagination pattern by following _links in the response.
        The API returns first, prev, next, and last links. Missing links indicate
        non-existent pages (e.g., no prev link on first page).
        
        Args:
            tags: Optional list of tags to filter projects. All tags must match.
            
        Returns:
            List[dict]: List of project dictionaries
            
        Note:
            Uses a smaller page size (20) to better handle rate limits
            Automatically follows pagination links until all items are retrieved
        """
        try:
            # Build initial URL with filter and limit

            params = {"limit": limit}

            if tags:
                # Join multiple tags with '+' and URL encode
                tags_filter = "+".join(tags)
                params["filter"] = f"tags:{tags_filter}"
            
            projects = []
            next_page = "projects"  # Initial endpoint
            
            while next_page:
                response = self._make_request_with_backoff(next_page, params)
                
                if response and "items" in response:
                    projects.extend(response["items"])
                
                next_page = self._nextPage(response)

                params = {}

            return projects
            
        except Exception as e:
            print(f"\nError fetching projects: {e}")
            return []

    def get_feature_flags(self, project_key: str, limit: int = 20) -> List[dict]:
        """
        Fetch all feature flags for a project with pagination
        
        Uses LaunchDarkly's pagination pattern and includes a progress bar.
        Fetches detailed flag data for each flag in the list.
        
        Args:
            project_key: Project identifier
            limit: Number of items per page (default: 50)
        
        Returns:
            List[dict]: List of detailed flag dictionaries
            
        Note:
            - Shows progress bar during fetch
            - Handles partial results if errors occur
            - Fetches detailed data for each flag
            - Follows pagination links automatically
        """
        all_flags = []
        progress = tqdm(desc=f"Fetching flags for {project_key}", unit="flags", leave=False)
        
        try:
            # Build initial URL with filter and limit
            params = {"limit": limit}
            next_page = f"flags/{project_key}"  # Initial endpoint
            while next_page:
                try:
                    response = self._make_request_with_backoff(next_page, params)
                    flags = response.get("items", [])
                    
                    if not flags:
                        break
                    
                    # Process each flag
                    for flag in flags:
                        try:
                            flag_detail = self._make_request_with_backoff(
                                f"flags/{project_key}/{flag['key']}"
                            )
                            all_flags.append(flag_detail)
                        except RequestException as e:
                            print(f"\nError fetching details for flag {flag['key']}: {e}")
                            # Add basic flag data if detailed fetch fails
                            all_flags.append(flag)
                    
                    # Update progress
                    progress.total = response.get("totalCount", 0)
                    progress.n = len(all_flags)
                    progress.refresh()
                    
                    next_page = self._nextPage(response)

                    params = {}
                        
                except RequestException as e:
                    print(f"\nError fetching flags page for project {project_key}: {e}")
                    if not all_flags:  # If we haven't fetched any flags yet
                        raise
                    print("Returning partially fetched flags.")
                    break
                    
        except RequestException as e:
            print(f"Error fetching flags for project {project_key}: {e}")
            return []
        finally:
            progress.close()
        
        return all_flags
    def get_flag_statuses_by_environment(self, project_key: str, environment_key: str, limit: int = 20) -> Dict[str, dict]:
        """
        Fetch status of all flags in a specific environment
        
        Args:
            project_key: Project identifier
            environment_key: Environment key
            limit: Number of items per page (max 50)
        
        Returns:
            Dictionary mapping flag keys to their status
        """
        status_map = {}
        offset = 0
        
        try:
            while True:
                params = {
                    "limit": limit,
                    "offset": offset
                }
                
                response = self._make_request_with_backoff(
                    f"flag-statuses/{project_key}/{environment_key}",
                    params=params
                )
                
                statuses = response.get("items", [])
                if not statuses:
                    break
                    
                for status in statuses:
                    
                    # Extract flag key from the parent link
                    flag_key = status["_links"]["parent"]["href"].split("/")[-1]
                    
                    status_map[flag_key] = {
                        "lastRequested": status.get("lastRequested"),
                        "status": status["name"]
                    }
                
                offset += len(statuses)
                total = response.get("totalCount", 0)
                if offset >= total:
                    break
                    
        except RequestException as e:
            print(f"\nError fetching flag statuses for {project_key}/{environment_key}: {e}")
        
        return status_map

    def _fetch_project_data(self, project: dict) -> dict:
        """
        Fetch all flag and status data for a project
        
        Args:
            project: Project dictionary with basic info
        
        Returns:
            Project dictionary with complete flag and environment data
        """
        project_data = {
            "key": project["key"],
            "name": project["name"],
            "tags": project.get("tags", []),
            "environments": self.get_project_environments(project["key"]),
            "flags": []
        }
        
        # Get all flags for the project
        flags = self.get_feature_flags(project["key"])
        
        # For each environment, get flag statuses
        env_statuses = {}
        for env in project_data["environments"]:
            env_key = env["key"]
            env_statuses[env_key] = self.get_flag_statuses_by_environment(
                project["key"], 
                env_key
            )
        
        # Process each flag with its status per environment
        for flag in tqdm(flags, desc=f"Processing flags for {project['key']}", leave=False):
            flag_data = flag.copy()
            
            if "environments" not in flag_data:
                flag_data["environments"] = {}
            
            for env in project_data["environments"]:
                env_key = env["key"]
                if env_key not in flag_data["environments"]:
                    flag_data["environments"][env_key] = {}
                
                env_data = flag_data["environments"][env_key]
                status_data = env_statuses[env_key].get(flag["key"], {})
                
                env_data.update({
                    "lastRequested": status_data.get("lastRequested"),
                    "status": status_data.get("status", "unknown"),
                    "on": env_data.get("on", False),
                    "archived": env_data.get("archived", False)
                })
            
            project_data["flags"].append(flag_data)
        
        return project_data

    def get_single_project(self, project_key: str) -> Optional[dict]:
        """
        Fetch data for a single project
        
        Args:
            project_key: Project identifier
        
        Returns:
            Project dictionary with all its data or None if not found
        """
        try:
            # Get project details
            project = self._make_request_with_backoff(f"projects/{project_key}")
            return self._fetch_project_data(project)
            
        except RequestException as e:
            if e.response and e.response.status_code == 404:
                return None
            raise

    
    def fetch_and_cache_data(self, force: bool = False, project_key: Optional[str] = None, 
                           tags: Optional[List[str]] = None):
        """
        Fetch data from LaunchDarkly and cache it
        
        Args:
            force: Force refresh even if cache exists
            project_key: Optional specific project to fetch
            tags: Optional list of tags to filter projects
            
        Returns:
            dict: Fetched data
        """
        # Check if we can use cached data
        if not force:
            cached_data = self.load_cached_data()
            if cached_data:
                if tags:
                    cached_data["projects"] = self._filter_projects_by_tags(cached_data["projects"], tags)

                return cached_data
                
        data = {
            "fetch_date": datetime.now().isoformat(),
            "cache_ttl": self.cache_ttl,  # Store current TTL in cache
            "projects": []
        }
        
        try:
            if project_key:
                # Fetch single project
                project = self.get_single_project(project_key)
                if project:
                    data["projects"].append(project)
                else:
                    raise ValueError(f"Project '{project_key}' not found")
            else:
                # Fetch projects with optional tag filter
                projects = self.get_all_projects(tags)
                if not projects:
                    if tags:
                        tags_str = "', '".join(tags)
                        raise ValueError(f"No projects found with tags: '{tags_str}'")
                    else:
                        raise ValueError("No projects found")
                        
                for project in tqdm(projects, desc="Processing projects"):
                    project_data = self._fetch_project_data(project)
                    data["projects"].append(project_data)

            # Save to cache file
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)

            return data
            
        except Exception as e:
            print(f"\nError fetching data: {e}")
            return None

    def _get_eval_cache_path(self, project_key: str) -> str:
        """Get the path for the evaluation metrics cache file"""
        return os.path.join(self.cache_dir, f"ldc_cache_eval_{project_key}.json")
         
    def load_cached_data(self, cache_path: Optional[str] = None) -> Optional[Dict]:
        """
        Load cached data from a JSON file if it exists and is still valid.
        
        Args:
            cache_path (Optional[str]): Path to the cache file. If None, uses default cache file.
            
        Returns:
            Optional[Dict]: Dictionary containing cached data if valid, None otherwise
            
        The cache is considered invalid if:
        - The file doesn't exist
        - The cache TTL has changed from the value stored in the cache
        - The cache has expired based on TTL (time since fetch_date exceeds TTL)
        
        The cache data structure contains:
        - fetch_date: ISO format timestamp of when data was fetched
        - cache_ttl: TTL value in hours that was used when caching
        - projects: List of project data dictionaries
        """
        if cache_path is None:
            cache_path = self.cache_file
            
        if not os.path.exists(cache_path):
            return None
            
        try:
            with open(cache_path, 'r') as f:
                cache = json.load(f)

            cached_ttl = cache.get("cache_ttl")
            if cached_ttl != self.cache_ttl:
                print(f"Cache TTL changed from {cached_ttl} to {self.cache_ttl} hours")
                return None       
            
            # Check cache validity
            cache_date = datetime.fromisoformat(cache["fetch_date"])
            cache_age = datetime.now() - cache_date

            # Check if cache TTL has changed
            if cache_age.total_seconds() < (self.cache_ttl * 3600):
                return cache
            
        except Exception as e:
            print(f"Error loading evaluation cache: {e}")
        
        
        return None   
    
  
            
    def _save_eval_cache(self, project_key: str, data: Dict):
        """Save evaluation metrics to cache file"""
        cache_path = self._get_eval_cache_path(project_key)
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving evaluation cache: {e}")

    def _filter_projects_by_tags(self, projects: List[dict], tags: List[str]) -> List[dict]:
        """
        Filter projects by tags.
        
        Args:
            projects: List of project dictionaries to filter
            tags: List of tag strings to filter by
            
        Returns:
            List[dict]: Filtered list of projects that have any of the specified tags
            
        Example:
            >>> projects = [{"name": "Project1", "tags": ["tag1", "tag2"]}]
            >>> tags = ["tag1"]
            >>> filtered = _filter_projects_by_tags(projects, tags)
            >>> len(filtered)
            1
        """
        filtered_projects = []
        for project in projects:
            project_tags = set(project.get("tags", []))
            if any(tag in project_tags for tag in tags):
                filtered_projects.append(project)
        return filtered_projects
    
    def get_flag_evaluations(self, project_key: str, environment_key: str, flag_key: str, 
                        days: int = 30, start_date: Optional[datetime] = None, 
                        timezone: str = "UTC", force_refresh: bool = False) -> Optional[int]:
        """
        Get total flag evaluations for a specific time period.
        """
        try:
            # Try to get from cache first
            if not force_refresh:
                cache = self.load_cached_data(self._get_eval_cache_path(project_key))
                if cache:
                    cache_key = f"{environment_key}:{flag_key}:{days}:{start_date.isoformat() if start_date else 'now'}"
                    if cache_key in cache["evaluations"]:
                        return cache["evaluations"][cache_key]
            
            # Calculate timestamps
            end_date = start_date or datetime.now()
            from_date = end_date - timedelta(days=days)
            
            # Convert to millisecond timestamps
            from_ts = int(from_date.timestamp() * 1000)
            to_ts = int((end_date + timedelta(days=1)).timestamp() * 1000)  # Include full end date
            
            # print(f"\nFetching evaluations for {flag_key} in {environment_key} days: {days}")
            # print(f"From: {from_date.isoformat()} ({from_ts})")
            # print(f"To: {end_date.isoformat()} ({to_ts})")
            
            params = {
                'from': str(from_ts),
                'to': str(to_ts),
                'tz': timezone
            }

            response = self._make_request_with_backoff(
                f"usage/evaluations/{project_key}/{environment_key}/{flag_key}",
                params=params,
                use_beta=True
            )
            
            if response and 'totalEvaluations' in response:
                total = response['totalEvaluations']
                # print(f"Total evaluations: {total}")
                
                # Update cache
                cache = self.load_cached_data(self._get_eval_cache_path(project_key)) or {
                    "fetch_date": datetime.now().isoformat(),
                    "cache_ttl": self.cache_ttl,
                    "evaluations": {}
                }
                
                cache_key = f"{environment_key}:{flag_key}:{days}:{start_date.isoformat() if start_date else 'now'}"
                cache["evaluations"][cache_key] = total
                self._save_eval_cache(project_key, cache)
                
                return total
                
            print("No evaluation data in response")
            return None
            
        except Exception as e:
            print(f"\nError fetching evaluations for flag {flag_key}: {e}")
            return None

    def purge_eval_cache(self, project_key: Optional[str] = None):
        """
        Purge evaluation metrics cache files
        
        Args:
            project_key: Optional specific project cache to purge.
                       If None, purges all files in the cache directory.
                       
        Note:
            - If project_key is provided, only removes that project's evaluation cache
            - If project_key is None, removes all files in the cache directory
            - The cache directory itself is preserved
        """
        if project_key:
            cache_path = self._get_eval_cache_path(project_key)
            if os.path.exists(cache_path):
                os.remove(cache_path)
        else:
            if os.path.exists(self.cache_dir):
                for filename in os.listdir(self.cache_dir):
                    if filename.startswith("ldc_cache_") and filename.endswith(".json"):
                        file_path = os.path.join(self.cache_dir, filename)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                        except Exception as e:
                            print(f"Error removing {file_path}: {e}")
            
            # Ensure cache directory exists
            os.makedirs(self.cache_dir, exist_ok=True)

    def _fetch_flag_evaluation_metrics(self, project_key: str, environment_key: str, 
                                    flag_key: str, force_refresh: bool = False) -> Dict[str, Optional[int]]:
        """
        Fetch evaluation metrics for 7, 14, 30, and 60-day periods
        
        Args:
            project_key: Project identifier
            environment_key: Environment identifier
            flag_key: Flag identifier
            force_refresh: Whether to bypass cache
        
        Returns:
            Dict with evaluation counts for different time periods:
            {
                '60_day_evals': int,  # Evaluations in last 60 days
                '30_day_evals': int,  # Evaluations in last 30 days
                '14_day_evals': int,  # Evaluations in last 14 days
                '7_day_evals': int    # Evaluations in last 7 days
            }
        
        Note:
            Shows recent usage trends with increasing granularity:
            - 60 days for long-term usage pattern
            - 30 days for monthly activity
            - 14 days for bi-weekly trend
            - 7 days for recent activity
        """
        metrics = {
            '60_day_evals': None,
            '30_day_evals': None,
            '14_day_evals': None,
            '7_day_evals': None
        }
        
        today = datetime.now()
        
        # Get evaluations for each time period
        for days in [60, 30, 14, 7]:
            count = self.get_flag_evaluations(
                project_key,
                environment_key,
                flag_key,
                days=days,
                start_date=None,  # Use current date
                force_refresh=force_refresh
            )
            metrics[f'{days}_day_evals'] = count or 0
        
        # print(f"\nMetrics for {flag_key} in {environment_key}:")
        # print(f"Last 60 days: {metrics['60_day_evals']}")
        # print(f"Last 30 days: {metrics['30_day_evals']}")
        # print(f"Last 14 days: {metrics['14_day_evals']}")
        # print(f"Last 7 days: {metrics['7_day_evals']}")
        
        return metrics

def parse_args():
    """
    Parse command line arguments
    
    Returns:
        argparse.Namespace: Parsed command line arguments
        
    Command Line Options:
        --force-refresh: Force refresh of cached data
        --output (-o): Output file path (default: flag_cleanup_report.csv)
        --cache-ttl: Cache time-to-live in hours (default: 24)
        --project_key (-p): Specific project key to analyze
        --tag (-t): Filter by project tag(s). Can be specified multiple times
        --list-projects: List all available projects and exit
        --list-tags: List all available project tags and exit
        --all-projects: Generate report for all projects
        --cache-dir: Directory to store cache files (default: cache)
        
    Note:
        Running without arguments triggers interactive mode
    """
    parser = argparse.ArgumentParser(
        description="LaunchDarkly Feature Flag Cleanup Report Generator",
        usage="%(prog)s [options]"
    )
    parser.add_argument("--force-refresh", action="store_true", 
                      help="Force refresh of cached data")
    parser.add_argument("--output", "-o", 
                      help="Output file path (default: flag_cleanup_report.csv)")
    parser.add_argument("--cache-ttl", type=int, default=24,
                      help="Cache time-to-live in hours (default: 24)")
    parser.add_argument("--project_key", "-p", 
                      help="Specific project key to analyze")
    parser.add_argument("--tag", "-t",
                      action="append",  # Changed from 'store' to 'append' to support multiple tags
                      help="Filter by project tag(s). Can be specified multiple times for multiple tags")
    parser.add_argument("--list-projects", action="store_true",
                      help="List all available projects and exit")
    parser.add_argument("--list-tags", action="store_true",
                      help="List all available project tags and exit")
    parser.add_argument("--all-projects", action="store_true",
                      help="Generate report for all projects")
    parser.add_argument("--cache-dir", default="cache",
                      help="Directory to store cache files (default: cache)")
    parser.add_argument("--environment-report", action="store_true",
                      help="Generate environment report")
    parser.add_argument("--flag-details",
                      help="Generate flag details report for all flags in project and environments. Requires project key to be specified.")
    
    args = parser.parse_args()
    isInvalidArgs = False

    # Show help and validate arguments
    if len(sys.argv) == 1:
        # No arguments triggers interactive mode
        return args
    elif not any([args.all_projects, args.list_projects, args.list_tags, args.project_key, args.tag, args.flag_details]):
        print("\nError: Must specify one of:")
        print("  --all-projects    : Generate report for all projects")
        print("  --project_key (-p): Generate report for specific project")
        print("  --tag (-t)        : Generate report for projects with tag")
        print("  --list-projects   : List available projects")
        print("  --list-tags       : List available tags")
        print("  --flag-details    : Generate flag details report for specific project")
        print("  Or run without arguments for interactive mode")
        isInvalidArgs = True

    if isInvalidArgs:
        sys.exit(1)
        
    return args
def _obfuscate_key(key: str, show_last: int = 4) -> str:
    """
    Obfuscate all characters/digits of a key except for the last N characters.
    
    Args:
        key: The key string to obfuscate
        show_last: Number of characters to show at the end (default: 4)
        
    Returns:
        Obfuscated string with asterisks replacing all but the last N characters
        
    Examples:
        >>> _obfuscate_key("987654321")
        '*****4321'
        >>> _obfuscate_key("sdk-1234-5678-9012", 4)
        '**************9012'
        >>> _obfuscate_key("abc", 4)
        'abc'
        >>> _obfuscate_key("")
        ''
    """
    if not key:
        return ""
    if len(key) <= show_last:
        return key
    visible_part = key[-show_last:]
    hidden_count = len(key) - show_last
    return "*" * hidden_count + visible_part

def _to_datetime_format(last_req: str) -> Optional[datetime]:
    """
    Convert LaunchDarkly timestamp string to datetime object
    
    Args:
        last_req: ISO format timestamp string (e.g. "2024-03-14T15:30:00Z")
        
    Returns:
        datetime object or None if conversion fails
    """
    if last_req is None:
        return None
        
    try:
        # Ensure timestamp has milliseconds
        if '.' not in last_req:
            last_req = last_req.replace('Z', '.000Z')
        return datetime.strptime(last_req, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return None

def _day_ago_from_today(last_req: str) -> str:
    """
    Calculate days since last request in a human-readable format
    
    Args:
        last_req: ISO format timestamp string
        
    Returns:
        String describing time since last request (e.g. "Today", "5 days ago", "Never")
    """
    if last_req is None:
        return "Never"
   
    today = datetime.now()
    lastRequested_dt = _to_datetime_format(last_req)
    lastRequestedDays = (today - lastRequested_dt).days 
    if lastRequestedDays <= 0:
        return "Today"

    return f"{lastRequestedDays} days ago"

def list_projects(ld_api: LaunchDarklyAPI, data: Optional[dict] = None) -> List[dict]:
    """
    List all available LaunchDarkly projects with usage statistics
    
    Args:
        ld_api: LaunchDarklyAPI instance
        data: Optional pre-filtered data dictionary
        
    Returns:
        List of project dictionaries
        
    Displays table with:
        - Project name and key
        - Project tags
        - Number of flags
        - Days since last flag evaluation
        - Environment names
    """
    if not data:
        data = ld_api.load_cached_data()
        if not data:
            print("No cached data found. Fetching from LaunchDarkly API...")
            data = ld_api.fetch_and_cache_data()
    
    projects = data["projects"]
    today = datetime.now()
    charCount = 140  # Increased width for new column
    
    print("\nAvailable Projects:")
    print("-" * charCount)
    print(f"{'#':<4} {'Project Name':<30} {'Project Key':<25} {'Project Tags':<25} {'Flags':<8} {'Last Requested':<25} {'Environments':<10}")
    print("-" * charCount)
    
    for i, project in enumerate(projects, 1):
        # Get most recent flag evaluation across all flags and environments
        most_recent = None
     

        # Find most recent flag evaluation across all flags and environments
        last_requested_dates = []
        for flag in project["flags"]:
            for env_data in flag["environments"].values():
                if date := _to_datetime_format( env_data.get("lastRequested")):
                    last_requested_dates.append(date)
        
        most_recent = max(last_requested_dates) if last_requested_dates else None

        # Format display string
        if most_recent:
            days_since = (today - most_recent).days
            days_display = "Today" if days_since <= 0 else f"{days_since} days ago"
        else:
            days_display = "Never"

        flag_count = len(project["flags"])
        tags = ", ".join(project.get("tags", [])) or "none"
        project_name = project["name"]
        if len(project_name) > 25:
            project_name = project_name[:22] + "..."
        project_key = project["key"]
        if len(project_key) > 25:
            project_key = project_key[:22] + "..."
        if len(tags) > 25:
            tags = tags[:20] + "..."

        envs = ", ".join([env["name"] for env in project["environments"]])
        print(f"{i:<4} {project_name:<30} {project_key:<25} {tags:<25} {flag_count:<8} {days_display:<25} {envs:<10}")
    
    print("-" * charCount)
    print(f"\nTotal Projects: {len(projects)}")
    
    return projects

def prompt_for_project(projects: List[dict]) -> Optional[str]:
    """
    Interactive prompt for user to select a project from the list.
    
    Args:
        projects: List of project dictionaries to choose from
        
    Returns:
        Optional[str]: Selected project key, 'all' for all projects, or None to quit
        
    Interactive Options:
        - Enter number (1-N): Select specific project
        - 'a': Analyze all projects
        - 'q': Quit application
        
    Example:
        >>> projects = [{"key": "demo", "name": "Demo Project"}]
        >>> key = prompt_for_project(projects)
        Select a project number (or 'a' for all projects, 'q' to quit): 1
        >>> print(key)
        'demo'
    """
    while True:
        choice = input("\nSelect a project number (or 'a' for all projects, 'q' to quit): ").strip().lower()
        
        if choice == 'q':
            return None
        elif choice == 'a':
            return 'all'
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(projects):
                return projects[index]["key"]
            else:
                print(f"Please enter a number between 1 and {len(projects)}")
        except ValueError:
            print("Please enter a valid number, 'a' for all projects, or 'q' to quit")

def generate_environment_report(data: dict, output_file: str, project_key: Optional[str] = None):
    """
    Generate CSV report of environment data
    
    Args:
        data: Project and environment data from LaunchDarkly
        output_file: Path to output CSV file
        project_key: Optional specific project to analyze (if None, includes all projects)
    """
    # Generate timestamp in Unix epoch format (milliseconds)
    report_timestamp = int(time.time() * 1000)
    
    headers = [
        'Project_Key', 'Environment_Key', 'Environment_Name', 'Color', 
        'Default_TTL', 'Secure_Mode', 'Default_Track_Events', 'Require_Comments',
        'Confirm_Changes', 'Tags', 'Critical', 'API_Key', 'Mobile_Key',
        'Approval_Required', 'Bypass_Approvals_For_Pending_Changes', 
        'Min_Num_Approvals', 'Can_Review_Own_Request', 'Can_Apply_Declined_Changes',
        'Service_Kind', 'Required_Approval_Tags', 'Report_Generated_Timestamp'
    ]
    rows = []
    for project in data.get('projects', []):
        current_project_key = project.get('key', '')
        if project_key and current_project_key != project_key:
            continue
        environments = project.get('environments', [])
        for env in environments:
            row = {
                'Project_Key': current_project_key,
                'Environment_Key': env.get('key', ''),
                'Environment_Name': env.get('name', ''),
                'Color': env.get('color', ''),
                'Default_TTL': env.get('defaultTtl', ''),
                'Secure_Mode': env.get('secureMode', ''),
                'Default_Track_Events': env.get('defaultTrackEvents', ''),
                'Require_Comments': env.get('requireComments', ''),
                'Confirm_Changes': env.get('confirmChanges', ''),
                'Tags': ';'.join(env.get('tags', [])) if env.get('tags') else '',
                'Critical': env.get('critical', ''),
                'API_Key': _obfuscate_key(env.get('apiKey', '')),
                'Mobile_Key': _obfuscate_key(env.get('mobileKey', '')),
                'Approval_Required': env.get('approvalRequired', ''),
                'Bypass_Approvals_For_Pending_Changes': env.get('bypassApprovalsForPendingChanges', ''),
                'Min_Num_Approvals': env.get('minNumApprovals', ''),
                'Can_Review_Own_Request': env.get('canReviewOwnRequest', ''),
                'Can_Apply_Declined_Changes': env.get('canApplyDeclinedChanges', ''),
                'Service_Kind': env.get('serviceKind', ''),
                'Required_Approval_Tags': ';'.join(env.get('requiredApprovalTags', [])) if env.get('requiredApprovalTags') else '',
                'Report_Generated_Timestamp': report_timestamp
            }
            rows.append(row)
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Environment report generated: {output_file}")
    print(f"Total environments: {len(rows)}")
def generate_flag_details_report(data: dict, output_file: str, ld_api: LaunchDarklyAPI, 
                          project_key: str, force_refresh: bool = False):
    """
    Generate CSV report with detailed flag information for a specific project.
    Each row represents one flag in one environment.
    
    Args:
        data: Project and flag data from LaunchDarkly
        output_file: Path to output CSV file
        ld_api: LaunchDarklyAPI instance for fetching evaluation metrics
        project_key: Specific project to analyze (required)
        force_refresh: Whether to bypass cache
    """
    # Generate timestamp in Unix epoch format (milliseconds)
    report_timestamp = int(time.time() * 1000)
    
    headers = [
        'Primary_Key',  # <project-key>_<environment-key>_<flag-key>
        'Project_Name',
        'Project_Key',
        'Project_Tags',
        'Environment_Key',
        'Environment_Name',
        'Flag_Name',
        'Flag_Key',
        'Maintainer',
        'Creation_Date',
        'Days_Since_Creation',
        'Flag_State',  # On/Off
        'Flag_Status',  # active/inactive/launched
        'Archived',
        'Last_Requested',
        'Days_Since_Last_Eval',
        'Temporary',
        'Flag_Tags',
        'Kind',
        '60_Day_Evals',
        '30_Day_Evals',
        '14_Day_Evals',
        '7_Day_Evals',
        'Report_Generated_Timestamp'
    ]
    today = datetime.now()
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        target_project = next(
            (p for p in data["projects"] if p["key"] == project_key),
            None
        )
        if not target_project:
            raise ValueError(f"Project '{project_key}' not found")
        projects = [target_project]
        total_rows = sum(
            len(project["flags"]) * len(project["environments"]) 
            for project in projects
        )
        progress = tqdm(total=total_rows, desc="Generating flag details report", unit="rows")
        for project in projects:
            project_tags = ", ".join(project.get("tags", [])) or "none"
            for flag in project["flags"]:
                creation_date = datetime.fromtimestamp(flag["creationDate"] / 1000)
                days_since_creation = (today - creation_date).days + 1
                for env in project["environments"]:
                    env_key = env["key"]
                    env_name = env["name"]
                    env_data = flag["environments"].get(env_key, {})
                    primary_key = f"{project['key']}_{env_key}_{flag['key']}"
                    state = "On" if env_data.get("on") else "Off"
                    status = env_data.get("status", "unknown")
                    archived = "Yes" if env_data.get("archived") else "No"
                    last_req = env_data.get("lastRequested")
                    if last_req is not None:
                        days_ago = _day_ago_from_today(last_req)
                        days_since_eval = (today - _to_datetime_format(last_req)).days if _to_datetime_format(last_req) else ""
                    else:
                        last_req = "Never"
                        days_ago = "Never"
                        days_since_eval = ""
                    metrics = ld_api._fetch_flag_evaluation_metrics(
                        project["key"], 
                        env_key, 
                        flag["key"],
                        force_refresh=force_refresh
                    )
                    row = [
                        primary_key,
                        project["name"],
                        project["key"],
                        project_tags,
                        env_key,
                        env_name,
                        flag["name"],
                        flag["key"],
                        flag.get("_maintainer", {}).get("email", "No maintainer"),
                        creation_date.strftime("%Y-%m-%d"),
                        days_since_creation,
                        state,
                        status,
                        archived,
                        last_req,
                        days_since_eval,
                        "Yes" if flag.get("temporary", False) else "No",
                        ", ".join(flag.get("tags", [])) or "none",
                        flag.get("kind", "unknown"),
                        metrics.get('60_day_evals', 0),
                        metrics.get('30_day_evals', 0),
                        metrics.get('14_day_evals', 0),
                        metrics.get('7_day_evals', 0),
                        report_timestamp
                    ]
                    writer.writerow(row)
                    progress.update(1)  # Update progress bar
        progress.close()
    print(f"\nFlag details report generated successfully: {output_file}")
    print(f"Total rows: {total_rows}")
    return 0
def generate_cleanup_report(data: dict, output_file: str, ld_api: LaunchDarklyAPI, 
                          project_key: Optional[str] = None, force_refresh: bool = False):
    """
    Generate CSV report of flag usage and evaluation metrics
    
    Args:
        data: Project and flag data from LaunchDarkly
        output_file: Path to output CSV file
        ld_api: LaunchDarklyAPI instance for fetching evaluation metrics
        project_key: Optional specific project to analyze
        force_refresh: Whether to bypass cache
    """
    # Generate timestamp in Unix epoch format (milliseconds)
    report_timestamp = int(time.time() * 1000)
    
    # Define base headers
    base_headers = [
        'Project_Name', 'Project_Key', 'Project_Tags',
        'Flag_Name', 'Flag_Key', 'Maintainer',
        'Creation_Date', 'Days_Since_Creation',
        'Environment_Count', 'Environment_Details',
        'Temporary', 'Flag_Tags', 'Kind'
    ]
    
    # Add evaluation headers only for single project reports
    headers = base_headers.copy()
    if project_key:
        # Get all environment keys for the project
        project = next((p for p in data["projects"] if p["key"] == project_key), None)
        if project:
            for env in project["environments"]:
                env_name = env["name"]
                headers.extend([
                    f'{env_name} 60 Day Evals',
                    f'{env_name} 30 Day Evals',
                    f'{env_name} 14 Day Evals',
                    f'{env_name} 7 Day Evals'
                ])
    
    # Add timestamp as last column
    headers.append('Report_Generated_Timestamp')
    
    today = datetime.now()
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        # Find target project if specified
        target_project = None
        if project_key:
            target_project = next(
                (p for p in data["projects"] if p["key"] == project_key),
                None
            )
            if not target_project:
                raise ValueError(f"Project '{project_key}' not found")
        
        # Use either the single target project or all projects
        projects = [target_project] if target_project else data["projects"]
        
        # Calculate total flags for progress bar
        total_flags = sum(len(project["flags"]) for project in projects)
        progress = tqdm(total=total_flags, desc="Generating report", unit="flags")
                
        for project in projects:
            project_tags = ", ".join(project.get("tags", [])) or "none"
            
            for flag in project["flags"]:
                creation_date = datetime.fromtimestamp(flag["creationDate"] / 1000)
                
                # Get environment details
                env_details = []
                env_metrics = {}  # Dictionary to store metrics per environment
                
                for env in project["environments"]:
                    env_key = env["key"]
                    env_name = env["name"]
                    env_data = flag["environments"].get(env_key, {})
                    
                    # Get existing environment details
                    state = "On" if env_data.get("on") else "Off"
                    status = env_data.get("status")
                    archived = True if env_data.get("archived") else False
                    last_req = env_data.get("lastRequested")
                    if last_req is not None:
                        days_ago = _day_ago_from_today(last_req)
                        eval_info = f"Last eval: {last_req} ({days_ago})"
                    else:
                        eval_info = "Never evaluated"
                    
                    # Only fetch evaluation metrics for single project reports
                    if project_key:
                        metrics = ld_api._fetch_flag_evaluation_metrics(
                            project["key"], 
                            env_key, 
                            flag["key"],
                            force_refresh=force_refresh
                        )
                        
                        env_metrics[env_name] = metrics
                    
                    env_details.append(
                        f"{env_key}: {state}, status={status}, "
                        f"archived={archived}, {eval_info}"
                    )
                
                # Build row with base data
                row = [
                    project["name"],
                    project["key"],
                    project_tags,
                    flag["name"],
                    flag["key"],
                    flag.get("_maintainer", {}).get("email", "No maintainer"),
                    creation_date.strftime("%Y-%m-%d"),
                    (today - creation_date).days + 1,
                    len(flag["environments"]),
                    " | ".join(env_details),
                    "Yes" if flag.get("temporary", False) else "No",
                    ", ".join(flag.get("tags", [])) or "none",
                    flag.get("kind", "unknown")
                ]
                
                # Add evaluation metrics only for single project reports
                if project_key:
                    for env in project["environments"]:
                        env_name = env["name"]
                        metrics = env_metrics.get(env_name, {})
                        row.extend([
                            metrics.get('60_day_evals', 0),
                            metrics.get('30_day_evals', 0),
                            metrics.get('14_day_evals', 0),
                            metrics.get('7_day_evals', 0)
                        ])
                
                # Add timestamp as last column
                row.append(report_timestamp)
                
                writer.writerow(row)
                progress.update(1)  # Update progress bar

        progress.close()
    print(f"\nReport generated successfully: {output_file}")
    return 0

def list_project_tags(ld_api: LaunchDarklyAPI) -> List[str]:
    """
    List all unique project tags and their associated projects.
    
    Args:
        ld_api: LaunchDarklyAPI instance to fetch project data
        
    Returns:
        List[str]: List of unique project tags
        
    Displays:
        Table showing:
        - Tag name
        - Projects using the tag
        - Count of projects per tag
    """
    data = ld_api.load_cached_data()
    if not data:
        print("No cached data found. Fetching from LaunchDarkly API...")
        data = ld_api.fetch_and_cache_data()
    
    # Collect unique tags
    all_tags = set()
    tag_projects = {}
    
    for project in data["projects"]:
        for tag in project.get("tags", []):
            all_tags.add(tag)
            if tag not in tag_projects:
                tag_projects[tag] = []
            tag_projects[tag].append(project["name"])
    
    # Display tags and their projects
    print("\nAvailable Project Tags:")
    print("-" * 100)
    print(f"{'Tag':<30} {'Projects':<60} {'Count':<10}")
    print("-" * 100)
    
    for tag in sorted(all_tags):
        projects = tag_projects[tag]
        project_list = ", ".join(projects)
        if len(project_list) > 57:
            project_list = project_list[:54] + "..."
        print(f"{tag:<30} {project_list:<60} {len(projects):<10}")
    
    print("-" * 100)
    print(f"\nTotal Tags: {len(all_tags)}")
    
    return list(all_tags)

def load_environment() -> str:
    """
    Load LaunchDarkly API key from environment variables or .env file.
    
    Searches for LAUNCHDARKLY_API_KEY in:
        1. Current directory .env file
        2. Project root .env file
        3. Environment variables
        
    Returns:
        str: LaunchDarkly API key
        
    Raises:
        ValueError: If API key is not found in any location
    """
    # Try to load from .env in current directory
    env_path = Path('.') / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Try to load from project root
        project_root = Path(__file__).parent.parent
        env_path = project_root / '.env'
        if env_path.exists():
            load_dotenv(env_path)
    
    api_key = os.getenv('LAUNCHDARKLY_API_KEY')
    if not api_key:
        raise ValueError(
            "LAUNCHDARKLY_API_KEY not found. Please create a .env file with your API key "
            "or set it as an environment variable."
        )
    return api_key

def log_command_execution(args: argparse.Namespace, log_file: str = "command_execution_log.csv"):
    """
    Log the command execution details to a CSV file.
    
    Args:
        args: Parsed command line arguments
        log_file: Path to the log file (default: command_execution_log.csv)
        
    The log includes:
        - Human-readable timestamp
        - Timestamp in milliseconds (Unix epoch)
        - Command type (report type or action)
        - All options/parameters used
    """
    # Generate timestamps
    now = datetime.now()
    human_readable_timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    timestamp_ms = int(now.timestamp() * 1000)
    
    # Determine command type
    if args.list_projects:
        command = "list_projects"
    elif args.list_tags:
        command = "list_tags"
    elif args.flag_details:
        command = "flag_details_report"
    elif args.environment_report:
        command = "environment_report"
    else:
        command = "cleanup_report"
    
    # Build options string
    options = []
    if args.project_key:
        options.append(f"project_key={args.project_key}")
    if args.tag:
        options.append(f"tags={','.join(args.tag)}")
    if args.all_projects:
        options.append("all_projects=True")
    if args.force_refresh:
        options.append("force_refresh=True")
    if args.output:
        options.append(f"output={args.output}")
    if args.cache_ttl != 24:  # Only log if non-default
        options.append(f"cache_ttl={args.cache_ttl}")
    if args.cache_dir != "cache":  # Only log if non-default
        options.append(f"cache_dir={args.cache_dir}")
    if args.flag_details:
        options.append(f"flag_details={args.flag_details}")
    
    options_str = "; ".join(options) if options else "none"
    
    # Check if log file exists to determine if we need to write header
    file_exists = os.path.exists(log_file)
    
    try:
        with open(log_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header if file is new
            if not file_exists:
                writer.writerow([
                    'Timestamp_Human_Readable',
                    'Timestamp_Milliseconds',
                    'Command',
                    'Options'
                ])
            
            # Write log entry
            writer.writerow([
                human_readable_timestamp,
                timestamp_ms,
                command,
                options_str
            ])
    except Exception as e:
        # Don't fail the application if logging fails
        print(f"Warning: Failed to write to log file: {e}")

def main() -> int:
    """
    Main entry point for the LaunchDarkly cleanup report generator.
    """
    try:
        args = parse_args()
        
        # Log command execution
        log_command_execution(args)
        
        # Load API key from .env file
        try:
            api_key = load_environment()
        except ValueError as e:
            print(f"Error: {e}")
            print("\nYou can:")
            print("1. Create a .env file with your API key")
            print("2. Copy .env.example to .env and update it")
            print("3. Set LAUNCHDARKLY_API_KEY as an environment variable")
            return 1

        ld_api = LaunchDarklyAPI(
            api_key, 
            cache_ttl=args.cache_ttl,
            cache_dir=args.cache_dir
        )
        
        # Handle cache purging for force refresh
        if args.force_refresh:
            if args.project_key:
                ld_api.purge_eval_cache(args.project_key)
            elif args.flag_details:
                ld_api.purge_eval_cache(args.flag_details)
            else:
                ld_api.purge_eval_cache()
        
        # Handle --list-tags option
        if args.list_tags:
            list_project_tags(ld_api)
            return 0
        
        # Handle --list-projects option
        if args.list_projects:
            print("Fetching projects...")
            data = ld_api.fetch_and_cache_data(
                force=args.force_refresh,
                tags=args.tag
            )
            if not data:
                print("Failed to fetch project data")
                return 1
                
            list_projects(ld_api, data)
            return 0
        if args.flag_details:
            print(f"Fetching flag details for project: {args.flag_details}")
            data = ld_api.fetch_and_cache_data(
                force=args.force_refresh,
                project_key=args.flag_details
            )
            if not data:
                print("Failed to fetch project data")
                return 1
            output_file = args.output if args.output else f"flag_details_{args.flag_details}.csv"
            generate_flag_details_report(
                data,
                output_file,
                ld_api,
                args.flag_details,
                force_refresh=args.force_refresh
            )
            return 0
        
        # Fetch data
        print("Loading data...")
        data = None
        if os.path.exists(ld_api.cache_file) and not args.force_refresh:
            data = ld_api.load_cached_data()
            # Filter by tags if specified
            if data and args.tag:
                data["projects"] = ld_api._filter_projects_by_tags(data["projects"], args.tag)
        
        if not data:
            print("Fetching from LaunchDarkly API...")
            data = ld_api.fetch_and_cache_data(
                force=args.force_refresh,
                project_key=args.project_key,
                tags=args.tag
            )
            
        if not data:
            print("Failed to fetch data")
            return 1
            
        # Interactive mode if no specific project or all-projects flag
        if not (args.project_key or args.all_projects or args.flag_details):
            # Display projects and get user selection
            projects = list_projects(ld_api, data)
            selected_key = prompt_for_project(projects)
            
            if selected_key is None:  # User chose to quit
                return 0
            elif selected_key != 'all':  # User selected specific project
                args.project_key = selected_key
            # If 'all' was selected, proceed with all projects
        
        # Generate report
        if args.environment_report:
            output_file = args.output if args.output else "environment_report.csv"
            generate_environment_report(data, output_file, args.project_key)
        else:
            output_file = args.output if args.output else "flag_cleanup_report.csv"
            generate_cleanup_report(
                data, 
                output_file, 
                ld_api, 
                args.project_key,
                force_refresh=args.force_refresh
            )
        return 0
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"\nError: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main()) 