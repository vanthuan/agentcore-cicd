#!/usr/bin/env python3
"""
Agent Deployment Script for AWS Bedrock AgentCore

This script handles the deployment of Strand agents to AWS Bedrock AgentCore Runtime.
It includes ARM64 architecture support, ECR repository management, and enhanced
security scanning configuration.

Usage:
    python deploy_agent.py --agent-name myagent --region us-west-2
                          --entrypoint agents/strands_agent.py
                          --requirements-file agents/requirements.txt
"""

import logging
from argparse import ArgumentParser, RawDescriptionHelpFormatter
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


def deploy_agent(agent_name, region, container_uri, auto_update=True):
    """
    Deploy agent to AWS Bedrock AgentCore Runtime using boto3 APIs.

    Args:
        agent_name (str): Name of the agent to deploy
        region (str): AWS region for deployment
        container_uri (str): ECR container URI
        auto_update (bool): Whether to update existing agents or fail on conflicts

    Returns:
        dict: Result containing agent ARN and ECR URI
    """
    # Read the IAM role ARN created by create_iam_role.py
    try:
        with open("role_arn.txt", "r", encoding="utf-8") as f:
            role_arn = f.read().strip()
    except FileNotFoundError:
        logger.error("Error: role_arn.txt not found")
        logger.error("Please run create_iam_role.py first to create the execution role")
        exit(1)

    logger.info(f"Deploying agent {agent_name}")
    logger.info("Platform: ARM64 (required by Bedrock AgentCore)")
    logger.info(f"Using execution role: {role_arn}")

    # Initialize AgentCore client
    agentcore_client = boto3_client("bedrock-agentcore-control", region_name=region)

    try:
        # Check if agent already exists - try direct approach first
        existing_agent = None
        agent_exists = False

        try:
            # Try to get agent directly if we can construct the ID pattern
            existing_agents = agentcore_client.list_agent_runtimes()
            logger.info(
                f"Found {len(existing_agents.get('agentRuntimes', []))} existing agents"
            )

            for agent in existing_agents.get("agentRuntimes", []):
                logger.info(f"Found agent: {agent['agentRuntimeName']}")
                if agent["agentRuntimeName"] == agent_name:
                    existing_agent = agent
                    agent_exists = True
                    break
        except Exception as e:
            logger.warning(f"Error listing agents: {e}")

        logger.info(
            f"Agent {agent_name} exists: {agent_exists}, auto_update: {auto_update}"
        )

        if agent_exists and not auto_update:
            logger.error(
                f"Agent {agent_name} already exists and auto-update is disabled"
            )
            exit(1)
        elif agent_exists and auto_update:
            logger.info(
                f"Updating existing agent {agent_name} with update_agent_runtime"
            )
            # Update existing agent runtime using agentRuntimeId
            response = agentcore_client.update_agent_runtime(
                agentRuntimeId=existing_agent["agentRuntimeId"],
                agentRuntimeArtifact={
                    "containerConfiguration": {"containerUri": container_uri}
                },
                networkConfiguration={"networkMode": "PUBLIC"},
                roleArn=role_arn,
            )
        else:
            # Try to create new agent runtime, handle conflict if agent actually exists
            try:
                response = agentcore_client.create_agent_runtime(
                    agentRuntimeName=agent_name,
                    agentRuntimeArtifact={
                        "containerConfiguration": {"containerUri": container_uri}
                    },
                    networkConfiguration={"networkMode": "PUBLIC"},
                    roleArn=role_arn,
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConflictException" and auto_update:
                    logger.info(
                        "Agent exists but wasn't detected in list. Attempting to find and update..."
                    )
                    # Agent exists but we couldn't find it in the list - try to find it another way
                    # For now, we'll need to handle this case differently
                    logger.error(
                        "Cannot update agent - unable to find agentRuntimeId. Please delete and recreate manually."
                    )
                    exit(1)
                else:
                    raise

        agent_arn = response["agentRuntimeArn"]
        agent_id = response["agentRuntimeId"]

        # Save deployment information
        with open("deployment_info.txt", "w", encoding="utf-8") as f:
            f.write(f"agent_arn={agent_arn}\n")
            f.write(f"agent_id={agent_id}\n")
            f.write(f"ecr_uri={container_uri}\n")

        logger.info("Agent deployed successfully!")
        logger.info(f"Agent ARN: {agent_arn}")
        logger.info(f"ECR URI: {container_uri}")

        return {"agent_arn": agent_arn, "agent_id": agent_id, "ecr_uri": container_uri}

    except ClientError as e:
        logger.error(f"AgentCore deployment failed: {e}")
        exit(1)


def main():
    """
    Main function to handle command-line arguments and initiate deployment.

    Parses command-line arguments and calls the deploy_agent function with
    the provided parameters.
    """
    parser = ArgumentParser(
        description="Deploy Strand Agent to AWS Bedrock AgentCore Runtime",
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy with auto-update (default behavior)
  python deploy_agent.py --agent-name myagent --region us-west-2 \\
                        --entrypoint agents/strands_agent.py \\
                        --requirements-file agents/requirements.txt

  # Explicitly enable auto-update
  python deploy_agent.py --agent-name myagent --region us-west-2 \\
                        --entrypoint agents/strands_agent.py \\
                        --requirements-file agents/requirements.txt \\
                        --auto-update-on-conflict

  # Fail if agent already exists (no auto-update)
  python deploy_agent.py --agent-name myagent --region us-west-2 \\
                        --entrypoint agents/strands_agent.py \\
                        --requirements-file agents/requirements.txt \\
                        --no-auto-update
        """,
    )

    parser.add_argument(
        "--agent-name", required=True, help="Name of the agent to deploy"
    )
    parser.add_argument(
        "--region", required=True, help="AWS region for deployment (e.g., us-west-2)"
    )
    parser.add_argument(
        "--container-uri", required=True, help="ECR container URI for the agent"
    )
    parser.add_argument(
        "--auto-update-on-conflict",
        action="store_true",
        default=True,
        help="Update existing agents instead of failing on conflicts (default: True)",
    )
    parser.add_argument(
        "--no-auto-update",
        dest="auto_update_on_conflict",
        action="store_false",
        help="Fail if agent already exists instead of updating",
    )

    args = parser.parse_args()

    # Deploy the agent with the provided parameters
    deploy_agent(
        args.agent_name, args.region, args.container_uri, args.auto_update_on_conflict
    )


if __name__ == "__main__":
    main()
