#!/usr/bin/env python3
"""
LaunchDarkly Transformer Model Downloader

This script downloads transformer models from Hugging Face to a specified local path.
It's useful for users who want to download models locally first before using them
with the LaunchDarkly Policy Report Generator.

Usage:
    download_transformer.py [options]

Author: Benedicto Tan
"""

import argparse
import logging
from pathlib import Path
from sentence_transformers import SentenceTransformer
import sys

def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Download transformer models from Hugging Face",
        usage="%(prog)s [options]"
    )
    parser.add_argument("--model", 
                       default="all-MiniLM-L6-v2",
                       choices=["all-MiniLM-L6-v2", "all-mpnet-base-v2"],
                       help="Model to download from Hugging Face (default: all-MiniLM-L6-v2)")
    parser.add_argument("--output-path",
                       required=True,
                       help="Path where the model should be downloaded")
    parser.add_argument("--debug",
                       action="store_true",
                       help="Enable debug logging")
    return parser.parse_args()

def main() -> int:
    """Entry point for the command line tool"""
    args = parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    try:
        # Create output directory if it doesn't exist
        output_path = Path(args.output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Downloading model '{args.model}' to {output_path}")
        logger.info("This may take a few minutes depending on your internet connection...")
        
        # Download and save the model
        model = SentenceTransformer(args.model)
        model.save(str(output_path))
        
        logger.info(f"Successfully downloaded model to {output_path}")
        logger.info(f"You can now use this model with ld-policy-report.py using --model-path {output_path}")
        return 0
        
    except Exception as e:
        logger.error(f"Error downloading model: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main()) 