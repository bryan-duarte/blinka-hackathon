locals {
  backend_service_name           = "${local.name}-backend"
  backend_container_name         = "backend"
  ecr_images_kept                = 10
  log_retention_days             = 7
  backend_task_cpu_units         = 1024
  backend_task_memory_mib        = 2048
  container_stop_timeout_seconds = 60
  startup_grace_period_seconds   = 180
  ssm_parameter_arn_wildcard     = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${local.ssm_prefix}/*"
}

resource "aws_ecr_repository" "backend" {
  name                 = local.backend_service_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last ${local.ecr_images_kept} images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = local.ecr_images_kept }
      action       = { type = "expire" }
    }]
  })
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${local.backend_service_name}"
  retention_in_days = local.log_retention_days
}

data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "backend_execution" {
  name               = "${local.backend_service_name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

resource "aws_iam_role_policy_attachment" "backend_execution_managed" {
  role       = aws_iam_role.backend_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "backend_execution_ssm" {
  statement {
    sid       = "InjectBackendConfig"
    effect    = "Allow"
    actions   = ["ssm:GetParameters"]
    resources = [local.ssm_parameter_arn_wildcard]
  }
}

resource "aws_iam_role_policy" "backend_execution_ssm" {
  name   = "read-backend-config"
  role   = aws_iam_role.backend_execution.id
  policy = data.aws_iam_policy_document.backend_execution_ssm.json
}

resource "aws_iam_role" "backend_task" {
  name               = "${local.backend_service_name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

resource "aws_iam_role_policy" "backend_task_evidence" {
  name   = "evidence"
  role   = aws_iam_role.backend_task.id
  policy = data.aws_iam_policy_document.backend_evidence.json
}

resource "aws_iam_role_policy" "backend_task_realtime" {
  name   = "realtime-publish"
  role   = aws_iam_role.backend_task.id
  policy = data.aws_iam_policy_document.backend_realtime_publish.json
}

data "aws_iam_policy_document" "backend_guardrail" {
  statement {
    sid     = "ScreenEmailInput"
    effect  = "Allow"
    actions = ["bedrock:ApplyGuardrail"]
    resources = [
      aws_bedrock_guardrail.email_input_guard.guardrail_arn,
      "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:guardrail-profile/us.guardrail.v1:0",
    ]
  }
}

resource "aws_iam_role_policy" "backend_task_guardrail" {
  name   = "guardrail"
  role   = aws_iam_role.backend_task.id
  policy = data.aws_iam_policy_document.backend_guardrail.json
}

locals {
  bedrock_claude_profile_arns = "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/*${var.bedrock_claude_model_family}*"
}

data "aws_iam_policy_document" "backend_bedrock_invoke" {
  statement {
    sid       = "InvokeClaudeProfiles"
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [local.bedrock_claude_profile_arns]
  }

  statement {
    sid       = "InvokeClaudeViaProfile"
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = ["arn:aws:bedrock:*::foundation-model/${var.bedrock_claude_model_family}*"]

    condition {
      test     = "StringLike"
      variable = "bedrock:InferenceProfileArn"
      values   = [local.bedrock_claude_profile_arns]
    }
  }

  statement {
    sid       = "EmbedMemories"
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_embedding_model_id}"]
  }
}

resource "aws_iam_role_policy" "backend_task_bedrock_invoke" {
  name   = "bedrock-invoke"
  role   = aws_iam_role.backend_task.id
  policy = data.aws_iam_policy_document.backend_bedrock_invoke.json
}

resource "aws_iam_user_policy" "backend_bedrock_invoke" {
  name   = "${local.name}-bedrock-invoke"
  user   = var.backend_iam_user
  policy = data.aws_iam_policy_document.backend_bedrock_invoke.json
}

data "aws_iam_policy_document" "ecs_exec" {
  statement {
    sid    = "EcsExecSessions"
    effect = "Allow"
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "backend_task_exec" {
  name   = "ecs-exec"
  role   = aws_iam_role.backend_task.id
  policy = data.aws_iam_policy_document.ecs_exec.json
}

resource "aws_ecs_cluster" "main" {
  name = local.name
}

resource "aws_ecs_task_definition" "backend" {
  family                   = local.backend_service_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = local.backend_task_cpu_units
  memory                   = local.backend_task_memory_mib
  execution_role_arn       = aws_iam_role.backend_execution.arn
  task_role_arn            = aws_iam_role.backend_task.arn

  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([{
    name         = local.backend_container_name
    image        = "${aws_ecr_repository.backend.repository_url}:latest"
    essential    = true
    stopTimeout  = local.container_stop_timeout_seconds
    portMappings = [{ containerPort = local.backend_container_port, protocol = "tcp" }]
    secrets      = [for env_var_name, parameter in local.backend_params : { name = env_var_name, valueFrom = parameter.arn }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.backend.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = local.backend_container_name
      }
    }
  }])
}

# deploy.sh owns the running revision and the desired count after creation.
resource "aws_ecs_service" "backend" {
  name                               = local.backend_service_name
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.backend.arn
  launch_type                        = "FARGATE"
  desired_count                      = 0
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
  health_check_grace_period_seconds  = local.startup_grace_period_seconds
  enable_execute_command             = true

  network_configuration {
    subnets          = aws_subnet.app[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = local.backend_container_name
    container_port   = local.backend_container_port
  }

  # Stop-then-start leaves no healthy revision to roll back to.
  deployment_circuit_breaker {
    enable   = true
    rollback = false
  }

  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }

  depends_on = [aws_lb_listener.https]
}
