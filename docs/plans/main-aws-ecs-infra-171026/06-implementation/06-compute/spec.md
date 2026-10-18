# Compute (ECR + ECS Fargate + IAM) Implementation

## Overview

This module defines:
- the ECR repo
- the log group
- the execution and task IAM roles
- the ECS cluster
- an ARM64 Fargate task definition that injects its config from SSM
- a single-task service in the private-app subnets behind the ALB

Terraform creates the service. After that, `deploy.sh` owns its image and desired count.

## Files to Modify/Create

- `infra/compute.tf` (new):
  - `aws_ecr_repository.backend`, `aws_ecr_lifecycle_policy.backend`
  - `aws_cloudwatch_log_group.backend`
  - `data "aws_iam_policy_document" "ecs_tasks_trust"`
  - `aws_iam_role.backend_execution`, `aws_iam_role_policy_attachment.backend_execution_managed`, `aws_iam_role_policy.backend_execution_ssm`
  - `aws_iam_role.backend_task`, `aws_iam_role_policy.backend_task_evidence`, `aws_iam_role_policy.backend_task_realtime`, `aws_iam_role_policy.backend_task_guardrail`, `aws_iam_role_policy.backend_task_exec`
  - `aws_ecs_cluster.main`, `aws_ecs_task_definition.backend`, `aws_ecs_service.backend`
- `infra/outputs.tf`: add the outputs listed under Integration Notes.

## Implementation Guidelines

### ECR + logs
```hcl
resource "aws_ecr_repository" "backend" {
  name                 = "blinka-backend"
  image_tag_mutability = "MUTABLE" # :latest is re-pushed; sha tags are never reused
  force_delete         = true
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 10 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
      action       = { type = "expire" }
    }]
  })
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/blinka-backend"
  retention_in_days = 7
}
```

### IAM
- `ecs_tasks_trust` allows the principal `ecs-tasks.amazonaws.com` to call `sts:AssumeRole`. Add the condition `StringEquals aws:SourceAccount = data.aws_caller_identity.current.account_id`.
- **Execution role** `blinka-backend-execution`:
  - Attach `arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy`.
  - Add an inline policy allowing `ssm:GetParameters` on `"arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${local.ssm_prefix}/*"`.
- **Task role** `blinka-backend-task`, with these inline policies:
  - `backend_task_evidence` uses `data.aws_iam_policy_document.backend_evidence.json` (from `evidence.tf`).
  - `backend_task_realtime` uses `data.aws_iam_policy_document.backend_realtime_publish.json` (from `realtime.tf`).
  - `backend_task_guardrail` uses a new document with `bedrock:ApplyGuardrail` on:
    ```hcl
    resources = [
      aws_bedrock_guardrail.email_input_guard.guardrail_arn,
      "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:guardrail-profile/us.guardrail.v1:0",
    ]
    ```
  - `backend_task_exec` uses a new document with `ssmmessages:CreateControlChannel`, `ssmmessages:CreateDataChannel`, `ssmmessages:OpenControlChannel` and `ssmmessages:OpenDataChannel` on `*`.

### Cluster + task definition
```hcl
resource "aws_ecs_cluster" "main" {
  name = "blinka"
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "blinka-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.backend_execution.arn
  task_role_arn            = aws_iam_role.backend_task.arn

  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([{
    name         = "backend"
    image        = "${aws_ecr_repository.backend.repository_url}:latest"
    essential    = true
    stopTimeout  = 60 # lets the lifespan cancel registries and dispose pools
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    secrets      = [for name, param in local.backend_params : { name = name, valueFrom = param.arn }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.backend.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "backend"
      }
    }
  }])
}
```

### Service
```hcl
resource "aws_ecs_service" "backend" {
  name                               = "blinka-backend"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.backend.arn
  launch_type                        = "FARGATE"
  desired_count                      = 0 # deploy.sh sets 1 after the first push
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
  health_check_grace_period_seconds  = 180 # migrations + LangGraph setup + demo seed
  enable_execute_command             = true

  network_configuration {
    subnets          = aws_subnet.app[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "backend"
    container_port   = 8000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = false # with a stop-then-start rollout there is no healthy revision to roll back to
  }

  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }

  depends_on = [aws_lb_listener.https]
}
```

## Dependencies

- From module 02: `aws_subnet.app` and `aws_security_group.app`.
- From module 03: `aws_lb_target_group.api` and `aws_lb_listener.https`.
- From module 05: `local.backend_params`.
- Existing: `data.aws_caller_identity.current` (`main.tf`).

## Integration Notes

Outputs that `deploy.sh` (module 07) reads with `terraform -chdir=infra output -raw <name>`:
| Output | Value |
|---|---|
| `ecr_repository_url` | `aws_ecr_repository.backend.repository_url` |
| `ecs_cluster_name` | `aws_ecs_cluster.main.name` |
| `ecs_service_name` | `aws_ecs_service.backend.name` |
| `task_family` | `aws_ecs_task_definition.backend.family` |
| `container_name` | `"backend"` |
| `log_group_name` | `aws_cloudwatch_log_group.backend.name` |
| `ssm_prefix` | `local.ssm_prefix` |
| `api_url` | `"https://${local.api_host}"` |
| `db_endpoint` | `aws_db_instance.main.address` |
| `jwt_secret`, `demo_password` | sensitive, from module 05 |

ECS Exec into the task:
```
aws ecs execute-command --cluster blinka --task <id> --container backend --interactive --command "/bin/sh"
```
The local machine needs the Session Manager plugin for this.
