#!/usr/bin/env python3
"""
ECR Image Cleanup Script

This script manages ECR repository storage by removing old container images
while preserving the most recent ones. It helps control storage costs and
maintains repository hygiene by automatically cleaning up outdated images.

Key Features:
- Automatic detection of AgentCore-related repositories
- Configurable retention count for recent images
- Safe deletion based on image push timestamps
- Comprehensive error handling for repository operations

Usage:
    python cleanup_ecr.py --region us-west-2 --keep-count 9

The script will:
1. List all ECR repositories in the region
2. Filter for AgentCore-related repositories
3. Sort images by push timestamp (newest first)
4. Delete images beyond the keep-count threshold
"""

import logging
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from boto3 import client as boto3_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def cleanup_ecr_images(region, keep_count=9, repository_name=None):
    """
    Clean up old ECR images while preserving recent ones.
    
    This function identifies AgentCore-related ECR repositories and removes
    older container images to manage storage costs. It preserves the most
    recent images based on the keep_count parameter.
    
    Args:
        region (str): AWS region containing the ECR repositories
        keep_count (int): Number of recent images to preserve (default: 9)
        
    Returns:
        None
        
    Note:
        Only processes repositories with 'agentcore' in the name for safety.
    """
    # Initialize ECR client for the specified region
    ecr_client = boto3_client("ecr", region_name=region)
    
    # Check if specific repository exists
    try:
        ecr_client.describe_repositories(repositoryNames=[repository_name])
        logger.info(f"Processing repository: {repository_name}")
        process_repository(ecr_client, repository_name, keep_count)
    except ecr_client.exceptions.RepositoryNotFoundException:
        logger.info(f"Repository {repository_name} not found, skipping cleanup")


def process_repository(ecr_client, repo_name, keep_count):
    """
    Process a single ECR repository for image cleanup.
    
    Args:
        ecr_client: Boto3 ECR client
        repo_name (str): Repository name to process
        keep_count (int): Number of recent images to preserve
    """
    try:
        # Get all images in the repository
        images = ecr_client.describe_images(repositoryName=repo_name)
        
        # Sort images by push timestamp (newest first)
        sorted_images = sorted(
            images["imageDetails"],
            key=lambda x: x.get("imagePushedAt", 0),  # Use 0 if no timestamp
            reverse=True  # Newest first
        )
        
        # Identify images to delete (beyond keep_count)
        images_to_delete = sorted_images[keep_count:]
        
        if images_to_delete:
            # Prepare image identifiers for batch deletion
            image_ids = []
            for image in images_to_delete:
                if "imageDigest" in image:
                    image_ids.append({"imageDigest": image["imageDigest"]})
            
            if image_ids:
                # Perform batch deletion
                ecr_client.batch_delete_image(
                    repositoryName=repo_name,
                    imageIds=image_ids
                )
                logger.info(f"Deleted {len(image_ids)} old images from {repo_name}")
                logger.info(f"Kept {min(len(sorted_images), keep_count)} recent images")
        else:
            logger.info(f"Repository {repo_name} has {len(sorted_images)} images (within keep limit)")
            
    except Exception as e:
        logger.error(f"Error processing repository {repo_name}: {e}")


def main():
    """
    Main function to handle command-line arguments and initiate cleanup.
    
    Parses command-line arguments and calls cleanup_ecr_images with
    the specified region and retention count.
    """
    parser = ArgumentParser(
        description="Clean up old ECR container images for AgentCore repositories",
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cleanup_ecr.py --region us-west-2
  python cleanup_ecr.py --region us-west-2 --keep-count 10

Safety Features:
- Only processes repositories with 'agentcore' in the name
- Preserves the most recent images based on push timestamp
- Uses batch operations for efficient deletion
        """
    )
    
    parser.add_argument("--region", required=True,
                       help="AWS region containing ECR repositories")
    parser.add_argument("--keep-count", type=int, default=9,
                       help="Number of recent images to keep (default: 9)")
    parser.add_argument("--repository-name", required=True,
                       help="ECR repository name to clean up")
    
    args = parser.parse_args()
    
    logger.info(f"Starting ECR cleanup in {args.region}")
    logger.info(f"Keeping {args.keep_count} most recent images per repository")
    
    # Perform the cleanup operation
    cleanup_ecr_images(args.region, args.keep_count, args.repository_name)
    
    logger.info("ECR cleanup completed!")


if __name__ == "__main__":
    main()