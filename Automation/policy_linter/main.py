from dotenv import load_dotenv
import json
import os
import sys

import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from policy_linter import PolicyLinter
from api_client import LaunchDarklyAPI


class App:
    def __init__(self):
        
        
        self.args = self._get_command_line_args()
     
        self.log_level = logging.DEBUG if self.args.debug else logging.INFO
        self.log_file = "policy_linter.log" if self.args.log_file is None else self.args.log_file
        self.loggers = self.setup_logging(log_level=self.log_level, log_file=self.log_file)
        self.logger= self.loggers.getLogger('main')

        self.api_key = self.load_api_key_from_env()
        self.ld_api_client = LaunchDarklyAPI(api_key=self.api_key)


        
        self.output_dir = Path("./output")
        self.reports_dir = self.output_dir / "reports"
        self.export_dir = self.output_dir / "exported_roles"
        
        self.patch_dir = self.output_dir / "patches"
        self.invalid_actions_file= self.reports_dir / "invalid_actions.json"
        self.all_policies_file= self.export_dir / "all-policies.json"

        self.resource_actions = json.load(open(self.args.resource_actions))
        self.policy_linter = PolicyLinter(patch_dir=self.patch_dir, logger=self.loggers.getLogger('policy_linter'))
    
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.patch_dir.mkdir(parents=True, exist_ok=True)
        
        self.export_dir.mkdir(parents=True, exist_ok=True)

                

    def run(self):
        has_option=False

        try:
            if self.args.export:
                self.logger.info("=== Exporting policies ===")
                has_option=True
                self._proc_export_policies()

            if self.args.validate:
                self.logger.info("=== Validating policies ===")
                has_option=True
                self._proc_validate_policies()
            
            # check after validate to ensure invalid actions file exists
            if self.args.fix:
                self.logger.info("=== Fixing policies ===")
                has_option=True
                self._proc_fix_policies()
            
            if self.args.apply_patch:
                self.logger.info("=== Apply Patch file to Policy ===")
                has_option=True
                ret= self._proc_apply_patch_policy()
                if ret == 1:
                    return 1
            
            if self.args.reverse_patch:
                self.logger.info("=== Apply Reverse Patch file to Policy ===")
                has_option=True
                ret= self._proc_apply_reverse_patch_policy()
                if ret == 1:
                    return 1
                
            if not has_option:
                self.logger.info("No options selected. Please select at least one option.")
                self.logger.info("Use --help to see available options.")
                return 1
            
            return 0
        
        except Exception as e:
            self.logger.error(f"Error occurred: {str(e)}", exc_info=True)
            return 1
    

    
        
    def _proc_apply_patch_policy(self):
        patch_file = self.args.apply_patch
        self.logger.info(f"Loading patch file: {patch_file}")
        content = json.load(open(patch_file))

        if not self.policy_linter.is_valid_patch_file(content):
            raise ValueError(f"Invalid patch file: {patch_file}. Make sure the patch file is valid and in the patches directory [{self.patch_dir}/*.patch] with the correct type [patch].")   

        
        policy_key = self.policy_linter.get_patch_key(content)
        json_patch = self.policy_linter.get_patch_jsonpatch(content)
        patch_type = self.policy_linter.get_patch_type(content)
        
        self.logger.debug(f"Patch policy key: {policy_key}")
        self.logger.debug(f"Patch json patch: {json_patch}")
        self.logger.debug(f"Patch type: {patch_type}")
        confirmation = input(f"\tLoaded Patch for Policy [{policy_key}]. Do you want to apply it? (y/N): ")
        
        if not confirmation or confirmation.lower() != 'y':
            # escape hatch
            self.logger.info("Patch operation cancelled by user")
            return 1

        self.logger.info(f"User confirmed, applying patch for {policy_key} using [{self.args.apply_patch}]")
        self.ld_api_client.update_custom_role(policy_key, json_patch)
        
        
    
        
    def _proc_apply_reverse_patch_policy(self):
        patch_file = self.args.reverse_patch
        self.logger.info(f"Loading patch file: {patch_file}")
        content = json.load(open(patch_file))

        if not self.policy_linter.is_valid_reverse_patch_file(content):
            raise ValueError(f"Invalid reverse patch file: {patch_file}. Make sure the patch file is valid and in the patches directory [{self.patch_dir}/*.reverse-patch] with the correct type [reverse-patch].")   

        policy_key = self.policy_linter.get_patch_key(content)
        json_patch = self.policy_linter.get_patch_jsonpatch(content)
        patch_type = self.policy_linter.get_patch_type(content)

        self.logger.debug(f"Patch policy key: {policy_key}")
        self.logger.debug(f"Patch json patch: {json_patch}")
        self.logger.debug(f"Patch type: {patch_type}")
        confirmation = input(f"\tLoaded Reverse Patch for Policy [{policy_key}]. Do you want to apply it? (y/N): ")
        
        if not confirmation or confirmation.lower() != 'y':
            # escape hatch
            self.logger.info("Patch operation cancelled by user")
            return 1

        self.logger.info(f"User confirmed, applying reverse patch for {policy_key} using [{self.args.reverse_patch}]")
        self.ld_api_client.update_custom_role(policy_key, json_patch)    


    def _proc_export_policies(self):
        return self.export_policies()

    def _proc_validate_policies(self) -> None:
        policies= None
        # Check if the all_policies_file.json exists, otherwise export policies
        if not os.path.exists(self.all_policies_file):
            self.logger.info(f"Policies file not found at [{self.all_policies_file}], exporting policies first.")
            policies = self._proc_export_policies()
        else:
            self.logger.info(f"Loading policies from {self.all_policies_file}")
            policies = json.load(open(self.all_policies_file))
    
        invalid_actions= self.policy_linter.validate (policies=policies, resource_actions=self.resource_actions)
        
        if invalid_actions:
            self.save_invalid_actions(invalid_actions)


    def save_invalid_actions(self, invalid_actions):
        

        if not os.path.exists(os.path.dirname(self.invalid_actions_file)):
            self.logger.info(f"Creating invalid actions directory at {self.invalid_actions_file}")
            os.makedirs(os.path.dirname(self.invalid_actions_file), exist_ok=True)

        with open(self.invalid_actions_file, 'w') as f:
            json.dump(invalid_actions, f, indent=2)

        self.logger.info(f"Successfully saved invalid actions to {self.invalid_actions_file}")


    def setup_logging(self, log_level=logging.INFO, log_file=None):
        """Configure logging for the application"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # Configure root logger
        # Configure root logger with console handler
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Clear existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(console_handler)
        
        
        file_handler = RotatingFileHandler(
            filename=self.log_file,
            maxBytes=2*1024*1024,  # 2mb
            backupCount=3,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)
        
      
        # Configure all related loggers
        loggers = [
            logging.getLogger('main'),
            logging.getLogger('policy_linter'),
            logging.getLogger('api_client')
        ]
        
        for logger in loggers:
            logger.setLevel(log_level)
        
        # Return logger for main module
        return logging

    def get_all_policies(self) -> None:
        return self.ld_api_client.get_custom_roles()

    
    def load_api_key_from_env(self) -> str:
        env_path = Path('.') / '.env'
        load_dotenv(env_path, override=True)
        api_key = os.getenv('LAUNCHDARKLY_API_KEY')
        if not api_key:
            raise ValueError(
                "LAUNCHDARKLY_API_KEY not found. Please create a .env file with your API key "
                "or set it as an environment variable."
            )
        self.logger.info("LD API key loaded successfully")
        self.logger.debug(f"LD API key: {api_key}")
        return api_key

    def _get_command_line_args(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="Policy Linter CLI tool")
        parser.add_argument("--apply-patch", "-ap",
                            help="Apply a patch file to a policy")
        parser.add_argument("--reverse-patch", "-arp",
                            help="Apply a reverse patch file to a policy")
        
        parser.add_argument("--validate", "-v", action="store_true",
                            help="Validate policies and generate a report of invalid actions in a json file. See --invalid-actiosn-file for output file.")
        parser.add_argument("--export", "-e", action="store_true",
                            help="Export policies to individual files")
        parser.add_argument("--debug", action="store_true",
                          help="Enable debug logging")
        parser.add_argument("--log-file",
                            help="Write logs to specified file in addition to console")
        parser.add_argument("--resource_actions",
                            help="Path to resource actions file",
                            default="config/resource_actions.json")
        parser.add_argument("--fix", "-f", 
                             action="store_true",
                            help="Fix invalid policies by removing invalid actions based on invalid_actions.json")
        # If no arguments provided, show help
        if len(sys.argv) == 1:
            parser.print_help()
            sys.exit(0)
            
        return parser.parse_args()

    def export_policies(self) -> None:  
         
        
        self.logger.info("Fetching policies from LaunchDarkly...")
        policies = self.get_all_policies()
        self.logger.info(f"Retrieved [{len(policies)}] custom roles.")
        
        all_policies_file = f"{self.export_dir}/all-policies.json"
        
        # Save individual policies
        for policy in policies:
            export_file = f"{self.export_dir}/{policy['key']}.json"
            
            PolicyLinter.save_policy(policy, export_file)
            self.logger.info(f"Saved policy {policy['key']} to {export_file}")
            
            # keep track of the hash for each policy in all-policies.json 
            # for easy lookup and comparison with validation
            # so we don't have to search through all the policies to find the one we want to validate.
            self.policy_linter.set_policy_hash(policy)
            
        # save all policies in one file
        PolicyLinter.save_policy(policies, all_policies_file)
        self.logger.info(f"Successfully saved combined policies to: {all_policies_file}")    

        self.logger.info(f"Individual policies saved to [{self.export_dir}] directory")
        return policies

    
    def _proc_fix_policies(self) -> None:
        self.logger.info("Fixing invalid actions in policies")
        
        if not os.path.exists(self.invalid_actions_file):
            raise ValueError(f"Invalid Actions file file not found at {self.invalid_actions_file}. Run with --validate first.")
        
        invalid_policies=None
        all_policies=None
        try:
            self.logger.info(f"Loading invalid policies from {self.invalid_actions_file}")
            invalid_policies = json.load(open(self.invalid_actions_file))
      
            self.logger.info(f"Loading policies from {self.all_policies_file}")
            all_policies = json.load(open(self.all_policies_file))

        except Exception as e:
            raise ValueError(f"Failed to load file(s): {str(e)}")
            
        invalid_policy_count = len(invalid_policies.keys())
        if (invalid_policy_count == 0):
            self.logger.info("No invalid actions found")
            return
        
        self.logger.info(f"Found {invalid_policy_count} policies with invalid actions.")
        self.logger.info(f"Fixing invalid policies")
        self.policy_linter.fix_invalid_policies( policies=all_policies, invalid_policies=invalid_policies)



def main() -> int:
    app = App()
    return app.run()

if __name__ == "__main__":
    exit(main()) 