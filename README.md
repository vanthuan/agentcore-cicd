**AgentCore CI/CD (math_agent)**

This folder contains a small example to build and deploy a containerized agent to AWS Bedrock AgentCore Runtime. The workflow, scripts, and patterns in this directory are inherited from the following reference projects:

- https://github.com/aws-samples/sample-bedrock-agentcore-runtime-cicd/tree/main/.github/workflows
- https://github.com/RekhuGopal/githubactions-awsagentcore

**Contents**
- **`Dockerfile`**: Builds the `math_agent` container image.
- **`.github/workflows/deploy-agentcore.yaml`**: GitHub Actions workflow used to validate, build, and deploy the image to ECR and AgentCore.
- **`app/math_agent/`**: Agent code used by the runtime.

**Quickstart**
- Build locally:

```
docker build -t math-agent:local .
```

- Run locally (port 8080):

```
docker run --rm -p 8080:8080 math-agent:local
```

- CI: push to the repository and let the Actions workflow `.github/workflows/deploy-agentcore.yaml` run.

**Notes & recommendations**
- Keep `requirements.txt` up to date; workflows install dependencies to run format/lint checks and to build the image.
- Use `.dockerignore` to exclude large files and secrets from the build context.
- This code was adapted from the upstream examples above — check their repos for detailed IAM and deployment guidance.
