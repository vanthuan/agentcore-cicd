Contributing
============

This document explains how to set up local formatting and linting to match the CI for the `math_agent` project.

Prerequisites
- Python 3.11
- Docker (for local container testing)

Quick dev setup
1. Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies and dev tools:

```bash
pip install --upgrade pip
pip install -r app/requirements.txt
pip install pre-commit black isort flake8
```

Pre-commit (recommended)
1. Install the hooks:

```bash
pre-commit install
```

2. Run hooks against all files (one-off / CI parity):

```bash
pre-commit run --all-files
```

Manual formatting & lint commands
- Check (CI-style):

```bash
black --check app/math_agent
isort --check-only app/math_agent
flake8 app/math_agent --max-line-length=88 --extend-ignore=E203,W503
```

- Auto-format:

```bash
black app/math_agent
isort app/math_agent
```

CI notes
- The GitHub Actions workflow `.github/workflows/deploy-agentcore.yaml` runs the formatter/linter checks as part of the `validate` job. If CI fails with a message like "1 file would be reformatted", run the auto-format commands or `pre-commit run --all-files` and push the resulting commit.

Local Docker quick test
- Build:

```bash
docker build -t math-agent:local .
```

- Run:

```bash
docker run --rm -p 8080:8080 math-agent:local
```

Attribution
- This repository and CI are adapted from:
  - https://github.com/aws-samples/sample-bedrock-agentcore-runtime-cicd/tree/main/.github/workflows
  - https://github.com/RekhuGopal/githubactions-awsagentcore

(Please follow their guidance for IAM and deployment details.)
