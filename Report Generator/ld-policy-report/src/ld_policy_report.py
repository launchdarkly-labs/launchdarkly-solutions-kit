#!/usr/bin/env python3
"""
LaunchDarkly Policy Report Generator

This script is the main entry point for the LaunchDarkly Policy Report Generator.
It analyzes LaunchDarkly custom role policies to identify similarities, track role
assignments, and visualize team access patterns.

The tool fetches data from the LaunchDarkly API, analyzes policy similarities using
semantic embeddings, and generates an interactive HTML report.

Usage:
    ld-policy-report [options]

Author: Benedicto Tan
"""

import sys
import json
from datetime import datetime
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv
from chromadb.utils import embedding_functions
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional
from sentence_transformers import SentenceTransformer

from launchdarkly_api_client import LaunchDarklyAPI
from launchdarkly_policy_similarity import LaunchDarklyPolicySimilarityService, validate_policies
from launchdarkly_reports import SimilarityReport
from policy_linter import PolicyLinter

class NoProgressEmbeddingFunction(embedding_functions.SentenceTransformerEmbeddingFunction):
    """
    Custom embedding function that disables progress bars during encoding.
    
    This class extends the SentenceTransformerEmbeddingFunction from ChromaDB
    to provide a cleaner console output by disabling progress bars when
    generating embeddings.
    
    Attributes:
        model: The sentence transformer model used for encoding
        path: The path to the local sentence transformer model to use
    """
    def __init__(self, model_name: str = None, path: str = None):
        """
        Initialize the embedding function with a specific model.
        
        Args:
            model_name (str): Name of the sentence transformer model to use from Hugging Face
            path (str): Path to the local sentence transformer model to use
        """
        self.logger = logging.getLogger(__name__)
        if path:
            self.model_name = path
            self.logger.info(f"Loading pretrained SentenceTransformer model from local path: {path}")
        elif model_name:
            self.model_name = model_name
            self.logger.info(f"Loading pretrained SentenceTransformer model from Hugging Face: {model_name}")
        else:
            raise ValueError("Either model_name or path must be provided.")
        super().__init__(model_name=self.model_name)
        self.model = SentenceTransformer(self.model_name)
        
    def __call__(self, texts):
        """
        Generate embeddings for the provided texts without showing progress bars.
        
        Args:
            texts: List of texts to encode
            
        Returns:
            List of embeddings for the input texts
        """
        self.logger.debug(f"Generating embeddings for {len(texts)} texts")
        return self.model.encode(texts, show_progress_bar=False, batch_size=32)

class LaunchDarklyPolicyReport:
    """
    Main class for generating LaunchDarkly policy reports.
    
    This class orchestrates the entire process of fetching data from LaunchDarkly,
    analyzing policy similarities, and generating the final HTML report.
    
    Attributes:
        args: Command line arguments
        api_key: LaunchDarkly API key
        embedding_func: Function for generating embeddings
        logger: Logger instance for this class
    """
    
    def __init__(self):
       
        self.args = self.parse_args()
       
              
        self.log_level = logging.DEBUG if self.args.debug else logging.INFO
        self.log_file = "report.log" 
        self.loggers = self.setup_logging(log_level=self.log_level, log_file=self.log_file)
        self.logger= self.loggers.getLogger('main')
        
        self.api_key = self.load_environment()

        self.embedding_func = NoProgressEmbeddingFunction(
            path=self.args.model_path
        )



    
    def setup_logging(self, log_level=logging.INFO, log_file=None):
        """Configure logging for the application"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
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
    
    def parse_args(self) -> argparse.Namespace:
        """
        Parse command line arguments.
        
        This method sets up the argument parser and defines all command line options
        for the LaunchDarkly Policy Report Generator.
        
        Returns:
            argparse.Namespace: Parsed command line arguments
            
        Command Line Options:
            --force-refresh: Force refresh of cached data and re-embed policies
            --policies-output: Output file for policy similarities
            --report-output: Output file for policy report
            --cache-ttl: Cache time-to-live in hours
            --cache-dir: Directory to store cache files
            --persist: Use persistent storage for embeddings
            --embeddings: Path to store persistent embeddings
            --collection: Name of the ChromaDB collection
            --model-path: Path to local transformer model
            --min-similarity: Minimum similarity threshold
            --max-results: Maximum number of similar policies to return
            --validate-actions: Validate policy actions against official LaunchDarkly resource actions
            --resource-actions-file: Path to JSON file containing LaunchDarkly resource actions
            --invalid-actions-output: Output file for invalid actions
            --query-file: Path to JSON file containing query parameters
            --debug: Enable debug logging
        """
        parser = argparse.ArgumentParser(
            description="LaunchDarkly Feature Flag Cleanup Report Generator",
            usage="%(prog)s [options]"
        )
        parser.add_argument("--force-refresh", action="store_true", 
                          help="Force refresh of cached data and re-embed policies")
        parser.add_argument("--policies-output", default="./reports/policies.json",
                          help="Output file for policy similarities (default: policies.json)")
        parser.add_argument("--report-output", default="./reports/policy_report.html",
                          help="Output file for policy report (default: policy_report.html)")
        parser.add_argument("--cache-ttl", type=int, default=24,
                        help="Cache time-to-live in hours (default: 24)")
        parser.add_argument("--cache-dir", default="cache",
                        help="Directory to store cache files (default: cache)")
        parser.add_argument("--persist", type=bool, default=True,
                          help="Use persistent storage for embeddings (default: True)")
        parser.add_argument("--embeddings", default="./embeddings",
                          help="Path to store persistent embeddings (default: ./embeddings)")
        parser.add_argument("--collection", default="launchdarkly_policies",
                          help="Name of the ChromaDB collection (default: launchdarkly_policies)")
        parser.add_argument("--model-path", default="./sentence_transformers/all-MiniLM-L6-v2",
                          help="Path to local transformer model")
        parser.add_argument("--min-similarity", type=float, default=0.5,
                          help="Minimum similarity threshold (default: 0.5)")
        parser.add_argument("--max-results", type=int, default=3,
                          help="Maximum number of similar policies to return (default: 3)")
        parser.add_argument("--validate-actions", action="store_true",
                          help="Validate policy actions against official LaunchDarkly resource actions")
        parser.add_argument("--resource-actions-file", 
                            help="Path to JSON file containing LaunchDarkly resource actions",
                            default="./config/resource_actions.json" )
        parser.add_argument("--invalid-actions-output", default="./reports/invalid_actions.json",
                          help="Output file for invalid actions (default: ./reports/invalid_actions.json)")
        parser.add_argument("--debug", action="store_true",
                          help="Enable debug logging")
        parser.add_argument("--query-file", type=str,
                          help="Run query against the collection using JSON policy file.")
        return parser.parse_args()


    def load_environment(self) -> str:
      
    # Try to load from .env in current directory
        env_path = Path('.') / '.env'
        if env_path.exists():
                    load_dotenv(env_path, override=True)
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

    def run(self) -> int:
        """
        Main execution method for the LaunchDarkly Policy Report Generator.
        
        This method:
        1. Initializes the LaunchDarkly API client
        2. Fetches or loads cached data
        3. Validates policy actions if requested
        4. Processes policy similarities
        5. Generates the HTML report
        
        If --validate-actions is specified, it will check all policy actions against
        the official LaunchDarkly resource actions and save invalid actions to a JSON file.
        
        If --query-file is specified, it will load parameters from the specified JSON file.
        Command line arguments will override any settings in the query file.
        
        Returns:
            int: 0 for success, 1 for failure
        """
        try:
            ld_api = LaunchDarklyAPI(
                        self.api_key, 
                        cache_ttl=self.args.cache_ttl,
                        cache_dir=self.args.cache_dir
            )
            
        # Handle cache purging for force refresh
            if self.args.force_refresh:
                self.logger.info("Purging eval cache...")
                ld_api.purge_eval_cache()

                if os.path.exists(self.args.policies_output):
                    self.logger.info(f"Removing existing policies output file: {self.args.policies_output}")
                    os.remove(self.args.policies_output)
            
            
            cached_data = None
            is_cached_data = False
            data= None
            # Check if we can use cached data
            if not self.args.force_refresh:
                cached_data = ld_api.load_cached_data()
                data = cached_data
                if cached_data:
                    self.logger.info(f"Returning cached data total roles= {len(cached_data['roles'])}")
                    is_cached_data = True
                      
            if not cached_data:
                self.logger.info("Fetching roles...")
                data = ld_api.fetch_and_cache_data()
                self.logger.info(f"Fetched {len(data['roles'])} roles")
            if not data:
                self.logger.error("Failed to fetch custom roles")
                return 1
            
            invalid_actions = None  
            # Validate policy actions if requested
            
            self.logger.info("Validating policy actions...")
            # invalid_actions = validate_policies(data, self.args.resource_actions_file)
            policy_linter = PolicyLinter(logger=self.loggers.getLogger('policy_linter'))
            resource_actions = json.load(open(self.args.resource_actions_file))
            invalid_actions= policy_linter.validate(data.get('roles', []), resource_actions)
            

            if invalid_actions:
                self.logger.info(f"Found {len(invalid_actions)} roles with invalid actions")
                
                # Create directory for output file if it doesn't exist
                os.makedirs(os.path.dirname(self.args.invalid_actions_output), exist_ok=True)
                
                # Write invalid actions to file
                with open(self.args.invalid_actions_output, 'w') as f:
                    json.dump(invalid_actions, f, indent=2)
                
                self.logger.info(f"Invalid actions saved to {self.args.invalid_actions_output}")
            else:
                self.logger.info("No invalid actions found in policies")

            ld_similarity_service = LaunchDarklyPolicySimilarityService(
                embedding_func=self.embedding_func,
                collection_name=self.args.collection,
                force=self.args.force_refresh,
                persist=self.args.persist,
                path=self.args.embeddings,
                output_file=self.args.policies_output
            )

            
            if not is_cached_data:
                ld_similarity_service.update_collection(data["roles"])

            if self.args.query_file:
                self.logger.info(f"Running query: [{self.args.query_file}]")
                query_policy = None
                with open(self.args.query_file, 'r') as f:
                    query_policy = json.load(f)

                policies = ld_similarity_service.run_query_standalone(query_policy, self.args.max_results, self.args.min_similarity)   
                
                policy_len = len(policies)
                self.logger.info(f"Found {policy_len} matching policies.")
                if policy_len == 0:
                    self.logger.info(f"No policies found. Try adjusting the min similarity to get more results.")
                else:
                    self.logger.info(f"Policies: minimum similarity: {self.args.min_similarity}, maximum results: {self.args.max_results}\n{json.dumps(policies, indent=2)}")
                    

                return 0;
        
            # Find similar policies for each role
            policies = ld_similarity_service.process_collection(data, self.args.max_results, self.args.min_similarity)

            self.logger.info(f"Policies saved to {self.args.policies_output}")
            report = SimilarityReport(output_file=self.args.report_output, ldc_cache_data=data, policy_data=policies, min_similarity=self.args.min_similarity, invalid_actions=invalid_actions)
            self.logger.info("Generating report...")
            report.generate_report()
            self.logger.info(f"Report saved to {self.args.report_output}")  
            
            return 0
            
        except Exception as e:
            self.logger.error(f"\nError: {str(e)}")
            return 1
        

def main() -> int:
    """Entry point for the command line tool"""
    report = LaunchDarklyPolicyReport()
    return report.run()

if __name__ == "__main__":
    exit(main()) 