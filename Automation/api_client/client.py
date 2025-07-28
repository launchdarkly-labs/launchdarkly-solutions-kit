import requests
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from tqdm import tqdm
from requests.exceptions import RequestException
import time
import logging


class LaunchDarklyAPI:
    """
    Client for interacting with the LaunchDarkly API.
    
    This client handles all API requests to LaunchDarkly, including fetching custom roles,
    teams, members, and projects. It implements caching to minimize API requests and
    provides methods for enriching the data with additional information.
    
    Attributes:
        api_key (str): LaunchDarkly API key
        base_url (str): Base URL for the LaunchDarkly API
        cache_dir (str): Directory to store cache files
        cache_file (str): Path to the main cache file
        cache_ttl (int): Cache time-to-live in hours
        headers (Dict): HTTP headers for API requests
        beta_headers (Dict): HTTP headers for beta API endpoints
        logger: Logger instance for this class
    """

    def __init__(self, api_key: str, cache_dir: str = "cache", cache_file: str = "ldc_cache_data.json", cache_ttl: int = 24):
        """
        Initialize LaunchDarkly API client
        
        Args:
            api_key (str): LaunchDarkly API key
            cache_dir (str): Directory to store cache files (default: "cache")
            cache_file (str): Name of main cache file (default: "ldc_cache_data.json")
            cache_ttl (int): Cache time-to-live in hours (default: 24)
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
        self.logger = logging.getLogger(__name__)

        self.logger.debug(f"cache_dir={self.cache_dir}")
        self.logger.debug(f"cache_file={self.cache_file}")
        self.logger.debug(f"cache_ttl={self.cache_ttl}")
        self.logger.debug(f"API Key={self.api_key}")
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)

    def _nextPage(self, response: dict) -> str:
        """
        Extract the next page URL from a paginated API response
        
        Args:
            response (dict): API response containing pagination information
            
        Returns:
            str: URL for the next page of results, or empty string if no more pages
        """
        links = response.get("_links", {})
        next_link = links.get("next", {}).get("href")
        
        if not next_link:
            return None
        
        if '/api/v2/' in next_link:
            next_page = next_link.split("/api/v2/")[1]
        else:
            next_page = next_link

        return next_page
    def _make_patch_request_with_backoff(self, endpoint: str, patch: List[dict], params: Optional[Dict] = None, 
                                 max_retries: int = 5, initial_delay: float = 1.0,
                                 use_beta: bool = False) -> dict:
        """
        Make a PATCH request with exponential backoff retry logic
        
        Handles rate limiting and retries with exponential backoff.
        
        Args:
            endpoint: API endpoint (path after /api/v2/)
            patch: List of patch operations to apply
            params: Optional query parameters
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            use_beta: Whether to use beta API headers
            
        Returns:
            dict: API response as dictionary
            
        Raises:
            RequestException: If all retries fail
        """
        delay = initial_delay
        last_exception = None
        headers = self.beta_headers if use_beta else self.headers

        for attempt in range(max_retries):
            try:
                response = requests.patch(
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    params=params,
                    json={"patch": patch}
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', delay))
                    self.logger.warning(f"\nRate limit reached. Waiting {retry_after} seconds.")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except RequestException as e:
                last_exception = e
                self.logger.error(f"Request failed: {str(e)}")
                self.logger.error(f"Response: {e.response.json()}")

                if e.response.status_code == 403:
                    raise e
                
                if attempt < max_retries - 1:
                    sleep_time = delay * (2 ** attempt)
                    self.logger.warning(f"Retrying in {sleep_time:.1f} seconds. (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(sleep_time)
                    continue
                raise

        raise last_exception

    
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
                    self.logger.warning(f"\nRate limit reached. Waiting {retry_after} seconds.")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except RequestException as e:
                last_exception = e
                if attempt < max_retries - 1:
                    sleep_time = delay * (2 ** attempt)
                    self.logger.warning(f"\nRequest failed: {str(e)}")
                    self.logger.warning(f"Retrying in {sleep_time:.1f} seconds. (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(sleep_time)
                    continue
                raise

        raise last_exception

    def get_project_environments(self, project_key: str, limit: int = 20) -> List[dict]:

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
                            "mobileKey": env["mobileKey"]
                        }
                        processed_environments.append(processed_env)
                    
                    all_environments.extend(processed_environments)
                    
                    next_page = self._nextPage(response)

                    params = {}  # Clear params as they're included in the URL

                except RequestException as e:
                    self.logger.error(f"\nError fetching environments page for project {project_key}: {e}")

                    if not all_environments:  # If we haven't fetched any environments yet
                        raise
                    self.logger.warning("Returning partially fetched environments.")
                    break
                    
        except RequestException as e:
            self.logger.error(f"\nError fetching environments for project {project_key}: {e}")
            return []
        
        return all_environments

    def get_custom_roles(self, limit: int = 20) -> List[dict]:
   
        all_roles = []
        next_page = "roles" 
        params = {"limit": limit}
        
        try:
            with tqdm(desc="Fetching custom roles", unit="page") as pbar:
                while next_page:
                    response = self._make_request_with_backoff(next_page, params)
                    roles = response.get("items", [])

                    if not roles:
                        break
                    
                    all_roles.extend(roles)
                    pbar.update(1)
                    pbar.set_postfix({"roles": len(all_roles)})
                    
                    next_page = self._nextPage(response)

                    params = {}
            return all_roles
            
        except Exception as e:
            self.logger.error(f"\nError fetching roles: {e}")
            raise e

    def get_custom_role(self, role_key: str) -> dict:
        """
        Fetch a specific custom role by its key
        
        Args:
            role_key (str): The key of the custom role to fetch
            
        Returns:
            dict: The custom role data
            
        Raises:
            Exception: If the role is not found or request fails
        """
        try:
            endpoint = f"roles/{role_key}"
            response = self._make_request_with_backoff(endpoint)
            self.logger.info(f"Successfully fetched custom role: {role_key}")
            return response
            
        except Exception as e:
            self.logger.error(f"\nError fetching custom role {role_key}: {e}")
            raise e
    

  

    def update_custom_role(self, custom_role_key: str, patch: List[dict]) -> dict:
        """
        Update a custom role using a JSON patch
        
        Args:
            custom_role_key (str): The key of the custom role to update
            patch (List[dict]): List of patch operations to apply
            
        Returns:
            dict: The updated custom role
            
        Raises:
            Exception: If the update fails
        """
        try:
            endpoint = f"roles/{custom_role_key}"
            response = self._make_patch_request_with_backoff(endpoint, patch)
            self.logger.info(f"Successfully updated custom role: {custom_role_key}")
            self.logger.info(f"Response: {response}")
            return response
        except Exception as e:
            self.logger.error(f"\nError updating custom role {custom_role_key}: {e}")
            raise e
        
    def _list_account_members(self, limit: int = 20) -> List[dict]:

        next_page = f"members"
        params = {"limit": limit, "expand":"customRoles,roleAttributes"}   
        account_members = []   
        try:
            with tqdm(desc="Fetching account members", unit="page") as pbar:
                while next_page:
                    response = self._make_request_with_backoff(next_page, params)
                    members = response.get("items", []) 
                    
                    if not members:
                        break
                    
                    account_members.extend(members)
                    pbar.update(1)
                    pbar.set_postfix({"members": len(account_members)})
                    
                    next_page = self._nextPage(response)

                    params = {}

                return account_members
            
        except Exception as e:
            self.logger.error(f"\nError fetching account_members: {e}")
            raise e
    
    def get_team_roles(self, team_key: str, limit: int = 20) -> List[dict]:
        """
        Fetch the custom roles that have been assigned to the team. 
        
        """
        next_page = f"teams/{team_key}/roles"
        params = {"limit": limit}   
        team_roles = []
        try:
            
            while next_page:
                response = self._make_request_with_backoff(next_page, params)
                roles = response.get("items", [])   
                
                if not roles:
                    break
                
                team_roles.extend(roles)
                next_page = self._nextPage(response)
                params = {}
            return team_roles
            
        except Exception as e:
            self.logger.error(f"\nError fetching team roles: {e}")
            raise e
        
    def list_teams(self, limit: int = 50) -> List[dict]:

        teams = []
        next_page = "teams" 
        params = {"limit": limit, "expand":"roles,members,projects,maintainers,roleAttributes"}
        
        try:
            with tqdm(desc="Fetching teams", unit="page") as pbar:
                while next_page:
                    response = self._make_request_with_backoff(next_page, params)
                    team = response.get("items", [])

                    if not team:
                        break
                    
                    teams.extend(team)
                    pbar.update(1)
                    pbar.set_postfix({"teams": len(teams)})
                    
                    next_page = self._nextPage(response)

                    params = {}

                return teams
            
        except Exception as e:
            self.logger.error(f"\nError fetching teams: {e}")
            raise e
        
    def get_team(self, team_key: str, limit: int = 50) -> dict:
        url = f"teams/{team_key}"
        params = {"expand":"roles,members,projects,maintainers,roleAttributes"}   
        team = {}
        try:
            with tqdm(desc=f"Fetching team {team_key}", total=1, unit="request") as pbar:
                team = self._make_request_with_backoff(url, params)
                pbar.update(1)
                return team
            
        except Exception as e:
            self.logger.error(f"\nError fetching teams details {e}")
            raise e
        
    def fetch_and_cache_data(self):
        try:
            data=self._enrich_fetched_data()
            # Save data to cache file
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)

            return data
            
        except Exception as e:
            self.logger.error(f"\nError fetching data: {e}")
            return None

    def load_cached_data(self) -> Optional[Dict]:
   
        if not os.path.exists(self.cache_file):
            return None
            
        try:
            # Load cache data
            with open(self.cache_file, 'r') as f:
                data = json.load(f)

       
            # Get cache TTL from data or use instance default
            cached_ttl = data.get("cache_ttl", self.cache_ttl)
            cache_date = datetime.fromisoformat(data["fetch_date"])
            cache_age = datetime.now() - cache_date

            # Check if cache has expired using the TTL from the cache if available
            if cache_age.total_seconds() >= (cached_ttl * 3600):
                self.logger.info(f"Cache expired (age: {cache_age}). Returning None")
                return None

            return data
            
        except Exception as e:
            print(f"Error loading cache: {e}")
            return None

    def purge_eval_cache(self):
        """
        Purge all cache files
        
        Removes the cache file in the cache directory.
        Creates the cache directory if it doesn't exist.
        """
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
        except Exception as e:
            print(f"Error removing {self.cache_file}: {e}")
        
        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)


    def _enrich_fetched_data (self)->dict:
        """
        Enrich the role data with the team and member data.
        """
        self.logger.debug(f"_enrich_fetched_data() start")
        

        data = {
            "fetch_date": datetime.now().isoformat(),
            "cache_ttl": self.cache_ttl,
        }
        try:
            checked_roles = {
                    'assigned':[],
                    'unassigned':[]
                }
            self.logger.info("Fetching custom roles...")
            roles = self.get_custom_roles()
            self.logger.info("Fetching teams...")
            teams = self.list_teams()
            assigned_teams = self._enrich_teams_with_roles(teams)
            team_project_list = self._create_teams_with_project_access_list(teams)  
            account_members = self._list_account_members()
            assigned_members = self._enrich_account_members_with_roles(account_members)
            self.logger.debug(f"_enrich_fetched_data() assigned_teams: {assigned_teams}")
            data["roles"] =[]
            data["total_roles"] = len(roles)
            data["total_teams"] = len(teams)
            data["total_account_members"] = len(account_members)
            data["teams"] = teams
            data["account_members"] = account_members

            self._enrich_team_with_member_email(teams, account_members)

            data["assigned_teams"] = assigned_teams # team with assigned roles
            data["assigned_members"] = assigned_members # members with assigned roles
            data["total_assigned_teams"] = len(assigned_teams)
            data["total_assigned_members"] = len(assigned_members)
            data["team_project_list"] = team_project_list
            for role in tqdm(roles, desc="Enriching role data", unit="role"):
                role_key = role['key']


                teams_with_role = self._list_teams_with_role(role_key, data['teams'])
                members_with_role = self._list_members_with_role(role_key, data['account_members'])
                role['teams'] = [team['key'] for team in teams_with_role]
                role['members'] = [member['email'] for member in members_with_role]

                role['total_teams'] = len(teams_with_role)
                role['total_members'] = len(members_with_role)
                role['total_assigned']= len(teams_with_role) + len(members_with_role)
                role['is_assigned'] = role['total_assigned'] > 0

                data['roles'].append(role)
                self.logger.debug(f"_enrich_fetched_data() role: {role['key']} total_teams={role['total_teams']} total_members={role['total_members']} total_assigned={role['total_assigned']} is_assigned={role['is_assigned']}")

                if role['is_assigned'] == False :
                    checked_roles['unassigned'].append(role["key"])   
                else:
                    checked_roles['assigned'].append(role["key"])   
                            
            data["unassigned_roles"] = checked_roles['unassigned']
            data["total_unassigned_roles"] = len(checked_roles['unassigned'])
            data["assigned_roles"] = checked_roles['assigned']
            data["total_assigned_roles"] = len(checked_roles['assigned'])
            self.logger.debug(f"_enrich_fetched_data() end")
            return data
        except Exception as e:
            self.logger.error(f"\nError enriching role data: {e}")
            raise e

    def _create_teams_with_project_access_list(self, teams:dict)->dict:
        self.logger.debug(f"_create_teams_with_project_access_list() start")

        team_project_list={}
        try:
            for team in teams:
                self.logger.debug(f"_create_teams_with_project_access_list() team: {team}")
                team_key = team['key']
                team_project_list[team_key]={}
                team_project_list[team_key]['projects']=[project['key'] for project in team['projects']['items']]
                team_project_list[team_key]['total_projects_write_access']=team['projects']['totalCount']
                team_project_list[team_key]['total_roles']=0
                team_project_list[team_key]['has_roles']=False
                
                if 'roles' in team:
                    team_project_list[team_key]['roles']=team['roles']
                    team_project_list[team_key]['has_roles']=len(team['roles'])>0

                self.logger.debug(f"_create_teams_with_project_access_list() team_project_list: {team_project_list[team_key]}")

            return team_project_list

        except Exception as e:
            self.logger.error(f"\nError creating team with project access list: {e}")
            raise e



    def _enrich_teams_with_roles (self,  teams: dict)->List[str]: 
        self.logger.debug(f"_enrich_teams_with_roles() start")

        teams_with_roles=[]
        try:
            from tqdm import tqdm
            
            for team in tqdm(teams, desc="Enriching teams with roles", unit="team"):
                team_key = team['key']
                team['roles'] = []
                self.logger.debug(f"_enrich_teams_with_role() Team: {team_key}")

                team_roles = self.get_team_roles(team_key)
                # self.logger.info(f"_enrich_teams_with_role() team: {team_key} roles: {team_roles}")
                # make the attribute consistent with the account members
                if len(team_roles) == 0:
                    self.logger.debug(f"_enrich_teams_with_role() team: {team_key} has no roles. Skipping...")
                    continue
                
                teams_with_roles.append(team_key)
                
                # make the attribute consistent with the account members
                team['customRolesInfo'] = team_roles
                for custom_role in team['customRolesInfo']:
                    team['roles'].append(custom_role['key'])
            return teams_with_roles

        except Exception as e:
            self.logger.error(f"\nError enriching teams with roles: {e}")
            raise e

    def _enrich_team_with_member_email(self, teams: dict, account_members: dict):
        self.logger.debug("_enrich_team_with_member_email() start")
        try:
            team_map = {team['key']: team for team in teams}
            for team in teams:
                team.setdefault('members', {}).setdefault('items', [])

            for member in account_members:
                for member_team in member.get('teams', []):
                    team = team_map.get(member_team['key'])
                    if team is not None:
                        team['members']['items'].append(member['email'])
            return teams
        except Exception as e:
            self.logger.error(f"\nError enriching team with member email: {e}")
            raise e

    def _enrich_account_members_with_roles (self,  account_members: dict)->List[Dict]: 
        self.logger.debug(f"_enrich_account_members_with_roles() start")
        members_with_roles=[]
        try:
            for member in account_members:
                
                member['roles']=[]
                if len(member['customRoles']) == 0:
                    self.logger.debug(f"_enrich_account_members_with_roles() member: {member['email']} has no roles. Skipping...")
                    continue

                members_with_roles.append(member['email'])

                if 'customRoles' in member and 'customRolesInfo' in member:
                    for role_id in member['customRoles']:
                        for role_info in member['customRolesInfo']:
                            if role_info['_id'] == role_id:
                                member['roles'].append(role_info['key'])
                        
                                self.logger.debug(f"_enrich_account_members_with_roles() Member: {member['email']} member roles: {member['roles']}")
                                break

                if len(member['roles']) >0:
                    # this is to make the attribute consistent with the teams
                    del member['customRoles']
            
            return members_with_roles
        except Exception as e:
            self.logger.error(f"\nError enriching account members with roles: {e}")
            raise e
            


    def _list_teams_with_role (self, role_key: str, teams: dict)->List[Dict]: 
     
        matched_teams = []
        try:
            for team in teams:
                team_key = team['key']
                if 'roles' not in team:
                    self.logger.info(f"_list_team_with_role() team: {team_key} has no roles. Skipping...")
                    self.logger.info(f"_list_team_with_role() team: {team}")
                    continue

                for team_role in team['roles']:
                    if team_role == role_key:
                        matched_teams.append(team)
                        break

        except Exception as e:
            self.logger.error(f"\nError listing teams with role: {e}")
            raise e
        
        return matched_teams

    def _list_members_with_role (self, role_key: str, members: dict)->List[Dict]:
        """
        Get a list of members who have a specific role assigned.

        Args:
            role_key (str): The role key to search for
            members (dict): Dictionary of account members

        Returns:
            List[Dict]: List of members with the specified role
        """
        members_with_role = []
        for member in members:
            for role in member.get('customRoles', []):
                if role['key'] == role_key:
                    members_with_role.append({
                        'email': member['email'],
                        'firstName': member.get('firstName', ''),
                        'lastName': member.get('lastName', ''),
                        'role': role_key
                    })
                    break  # Avoid duplicates if member has role multiple times

        return members_with_role

    def apply_team_patch(self, team_key: str, payload: Dict, max_retries: int = 5, 
                        initial_delay: float = 1.0) -> Dict:
        """
        Apply a patch to a team using the LaunchDarkly team update API
        
        Args:
            team_key (str): The team key to update
            payload (Dict): Payload containing instructions and optional comment
            max_retries (int): Maximum number of retry attempts
            initial_delay (float): Initial delay between retries in seconds
            
        Returns:
            Dict: Response from the API including success status
            
        Example payload:
            {
                "instructions": [
                    {
                        "kind": "addCustomRoles",
                        "values": ["role-key"]
                    },
                    {
                        "kind": "updateRoleAttribute", 
                        "key": "projectKey",
                        "values": ["project1", "project2"]
                    }
                ],
                "comment": "Applied patch via TeamManager"
            }
        """
        headers = {
            **self.headers,
           "Ld-Api-Version":'20240415',

            "Content-Type": "application/json; domain-model=launchdarkly.semanticpatch"
        }
        
        url = f"{self.base_url}/teams/{team_key}"
     
        
        for attempt in range(max_retries):
            try:
                response = requests.patch(url, headers=headers, json=payload)
                
                # Handle rate limiting with dynamic retry
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', initial_delay * (2 ** attempt)))
                    self.logger.warning(f"Rate limit reached for team {team_key}. Waiting {retry_after}s.")
                    time.sleep(retry_after)
                    continue
                
                # Process response (success or error)
                return self._process_patch_response(response, team_key)
                
            except RequestException as e:
        
            
                
                # Handle non-retryable errors immediately
                if self._is_non_retryable_error(e):
                    return self._create_error_response(team_key, e)
                
                # Log and potentially retry
                self.logger.error(f"Request failed for team {team_key} (attempt {attempt + 1}): {str(e)}")
                
                if attempt < max_retries - 1:
                    sleep_time = initial_delay * (2 ** attempt)
                    self.logger.warning(f"Retrying in {sleep_time:.1f}s. (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(sleep_time)
                else:
                    # Final attempt - return error
                    return self._create_error_response(
                        team_key, e, f"Request failed after {max_retries} attempts"
                    )
    
    def _process_patch_response(self, response: requests.Response, team_key: str) -> Dict:
        """Process the API response and return standardized result"""
        
        if response.status_code == 200:
            self.logger.info(f"Successfully applied patch to team: {team_key}")
            return {
                'success': True,
                'team_key': team_key,
                'response': response.json(),
                'status_code': response.status_code
            }
        
        # Handle error response
        error_data = self._safe_json_parse(response)
        error_message = error_data.get('message', f'HTTP {response.status_code}')
        
        self.logger.error(f"Failed to apply patch to team {team_key}: {error_message}")
        return {
            'success': False,
            'team_key': team_key,
            'error': error_message,
            'status_code': response.status_code,
            'response': error_data
        }
    
    def _is_non_retryable_error(self, exception: RequestException) -> bool:
        """Check if an error should not be retried"""
        if hasattr(exception, 'response') and exception.response is not None:
            # Don't retry authorization errors or client errors (4xx except 429)
            status_code = exception.response.status_code
            return status_code == 403 or (400 <= status_code < 500 and status_code != 429)
        return False
    
    def _create_error_response(self, team_key: str, exception: RequestException, 
                              custom_message: str = None) -> Dict:
        """Create standardized error response from exception"""
        error_message = custom_message or "Request failed"
        status_code = None
        
        if hasattr(exception, 'response') and exception.response is not None:
            status_code = exception.response.status_code
            error_data = self._safe_json_parse(exception.response)
            api_message = error_data.get('message', str(exception))
            
            if status_code == 403:
                error_message = f"Authorization error: {api_message}"
            elif custom_message:
                error_message = f"{custom_message}: {api_message}"
            else:
                error_message = api_message
        else:
            error_message = f"{error_message}: {str(exception)}"
        
        return {
            'success': False,
            'team_key': team_key,
            'error': error_message,
            'status_code': status_code
        }
    
    def _safe_json_parse(self, response: requests.Response) -> Dict:
        """Safely parse JSON response, return empty dict if parsing fails"""
        try:
            return response.json() if response.content else {}
        except (ValueError, json.JSONDecodeError):
            return {}

