# Risks & Mitigations

## Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `assign_later` placeholders pass validation but break the features that use them (for example, OpenRouter returns 401 and Composio auth configs are invalid) | med | Bring-up step: fill them in the SSM console, then run `deploy.sh --restart`. The deploy script prints the parameters that still hold `assign_later`. |
| The first `terraform apply` creates the service before any image exists in ECR | low | The service is created with `desired_count = 0`. `deploy.sh` sets it to 1 after it pushes the image. |
| An ARM64 image built on an x86 machine (a teammate) fails at runtime | low | `deploy.sh` always runs `docker buildx build --platform linux/arm64`. |
| A migration fails in the entrypoint, so the task crash-loops | med | `set -e` stops before uvicorn starts. `deploy.sh` waits for a stable service and dumps the logs if that fails. Roll back with `--rollback <tag>` (only safe if the migration did not partially apply). |
| Uploads take about 60s because of the malware scan, which risks the ALB timing out | low | ALB idle timeout is 120s and uvicorn keep-alive is 130s. |
| A new SSM parameter is not injected until Terraform adds it to the task definition | low | Every parameter is declared in `ssm.tf`. `deploy.sh` clones the latest active revision, so Terraform's changes are carried into the next deploy. |
| The task definition revision registered by Terraform is behind the one `deploy.sh` uses | low | The service ignores `task_definition`. `deploy.sh` always registers its own revision. |
| The RDS password contains URL-breaking characters | low | `random_password` uses `special = false`. |

## Integration Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Replacing `var.jwt_secret` with `random_password` rotates the Lambda authorizer's secret. The local backend's tokens stop authorizing realtime. | med | Output `jwt_secret` (sensitive). Bring-up step: copy it into the local `.env`. Existing users log in again. |
| An existing `terraform.tfvars` still sets `jwt_secret` | low | Terraform only warns about undeclared variables in tfvars. Remove the line. |
| The entrypoint now also runs in `docker compose`, so local starts run the migrations | low | The migrations are idempotent (`upgrade head`), and local databases already exist. This is acceptable and even convenient. |
| Changing the `aws_profile` default to `None` breaks a local setup whose `.env` doesn't set `*_AWS_PROFILE` | low | `.env.example` already sets `=panoptico` for every group. Mention it in the PR. |
| No hosted zone exists for `var.domain_name` | high | `data "aws_route53_zone"` fails at plan time with a clear error. You must create or delegate the zone first. |
| The frontend origin changes (for example, a Vercel preview URL) | low | `BLINKA_CORS__ALLOW_ORIGINS` is a managed parameter. Change `var.frontend_origin`, run `apply`, then `deploy.sh --restart`. |
| The single NAT gateway or AZ goes down, so external calls fail | low | Accepted for a hackathon. |

## Edge Cases Identified

- **Deploying from a dirty working tree.** The tag becomes `<sha>-dirty-<epoch>`, so a later deploy from the same commit never overwrites it.
- **`--rollback` to a tag that doesn't exist.** Before registering, the script checks `aws ecr describe-images --image-ids imageTag=<tag>` and exits with an error if the tag isn't there.
- **A deploy while an agent run is in flight.** With stop-then-start, the run is cancelled, and the next startup sweep marks it failed. This is existing behavior.
- **`blinka_payments` already exists.** `bootstrap` checks `pg_database` first and does nothing if it's there.
- **Destroying the stack.** RDS has no final snapshot, and ECR uses `force_delete`. `terraform destroy` removes all data, which is intended for a hackathon.
