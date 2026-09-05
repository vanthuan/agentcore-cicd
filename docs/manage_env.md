# Engineering Guide: Secure Environment Management with Docker Buildx, GitHub Actions, and Terraform

This guide establishes the architectural standards, technical best practices, and security safeguards for fetching configurations from **AWS Secrets Manager** and securely injecting them into a **Docker Buildx** compilation or runtime pipeline orchestrated via **Terraform**.

---

## 🏗️ Core Architecture Overview

[Developer updates env] ──> [Pushes via AWS CLI or Console] ──> [AWS Secrets Manager]│▼[Git Push / PR] ───────────> [GitHub Actions Buildx Engine] ◄───────────┘
1. **Infrastructure Provisioning:** Terraform handles the creation of the AWS Secrets Manager container and configures GitHub Actions IAM OIDC permissions once.
2. **Secrets Single Source of Truth:** Live application credentials reside strictly inside AWS Secrets Manager. They are kept entirely out of Git history and Terraform state files.
3. **Continuous Integration:** GitHub Actions utilizes official AWS actions to capture a snapshot of the secrets at build time and maps them to Buildx secret engines without needing a manual Terraform step.

---

## 🎯 Primary Use Cases

### Use Case A: Build-Time Compilation (Frontend Frameworks)
*   **App Types:** Next.js, Vite, Nuxt, React, or statically compiled binaries.
*   **The Problem:** These frameworks hardcode environmental variables directly into compiled browser bundles or perform schema validation during the `build` phase. The file must exist when the build runs.
*   **The Solution:** Generate a localized, temporary environment file on the runner, stream it to Buildx as a secret mount, and destroy it instantly.

### Use Case B: Container Runtime Isolation (Backend Components)
*   **App Types:** Node.js Express APIs, Python (FastAPI/Flask), Go, Java.
*   **The Problem:** Storing structural secrets permanently inside production image layers violates basic security compliance.
*   **The Solution:** Eradicate physical `.env` files within production stages. Use third-party environment loaders (like `loaddotenv` or `python-dotenv`) to safely pick up native environment variables injected directly into the running OS kernel by Docker Compose or Kubernetes at execution time.

---

## 🛡️ The "Do's" & "Don'ts" Checklist

### ❌ The Strict "Don'ts"
*   **NEVER burn secrets using `ENV` or `ARG` instructions:** Doing so writes plaintext credentials permanently into the Docker image metadata. Anyone with read access to the image can run `docker history` to extract them.
*   **NEVER pipe multi-line blocks with raw shell echos:** Do not run `echo "${{ env.RAW_ENV_DATA }}" > .env`. Standard shell string expansion can inadvertently leak structured data into workflow execution logs or cause compilation crashes if variables contain special characters (like backticks or `$`).
*   **NEVER give GitHub Actions write-back permissions:** The pipeline must maintain a strict, one-way read structure. GitHub Actions roles must never be granted `secretsmanager:PutSecretValue` or `update-secret` capabilities.

###  The Mandatory "Do's"
*   **DO use single-quoted Heredocs for temporary file assembly:** This prevents shell parsing and log leakage on the runner instance:
    ```bash
    cat << 'EOF' > .env.tmp
    \${{ env.RAW_ENV_DATA }}
    EOF
    ```
*   **DO implement fail-safe cleanups:** Always encapsulate runner file deletions in a step configured with `if: always()` to guarantee clean workspace teardowns even if a Buildx execution crashes mid-process.
*   **DO track schemas, not credentials:** Keep structural configuration keys (like `DB_HOST`, `LOG_LEVEL`) inside repository variables or Terraform code maps while populating the production values exclusively within AWS.

---

## 💻 Code Blueprints & Implementations

### 1. The Terraform Manifest (Safe Key/Value Configuration)
To prevent your live production passwords from spilling into plaintext `terraform.tfstate` files, use the **"Create but don't overwrite"** pattern by tracking value modifications with a `lifecycle` block.

```hcl
resource "aws_secretsmanager_secret" "secure_app_secrets" {
  name        = "prod/app-env"
  description = "Application configuration state container"
}

resource "aws_secretsmanager_secret_version" "secure_app_secrets_val" {
  secret_id     = aws_secretsmanager_secret.secure_app_secrets.id
  secret_string = "{\"DB_HOST\":\"initial-placeholder-value\"}"

  # Prevents Terraform from wiping or overriding developer local terminal updates
  lifecycle {
    ignore_changes = [
      secret_string
    ]
  }
}
```

### 2. GitHub Actions Workflow Structure (Buildx Deployment)
This step captures the plaintext raw multi-line `.env` block from AWS Secrets Manager, routes it through Buildx as a tracked secret mount object, and enforces an automatic workspace scrubbing routine.

```yaml
- name: Fetch Raw .env String
  uses: aws-actions/aws-secretsmanager-get-secrets@v3
  with:
    secret-ids: |
      prod/env-file, RAW_ENV_DATA

- name: Create Temporary .env File
  run: |
    cat << 'EOF' > .env.tmp
    \${{ env.RAW_ENV_DATA }}
    EOF

- name: Build with Buildx
  run: |
    docker buildx build \
      --secret id=env_file,src=.env.tmp \
      --target production \
      -t my-app-service:latest .

- name: Cleanup Temporary Runner File
  if: always()
  run: rm -f .env.tmp
```

### 3. Production Dockerfile Compilation (Secret Mounting)
Inside the `Dockerfile`, mount the injected Buildx secret explicitly onto the layer that processes application assembly. The resulting file disappears automatically as soon as that target execution finishes.

```dockerfile
# Stage 1: Build & Compilation environment
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# Mount the secret file into the exact path 'loaddotenv' or your bundler requires
RUN --mount=type=secret,id=env_file,dst=.env \
    npm run build

# Stage 2: Final Production Environment
FROM node:20-alpine
WORKDIR /app

# Only copy compiled artifacts over; the source code and .env are left behind completely
COPY --from=builder /app/dist ./dist
COPY package*.json ./
RUN npm prune --production

CMD ["node", "dist/index.js"]
```

---

## ⚙️ Terminal Shortcuts for Developers

Developers can skip the AWS console and push local configuration updates to AWS Secrets Manager using the AWS CLI:

*   **To sync structured Key/Value pairs:**
    ```bash
    aws secretsmanager update-secret --secret-id prod/app-env --secret-string '{"DB_HOST":"db.prod.internal","API_KEY":"xyz123"}'
    ```
*   **To sync an entire localized `.env` file string directly:**
    ```bash
    aws secretsmanager update-secret --secret-id prod/env-file --secret-string file://.env.production
    ```
