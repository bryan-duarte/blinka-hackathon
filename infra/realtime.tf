locals {
  realtime_authorizer_name = "blinka-realtime-authorizer"
  # Only well-formed JWTs reach the Lambda; anything else is rejected by AppSync for free.
  jwt_shape = "^[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+$"
}

data "archive_file" "realtime_authorizer" {
  type        = "zip"
  source_file = "${path.module}/lambda/realtime_authorizer/handler.py"
  output_path = "${path.module}/.build/realtime_authorizer.zip"
}

data "aws_iam_policy_document" "realtime_authorizer_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "realtime_authorizer" {
  name               = local.realtime_authorizer_name
  assume_role_policy = data.aws_iam_policy_document.realtime_authorizer_trust.json
}

resource "aws_iam_role_policy_attachment" "realtime_authorizer_logs" {
  role       = aws_iam_role.realtime_authorizer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Verifies the backend's login JWT and only lets a user subscribe to /inbox/<their sub>.
resource "aws_lambda_function" "realtime_authorizer" {
  function_name    = local.realtime_authorizer_name
  role             = aws_iam_role.realtime_authorizer.arn
  runtime          = "python3.13"
  handler          = "handler.handler"
  filename         = data.archive_file.realtime_authorizer.output_path
  source_code_hash = data.archive_file.realtime_authorizer.output_base64sha256
  timeout          = 5
  memory_size      = 128

  environment {
    variables = {
      JWT_SECRET = random_password.jwt_secret.result
    }
  }
}

resource "aws_lambda_permission" "appsync_invokes_realtime_authorizer" {
  statement_id  = "AllowAppSyncEventsInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.realtime_authorizer.function_name
  principal     = "appsync.amazonaws.com"
  source_arn    = aws_appsync_api.events.api_arn
}

resource "aws_appsync_api" "events" {
  name = var.events_api_name

  event_config {
    auth_provider {
      auth_type = "AWS_IAM"
    }

    auth_provider {
      auth_type = "AWS_LAMBDA"

      lambda_authorizer_config {
        authorizer_uri                   = aws_lambda_function.realtime_authorizer.arn
        authorizer_result_ttl_in_seconds = 300
        identity_validation_expression   = local.jwt_shape
      }
    }

    connection_auth_mode {
      auth_type = "AWS_LAMBDA"
    }

    default_publish_auth_mode {
      auth_type = "AWS_IAM"
    }

    default_subscribe_auth_mode {
      auth_type = "AWS_LAMBDA"
    }
  }
}

# Name must equal BLINKA_REALTIME__NAMESPACE; only the backend (IAM) can publish.
resource "aws_appsync_channel_namespace" "inbox" {
  api_id = aws_appsync_api.events.api_id
  name   = "inbox"

  publish_auth_mode {
    auth_type = "AWS_IAM"
  }

  subscribe_auth_mode {
    auth_type = "AWS_LAMBDA"
  }

  # Second, uncached ownership check on top of the authorizer.
  code_handlers = <<-EOT
    export function onSubscribe(ctx) {
      const handlerContext = ctx.identity && ctx.identity.handlerContext
      const subject = handlerContext && handlerContext.sub
      if (!subject || ctx.info.channel.path !== '/inbox/' + subject) {
        util.unauthorized()
      }
    }
  EOT
}

data "aws_iam_policy_document" "backend_realtime_publish" {
  statement {
    sid       = "PublishInboxEvents"
    effect    = "Allow"
    actions   = ["appsync:EventConnect", "appsync:EventPublish"]
    resources = [aws_appsync_api.events.api_arn, "${aws_appsync_api.events.api_arn}/*"]
  }
}

# Local development publishes as the developer IAM user; ECS gets the same document on its task role.
resource "aws_iam_user_policy" "backend_realtime" {
  name   = "blinka-backend-realtime"
  user   = var.backend_iam_user
  policy = data.aws_iam_policy_document.backend_realtime_publish.json
}
