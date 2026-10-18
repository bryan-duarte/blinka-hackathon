#!/usr/bin/env bash
set -euo pipefail

readonly USAGE="Usage: infra/deploy.sh [--restart | --rollback <tag>]"
readonly REQUIRED_TOOLS=(aws docker git jq terraform)
readonly FAILURE_LOG_WINDOW="15m"
readonly FAILURE_LOG_LINES=30
readonly UNASSIGNED_VALUE="assign_later"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
readonly ROOT
export AWS_PROFILE="${AWS_PROFILE:-panoptico}"
export AWS_REGION="${AWS_REGION:-us-east-1}"

fail() {
  echo "error: $*" >&2
  exit 1
}

require_tools() {
  local missing=()
  local tool
  for tool in "${REQUIRED_TOOLS[@]}"; do
    command -v "$tool" > /dev/null || missing+=("$tool")
  done
  if ((${#missing[@]} > 0)); then
    fail "missing required tools: ${missing[*]}"
  fi
}

terraform_output() {
  terraform -chdir="$ROOT/infra" output -raw "$1"
}

image_tag() {
  local sha
  sha="$(git -C "$ROOT" rev-parse --short HEAD)"
  local backend_has_uncommitted_changes
  backend_has_uncommitted_changes="$(git -C "$ROOT" status --porcelain -- backend)"
  if [[ -n "$backend_has_uncommitted_changes" ]]; then
    echo "${sha}-dirty-$(date +%s)"
  else
    echo "$sha"
  fi
}

warn_unassigned_params() {
  local unassigned_names
  unassigned_names="$(aws ssm get-parameters-by-path --path "$SSM_PREFIX" --recursive --with-decryption \
    --query "Parameters[?starts_with(Value, '${UNASSIGNED_VALUE}')].Name" --output text)"
  if [[ -n "$unassigned_names" ]]; then
    tr '\t' '\n' <<< "$unassigned_names" | sed "s/^/  still ${UNASSIGNED_VALUE}: /" >&2
  fi
}

build_and_push() {
  local tag="$1"
  aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO%%/*}"
  docker buildx build --platform linux/arm64 \
    -t "$REPO:$tag" -t "$REPO:latest" --push "$ROOT/backend"
}

require_image_exists() {
  local tag="$1"
  aws ecr describe-images --repository-name "${REPO##*/}" --image-ids imageTag="$tag" > /dev/null 2>&1 \
    || fail "image tag '$tag' is not in ECR repository ${REPO##*/}"
}

register_revision() {
  local image="$1"
  local task_definition_file="$TMP/task-definition.json"
  aws ecs describe-task-definition --task-definition "$FAMILY" --query taskDefinition \
    | jq --arg image "$image" --arg name "$CONTAINER" '
        .containerDefinitions |= map(if .name == $name then .image = $image else . end)
        | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities,
              .registeredAt, .registeredBy, .deregisteredAt, .enableFaultInjection)' \
    > "$task_definition_file"
  aws ecs register-task-definition --cli-input-json "file://$task_definition_file" \
    --query taskDefinition.taskDefinitionArn --output text
}

wait_until_stable() {
  echo "Waiting for $SERVICE to stabilize (up to 10 minutes)..."
  if ! aws ecs wait services-stable --cluster "$CLUSTER" --services "$SERVICE"; then
    echo "Service did not stabilize. Recent logs:" >&2
    aws logs tail "$LOG_GROUP" --since "$FAILURE_LOG_WINDOW" | tail -n "$FAILURE_LOG_LINES" >&2
    exit 1
  fi
}

roll_out() {
  local task_definition_arn="$1"
  aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" \
    --task-definition "$task_definition_arn" --desired-count 1 --force-new-deployment > /dev/null
  wait_until_stable
}

restart() {
  aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" \
    --desired-count 1 --force-new-deployment > /dev/null
  wait_until_stable
}

running_image() {
  local task_definition_arn
  task_definition_arn="$(aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" \
    --query 'services[0].taskDefinition' --output text)"
  aws ecs describe-task-definition --task-definition "$task_definition_arn" \
    --query "taskDefinition.containerDefinitions[?name=='${CONTAINER}'].image | [0]" --output text
}

main() {
  local mode="${1:-deploy}"
  local task_definition_arn
  case "$mode" in
    deploy | --restart) (($# <= 1)) || fail "$USAGE" ;;
    --rollback) (($# == 2)) || fail "$USAGE" ;;
    *) fail "$USAGE" ;;
  esac

  require_tools

  REPO="$(terraform_output ecr_repository_url)"
  CLUSTER="$(terraform_output ecs_cluster_name)"
  SERVICE="$(terraform_output ecs_service_name)"
  FAMILY="$(terraform_output task_family)"
  CONTAINER="$(terraform_output container_name)"
  LOG_GROUP="$(terraform_output log_group_name)"
  SSM_PREFIX="$(terraform_output ssm_prefix)"
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT

  warn_unassigned_params

  case "$mode" in
    deploy)
      local tag
      tag="$(image_tag)"
      build_and_push "$tag"
      task_definition_arn="$(register_revision "$REPO:$tag")"
      roll_out "$task_definition_arn"
      ;;
    --restart)
      restart
      ;;
    --rollback)
      local rollback_tag="$2"
      require_image_exists "$rollback_tag"
      task_definition_arn="$(register_revision "$REPO:$rollback_tag")"
      roll_out "$task_definition_arn"
      ;;
  esac

  echo "Deployed $(running_image) → $(terraform_output api_url)"
}

main "$@"
