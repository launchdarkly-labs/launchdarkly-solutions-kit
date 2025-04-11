import datetime
import os
import hashlib
import logging
import json
from pathlib import Path
from typing import Optional, Dict, List, Any
import re
import copy
import jsonpatch
class PolicyLinter:
    def __init__(self, patch_dir: Optional[Path] = "patches", logger: Optional[logging.Logger] = None):
        self.logger = logger
        self.patch_dir = patch_dir

    def set_logger(self, logger: logging.Logger):
        self.logger = logger
    def get_logger(self)->logging.Logger:
        return self.logger
    
    def set_patch_dir(self, patch_dir:Path)->None:
        self.patch_dir = patch_dir
    def get_patch_dir(self)->Path:
        return self.patch_dir
    

    def validate(self, policies: List[Dict[str, Any]], resource_actions: Dict[str, Dict[str, List[str]]]):
        policies = policies
        invalid_policies = self.get_invalid_actions(policies, resource_actions)
        self.logger.debug(f"Invalid policies:\n {invalid_policies}")
        self.logger.info(f"Found [{len(invalid_policies)}] policies with invalid actions.")
        return invalid_policies    
        # self.dump();
    
    def dump(self):
        self.logger.info(f"Resource actions:\n {self.resource_actions}")

   

    def get_matching_resource_actions(self, resource, resource_actions) -> List[str]:
        for pattern, actions in resource_actions['resources'].items():
            is_match = self.does_pattern_match(pattern, resource)
            if is_match:
                return actions
            
        return None
    

    def get_invalid_actions(self, policies: List[Dict[str, Any]], resource_actions: Dict[str, Dict[str, List[str]]]) -> Dict[str, List[str]]:
     
        invalid_policies = {}
        if not policies:
            raise ValueError("Missing policies")
            
        
        self.logger.info(f"Linting {len(policies)} policies")
        self.logger.debug(f"resource_actions: {resource_actions}")
        self.logger.debug(f"policies:{policies}")
        for role in policies:
            policy = role.get('policy', [])
            invalid_statements=[]

            for statement in policy:
                invalid_actions=[]
                resources = statement.get('resources', []) or statement.get('notResources', [])
                actions = statement.get('actions', []) or statement.get('notActions', [])
                effect = statement.get('effect', '')

                if len(resources) ==0:
                    continue

                resource = resources[0]

                valid_actions= self.get_matching_resource_actions(resource, resource_actions)
                if valid_actions is None:
                    # catch invalid resource names
                    invalid_statements.append(statement)
                    continue

                valid_actions.sort()
                actions.sort()
                
                for action in actions:
                    # Skip wildcard actions
                    if action == "*":
                        continue

                    if action not in valid_actions:
                        invalid_actions.append(action)
                        
                if len(invalid_actions) > 0:
                        invalid_statements.append({
                        'resources': resources,
                        'actions': invalid_actions,
                        'effect': effect
                    })

            if len(invalid_statements) > 0:
                invalid_policies[role['key']] = invalid_statements
                
                
        return invalid_policies
    
    
    def normalize_pattern(self,pattern):
        # Remove attribute specifications like ${...} and ;{...}
        pattern = re.sub(r'\$\{[^}]*\}', '*', pattern)  # Replace ${...} with *
        pattern = re.sub(r';{[^}]*}', '', pattern)      # Remove ;{...}
        return pattern

    def pattern_to_regex(self,pattern):
        # Normalize the pattern first to handle ${...} and ;{...}
        pattern = self.normalize_pattern(pattern)
        
        # Escape special regex characters
        pattern = re.escape(pattern)
        
        # Replace escaped * with regex wildcard that doesn't cross segment boundaries
        pattern = pattern.replace('\\*', '[^:]*')
        
        return f"^{pattern}$"

    def does_pattern_match(self,pattern, resource):
        # If pattern is a resource specification, convert it to regex
        regex = self.pattern_to_regex(pattern)
        # Normalize the resource to handle attributes
        norm_resource = self.normalize_pattern(resource)
        # Check if pattern matches resource
        return bool(re.match(regex, norm_resource))
    
    def get_valid_actions(self, policy_actions, invalid_actions)->list:
    
        valid_actions = [action for action in policy_actions if action not in invalid_actions]

        return valid_actions

    def create_resource_hash(self, statement) -> str:
        self.logger.debug(f"create_resource_hash() statement: {statement}")
        resources = statement.get('resources', []) or statement.get('notResources', [])
        if not resources:
            raise ValueError(f"Missing resources in statement {statement}")
        
        
        resources_str = ', '.join(sorted(resources))
        hash = hashlib.md5(resources_str.encode()).hexdigest()
        self.logger.debug(f"Creating hash for resources: [{resources_str}] hash: [{hash}]")
        return hash



    def set_policy_hash(self, policy)->None:
        policy['hash']=[]
        statements=policy.get('policy')
        for statement in statements:
            hash = self.create_resource_hash(statement)
            policy['hash'].append(hash)

        self.logger.debug(f"Setting hash for policy: {policy['key']} hash: {policy['hash']}")
    
    def remove_policy_hash(self, policy)->None:
    
        if policy.get('hash'):
            self.logger.debug(f"Removing hash from policy: {policy['key']} hash: {policy['hash']}")
            del policy['hash']
        else:
            self.logger.debug(f"No hash to remove from policy: {policy['key']}")
    


    def _get_policy_index(self, policies: dict, policy_key: str) -> int:
        for index, policy in enumerate(policies):
            if policy['key'] == policy_key:
                return index
        return None

    
    def fix_invalid_policies(self, policies: dict, invalid_policies: dict) -> None:
        
        skipped_policies=[]
        fixed_policies=[]
        for policy_key, invalid_statements in invalid_policies.items():
            # find the policy from all-policies.json that has the invalid statements
            policy_index = self._get_policy_index(policies, policy_key)
            if policy_index is None:
                raise ValueError(f"Policy {policy_key} not found in input policies. This should never happen.. check for typos in the invalid_actions.json file")

            statements_to_remove = []            
            modified_policy = copy.deepcopy(policies[policy_index])
            original_policy = copy.deepcopy(policies[policy_index])
            for invalid_statement in invalid_statements:
            
                invalid_resource_hash= self.create_resource_hash(invalid_statement)
                index = modified_policy['hash'].index(invalid_resource_hash)

                invalid_actions = invalid_statement['actions']

                valid_actions = self.get_valid_actions(modified_policy['policy'][index]['actions'], invalid_actions)
                modified_policy['policy'][index]['actions']=valid_actions
                self.logger.debug(f"Policy: {policy_key} Valid actions: {valid_actions}")
                self.logger.debug(f"Policy: {policy_key} Invalid actions: {invalid_actions}")

                if len(valid_actions) == 0:
                    statements_to_remove.append(modified_policy['policy'][index])
            
            # Remove the statements with empty actions
            for statement in statements_to_remove:
                modified_policy['policy'].remove(statement)

            
            if len(modified_policy.get('policy')) == 0:
                skipped_policies.append(policy_key)
                self.logger.warning(f"Policy [{policy_key}] has no statements after fixing invalid actions. Skipping writing patch for policy. Please consult with your LaunchDarkly admin.")
                continue
        
            self.remove_policy_hash(modified_policy)
            self.remove_policy_hash(original_policy)

            fixed_policies.append(policy_key)
            
            # create a patch and reverse patch
            self.generate_patches(original_policy, modified_policy, policy_key)

        # generate a custom role with ability to update the invalid policies 
        self.generate_limited_update_policy_role(fixed_policies)

        self.logger.info(f"Successfully fixed invalid policies. See patches in [{self.patch_dir}/*.patch].")
        self.logger.info(f"Skipped policies: count= {len(skipped_policies)}, list= {skipped_policies}")
        self.logger.info(f"Fixed policies: count= {len(fixed_policies)}, list= {fixed_policies}")
    
    
    def save_patch_file(self, policy_key:str, patch:list)-> str:
        patch_file_name = self.patch_dir / f"{policy_key}.patch"
        policy={
            "key": policy_key,
            "type": "patch",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "patch":list(patch)
        }
        PolicyLinter.save_policy(policy, patch_file_name)
        self.logger.info(f"Policy [{policy_key}]: Saved patch to {patch_file_name}")
        return patch_file_name
    
    def get_patch_key(self, content:dict)->str:
        return content.get('key')
    def get_patch_jsonpatch(self, content:dict)->list:
        return content.get('patch')
  
    def get_patch_type(self, content:dict)->str:
        return content.get('type')
    
    def is_valid_patch_file(self, content:dict)->bool:
        return content.get('type') == 'patch'
    
    def is_valid_reverse_patch_file(self, content:dict)->bool:
        return content.get('type') == 'reverse-patch'
    

    def save_patched_file(self, policy_key:str, patched_policy:list)-> str:
        patched_file_name = self.patch_dir / f"{policy_key}.patched"
        PolicyLinter.save_policy(patched_policy, patched_file_name)
        self.logger.info(f"Policy [{policy_key}]: Saved patched file to {patched_file_name}")
        return patched_file_name
    
    def save_reverse_patch_file(self, policy_key:str, reverse_patch:list)-> str:
        reverse_patch_file = self.patch_dir / f"{policy_key}.reverse-patch"
        policy={
            "key": policy_key,
            "type": "reverse-patch",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "patch":list(reverse_patch)
        }
        PolicyLinter.save_policy(policy, reverse_patch_file)
        self.logger.info(f"Policy [{policy_key}]: Saved reverse patch to {reverse_patch_file}")
        return reverse_patch_file
    
    def generate_limited_update_policy_role(self, fixed_policies:list)->None:
        self.logger.info(f"Generating Custom Role.")
        ld_policy=[
            {
                "resources": fixed_policies,
                "actions": [ "updatePolicy"],
                "effect": "allow"
            }]
        
        custom_role={
            "key": "limited-update-policy-role",
            "type": "custom-role",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "policy": ld_policy
        }

        file_name = self.patch_dir / "custom-role.role"
        PolicyLinter.save_policy(custom_role, file_name)
        self.logger.debug(f"Generated custom role:\n {custom_role}")
        self.logger.info(f"Custom Role saved to {file_name}")
        return file_name
      
    
    def generate_patches(self, original_policy, modified_policy, policy_key)->None:
            # Create PATCH and REVERSE PATCH
            self.logger.info(f"Generating patches for policy [{policy_key}].")
            patch = jsonpatch.make_patch(original_policy, modified_policy)
            applied_patch_policy= jsonpatch.apply_patch(original_policy, patch)
            reverse_patch = jsonpatch.make_patch(modified_policy, original_policy)
           
            # fail fast if the patch is not valid , don't bother saving the patch
            self.test_patch(modified_policy, applied_patch_policy)
            self.test_reverse_patch(original_policy, modified_policy, reverse_patch)

         
            self.save_patch_file(policy_key, list(patch))
            self.save_patched_file(policy_key, applied_patch_policy)
            self.save_reverse_patch_file(policy_key,  list(reverse_patch))
            self.logger.info(f"Successfully generated patches for policy [{policy_key}].")

            
    def test_reverse_patch(self, original_policy, modified_policy, reverse_patch_policy)->None:
        policy_key = modified_policy['key']
        applied_patch_policy= jsonpatch.apply_patch(modified_policy, reverse_patch_policy)
        test_patch= jsonpatch.make_patch(original_policy, applied_patch_policy)
        test_is_pass = "Pass" if len(list(test_patch)) == 0 else "Fail"
        self.logger.debug(f"test_reverse_patch(): Testing reverse patch for policy [{policy_key}]")
        self.logger.debug(f"test_reverse_patch(): Original policy:\n {json.dumps(original_policy)}")
        self.logger.debug(f"test_reverse_patch(): Reverse patch policy:\n {reverse_patch_policy}")
        self.logger.debug(f"test_reverse_patch(): Applied patch policy:\n {applied_patch_policy}")
       
        self.logger.info(f"Dry-run: Tested reverse patch for policy [{policy_key}]... {test_is_pass}")
        if test_is_pass == "Fail":
            # this should never happen
            self.logger.error("-----------DEBUG INFO---------------------")
            self.logger.error(f"Original policy:\n {json.dumps(original_policy, indent=2)}")
            self.logger.error(f"Reverse patch policy:\n {json.dumps(list(reverse_patch_policy), indent=2)}")
            self.logger.error("--------------------------------")
            raise ValueError(f"WARNING!!! WARNING!!! Check your code, reverse patch file is not the same as the original policy [{policy_key}]")
    
    def test_patch(self, modified_policy, applied_patch_policy)->None:
        # the modified policy should be the same as the applied patch policy
        # mdofied policy - policy without the invalid statements
        # applied patch policy - policy with the invalid statements removed using the patch
        policy_key = modified_policy['key']
        test_patch= jsonpatch.make_patch(modified_policy, applied_patch_policy)
        test_is_pass = "Pass" if len(list(test_patch)) == 0 else "Fail"
        self.logger.debug(f"test_patch(): Testing patch for policy [{policy_key}]")
        self.logger.debug(f"test_patch(): Modified policy:\n {modified_policy}")
        self.logger.debug(f"test_patch(): Applied patch policy:\n {applied_patch_policy}")
        
        self.logger.info(f"Dry-run: Tested patch for policy [{policy_key}]... {test_is_pass}")
        
        if test_is_pass == "Fail":
            # this should never happen
            self.logger.error("-----------DEBUG INFO---------------------")
            self.logger.error(f"Modified policy:\n {json.dumps(modified_policy, indent=2)}")
            self.logger.error(f"Applied patch policy:\n {json.dumps(list(applied_patch_policy), indent=2)}")
            self.logger.error("--------------------------------")
            raise ValueError(f"WARNING!!! WARNING!!! Check your code, patched file is not the same as the modified policy [{policy_key}]")
    


    @staticmethod
    def save_policy(json_data: dict, file_path : str) -> list:
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
         
            with open(file_path, 'w') as f:
                json.dump(json_data, f, indent=2)
            
        except Exception as e:
            raise ValueError(f"Failed to save policy to {file_path}: {str(e)}")