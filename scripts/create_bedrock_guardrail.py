#!/usr/bin/env python3
"""
Bedrock Guardrail Creation Script

Creates a minimal Bedrock guardrail with basic content filtering
to protect against harmful content in agent interactions.
"""

import logging
from argparse import ArgumentParser
from json import dumps
from boto3 import client as boto3_client
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_minimal_guardrail(region: str) -> str:
    """
    Create a minimal Bedrock guardrail with basic content filtering.
    
    Args:
        region (str): AWS region for the guardrail
        
    Returns:
        str: Guardrail ID of the created guardrail
    """
    bedrock_client = boto3_client("bedrock", region_name=region)
    
    guardrail_name = "AgentCore-Minimal-Guardrail"
    
    try:
        # Check if guardrail already exists
        response = bedrock_client.list_guardrails()
        for guardrail in response.get('guardrails', []):
            if guardrail['name'] == guardrail_name:
                logger.info(f"Guardrail {guardrail_name} already exists: {guardrail['id']}")
                return guardrail['id']
        
        # Create minimal guardrail with basic content filtering
        response = bedrock_client.create_guardrail(
            name=guardrail_name,
            description="Minimal guardrail for AgentCore agents with basic content filtering",
            contentPolicyConfig={
                'filtersConfig': [
                    {
                        'type': 'HATE',
                        'inputStrength': 'HIGH',
                        'outputStrength': 'HIGH'
                    },
                    {
                        'type': 'VIOLENCE',
                        'inputStrength': 'HIGH', 
                        'outputStrength': 'HIGH'
                    },
                    {
                        'type': 'SEXUAL',
                        'inputStrength': 'HIGH',
                        'outputStrength': 'HIGH'
                    }
                ]
            },
            blockedInputMessaging="I can't process that request due to content policy.",
            blockedOutputsMessaging="I can't provide that response due to content policy."
        )
        
        guardrail_id = response['guardrailId']
        logger.info(f"Created guardrail: {guardrail_name} (ID: {guardrail_id})")
        
        # Create version 1 to activate the guardrail
        try:
            version_response = bedrock_client.create_guardrail_version(
                guardrailIdentifier=guardrail_id,
                description="Version 1 - Active guardrail with HIGH strength filtering"
            )
            logger.info(f"Created guardrail version: {version_response['version']}")
        except ClientError as version_error:
            logger.warning(f"Could not create guardrail version: {version_error}")
            logger.info("Guardrail will use DRAFT version")
        
        # Save guardrail ID for deployment script
        with open("guardrail_id.txt", "w", encoding="utf-8") as f:
            f.write(guardrail_id)
            
        return guardrail_id
        
    except ClientError as e:
        logger.warning(f"Error creating guardrail: {e}")
        raise


def main():
    parser = ArgumentParser(description="Create minimal Bedrock guardrail")
    parser.add_argument("--region", required=True, help="AWS region")
    
    args = parser.parse_args()
    create_minimal_guardrail(args.region)


if __name__ == "__main__":
    main()