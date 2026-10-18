# Deploy Script Implementation

## Overview

`infra/deploy.sh` replaces CI/CD. It builds the backend image for ARM64 and pushes it to ECR with an immutable git-based tag. It then registers a new task-definition revision based on the family's latest ACTIVE revision, sets the service to one task, and waits for the service to be stable. It also has two extra modes: `--restart` (pick up edited SSM values) and `--rollback <tag>`.

## Files to Modify/Create

- `infra/deploy.sh` (new, executable). It is the only deploy entry point.

## Implementation Guidelines

### CLI contract
```
infra/deploy.sh                 # build + push + deploy current checkout
infra/deploy.sh --restart       # same task definition, new task (re-reads SSM)
infra/deploy.sh --rollback <tag># deploy an image tag already in ECR
```
Environment: `AWS_PROFILE` defaults to `panoptico` and `AWS_REGION` to `us-east-1`. Both are exported so every `aws` call uses them.

### Flow (orientative)
```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export AWS_PROFILE="${AWS_PROFILE:-panoptico}" AWS_REGION="${AWS_REGION:-us-east-1}"

tf_output() { terraform -chdir="$ROOT/infra" output -raw "$1"; }
REPO="$(tf_output ecr_repository_url)"
CLUSTER="$(tf_output ecs_cluster_name)"
SERVICE="$(tf_output ecs_service_name)"
FAMILY="$(tf_output task_family)"
CONTAINER="$(tf_output container_name)"
LOG_GROUP="$(tf_output log_group_name)"
SSM_PREFIX="$(tf_output ssm_prefix)"

image_tag() {
  local sha; sha="$(git -C "$ROOT" rev-parse --short HEAD)"
  if [[ -n "$(git -C "$ROOT" status --porcelain -- backend)" ]]; then
    echo "${sha}-dirty-$(date +%s)"
  else
    echo "$sha"
  fi
}

build_and_push() {
  local tag="$1"
  aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO%%/*}"
  docker buildx build --platform linux/arm64 \
    -t "$REPO:$tag" -t "$REPO:latest" --push "$ROOT/backend"
}

register_revision() {
  local image="$1"
  aws ecs describe-task-definition --task-definition "$FAMILY" --query taskDefinition \
    | jq --arg image "$image" --arg name "$CONTAINER" '
        .containerDefinitions |= map(if .name == $name then .image = $image else . end)
        | del(.taskDefinitionArn, .revision, .status, .requiresAttributes,
              .compatibilities, .registeredAt, .registeredBy, .deregisteredAt)' \
    > "$TMP/taskdef.json"
  aws ecs register-task-definition --cli-input-json "file://$TMP/taskdef.json" \
    --query taskDefinition.taskDefinitionArn --output text
}

deploy() {
  local task_def_arn="$1"
  aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" \
    --task-definition "$task_def_arn" --desired-count 1 --force-new-deployment > /dev/null
  wait_stable
}

wait_stable() {
  if ! aws ecs wait services-stable --cluster "$CLUSTER" --services "$SERVICE"; then
    echo "Service did not stabilize. Recent logs:" >&2
    aws logs tail "$LOG_GROUP" --since 15m | tail -n 30 >&2
    exit 1
  fi
}

warn_unassigned_params() {
  aws ssm get-parameters-by-path --path "$SSM_PREFIX" --with-decryption \
    --query "Parameters[?Value=='assign_later'].Name" --output text | tr '\t' '\n' \
    | sed 's/^/  still assign_later: /' >&2 || true
}
```

The main dispatcher:
- **No args:**
  1. `tag=$(image_tag)`
  2. `build_and_push "$tag"`
  3. `deploy "$(register_revision "$REPO:$tag")"`
- **`--restart`:** run `update-service --force-new-deployment --desired-count 1` without a new revision, then `wait_stable`.
- **`--rollback <tag>`:** first run `aws ecr describe-images --repository-name "${REPO##*/}" --image-ids imageTag="$tag"`, and exit with an error message if it fails. Then run `deploy "$(register_revision "$REPO:$tag")"`.
- **Every mode:** call `warn_unassigned_params` at the start, and at the end print `Deployed <tag> → $(tf_output api_url)`.

Rules:
- Use `TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT`.
- Check that `aws`, `docker`, `jq` and `terraform` are installed (`command -v`) before doing any work, and print a clear message if any are missing.
- `aws ecs wait services-stable` polls for up to 10 minutes, which covers migrations and the 180s grace period.
- `register_revision` starts from the family's **latest** revision, not the service's current one. That way, Terraform changes such as a new SSM parameter in `secrets` are carried into the next deploy.

## Dependencies

- Local tooling: AWS CLI v2, Docker with buildx, `jq`, Terraform, and git.
- Terraform outputs from module 06.

## Integration Notes

- The service ignores `task_definition` and `desired_count` (module 06). After the first apply, the revisions and the 0 → 1 desired count are owned only by this script.
- The ECR lifecycle policy keeps the last 10 images. `--rollback` therefore works for roughly the last 9 deploys.
