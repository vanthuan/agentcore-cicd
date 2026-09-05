#!/usr/bin/env python3
"""
IAM Role Creation Script for Amazon Bedrock AgentCore
This script sets up AWS Identity and Access Management (IAM) roles for Amazon Bedrock AgentCore agents. The roles provide access to Amazon Bedrock models, Amazon Elastic Container Registry (Amazon ECR), and Amazon CloudWatch.

Usage:
    python create_iam_role.py --agent-name myagent --region us-west-2

The script creates a role named "AgentCoreRole-{sanitized_agent_name}" and saves
the role ARN to "role_arn.txt" for use by other deployment scripts.
"""

import logging
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from json import dumps
from re import sub
from sys import exit

from boto3 import client as boto3_client
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def sanitize_agent_name(agent_name: str) -> str:
    """
    Sanitize agent name to meet AWS AgentCore naming requirements.

    AWS AgentCore has specific naming constraints:
    - Must start with a letter
    - Can only contain letters, numbers, and underscores
    - Maximum length of 48 characters

    Args:
        agent_name (str): Original agent name

    Returns:
        str: Sanitized agent name that meets AWS requirements
    """
    # Replace invalid characters with underscores
    sanitized = sub(r"[^a-zA-Z0-9_]", "_", agent_name)

    # Ensure name starts with a letter (prepend 'agent_' if needed)
    if not sanitized[0].isalpha():
        sanitized = "agent_" + sanitized

    # Truncate to maximum allowed length
    return sanitized[:48] if len(sanitized) > 48 else sanitized


def create_or_update_role(agent_name: str, region: str) -> str:
    """
    Create or update IAM execution role for the AgentCore agent.

    This function creates a comprehensive IAM role with all necessary permissions
    for Bedrock AgentCore operations, including model access, container operations,
    logging, and tracing capabilities.

    Args:
        agent_name (str): Name of the agent (will be sanitized)
        region (str): AWS region for the role

    Returns:
        str: ARN of the created or updated IAM role

    Raises:
        SystemExit: If role creation fails
    """
    # Sanitize the agent name for AWS compliance
    agent_name = sanitize_agent_name(agent_name)
    iam_client = boto3_client("iam", region_name=region)
    role_name = f"AgentCoreRole-{agent_name}"

    # Trust policy: allows Bedrock AgentCore service to assume this role
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    # Permissions policy: defines what the agent can do when running
    permissions_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                # Bedrock model access permissions
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",  # Invoke foundation models
                    "bedrock:InvokeModelWithResponseStream",  # Streaming model invocation
                    "bedrock:Converse",  # Converse API access
                    "bedrock:ConverseStream",  # Streaming converse API
                    "bedrock:CreateGuardrail",  # Create guardrails
                    "bedrock:CreateGuardrailVersion",  # Create guardrail versions
                    "bedrock:GetGuardrail",  # Get guardrail details
                    "bedrock:ListGuardrails",  # List available guardrails
                    "bedrock-agentcore:ListAgentRuntimes",  # List agent runtimes
                    "bedrock-agentcore:ListAgentRuntimeVersions",  # List runtime versions
                    "bedrock-agentcore:DeleteAgentRuntimeVersion",  # Delete runtime versions
                ],
                "Resource": [
                    # Claude Sonnet 4 models (US region specific)
                    "arn:aws:bedrock:*::foundation-model/us.anthropic.claude-sonnet-4-*",
                    # General Claude models (all regions)
                    "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
                    # Claude inference profiles (US region specific)
                    "arn:aws:bedrock:*:*:inference-profile/us.anthropic.claude-sonnet-4-*",
                    # General Claude inference profiles
                    "arn:aws:bedrock:*:*:inference-profile/anthropic.claude-*",
                ],
            },
            {
                # ECR permissions for container image access
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",  # Get ECR login token
                    "ecr:BatchCheckLayerAvailability",  # Check if image layers exist
                    "ecr:GetDownloadUrlForLayer",  # Get download URLs for layers
                    "ecr:BatchGetImage",  # Download container images
                ],
                "Resource": "*",  # ECR operations require wildcard resource
            },
            {
                # CloudWatch Logs permissions for agent logging
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",  # Create log groups for agent
                    "logs:CreateLogStream",  # Create log streams within groups
                    "logs:PutLogEvents",  # Write log events
                ],
                "Resource": "arn:aws:logs:*:*:*",  # All CloudWatch Logs resources
            },
        ],
    }

    try:
        # Check if role already exists
        response = iam_client.get_role(RoleName=role_name)
        role_arn = response["Role"]["Arn"]
        logger.info(f"Role {role_name} already exists, updating policies...")

        # Update the role policy to ensure it has the latest permissions
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"AgentCorePolicy-{agent_name}",
            PolicyDocument=dumps(permissions_policy),
        )
        logger.info(f"Updated permissions for role {role_name}")

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            # Role doesn't exist, create it
            logger.info(f"Creating new IAM role: {role_name}")
            response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=dumps(trust_policy),
                Description=f"Execution role for AgentCore Runtime {agent_name}",
            )
            role_arn = response["Role"]["Arn"]
            logger.info(f"Created role {role_name}")

            # Attach the permissions policy to the new role
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"AgentCorePolicy-{agent_name}",
                PolicyDocument=dumps(permissions_policy),
            )
            logger.info(f"Added permissions to role {role_name}")
        else:
            logger.error(f"Error creating role: {e}")
            exit(1)

    # Save role ARN to file for use by deployment scripts
    with open("role_arn.txt", "w", encoding="utf-8") as f:
        f.write(role_arn)

    logger.info(f"\nRole ARN: {role_arn}")
    logger.info("\nRole includes permissions for:")
    logger.info("Bedrock foundation models (Claude)")
    logger.info("Bedrock inference profiles (Claude)")
    logger.info("ECR container access")
    logger.info("CloudWatch logging")

    return role_arn


def main():
    """
    Main function to handle command-line arguments and create IAM role.

    Parses command-line arguments and calls create_or_update_role with
    the provided agent name and region.
    """
    parser = ArgumentParser(
        description="Create IAM execution role for Bedrock AgentCore agent",
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_iam_role.py --agent-name myagent --region us-west-2
  python create_iam_role.py --agent-name "My Custom Agent" --region eu-west-1

The script will:
1. Validate agent names based on AWS naming rules
2. Set up the AWS Identity and Access Management (IAM) role with required permissions
        """,
    )

    parser.add_argument(
        "--agent-name",
        required=True,
        help="Name of the agent (will be sanitized for AWS)",
    )
    parser.add_argument(
        "--region", required=True, help="AWS region for the role (e.g., us-west-2)"
    )

    args = parser.parse_args()

    # Create or update the IAM role
    create_or_update_role(args.agent_name, args.region)


if __name__ == "__main__":
    main()
