# AppSync Events Infra Implementation

## Overview

Terraform for an AWS AppSync **Events** API (not GraphQL) with these pieces:
- One `inbox` channel namespace. Publishing uses IAM; subscribing uses an API key.
- An API key for the browser.
- The IAM publish permission for the backend's current IAM user. It is written as a reusable policy document so it can attach to an instance role later.

## Files to Modify/Create

- `infra/realtime.tf` (new): `aws_appsync_api.events`, `aws_appsync_channel_namespace.inbox`, `aws_appsync_api_key.events`, `data.aws_iam_policy_document.backend_realtime_publish`, `aws_iam_user_policy.backend_realtime`.
- `infra/variables.tf`: add `events_api_name` (default `"blinka-events"`) and `events_api_key_expires` (string RFC3339, default `"2027-10-01T00:00:00Z"`, max 365 days from creation).
- `infra/outputs.tf`: add `events_http_domain`, `events_realtime_domain` and `events_api_key` (sensitive). Each description names the env var to set, following the existing `outputs.tf` style.
- `infra/versions.tf`: tighten the aws provider to `">= 6.9, < 7.0"`. `aws_appsync_api` was added in 6.9.0; the lock is 6.69.1.

## Implementation Guidelines

```hcl
# orientative — hashicorp/aws 6.69.1
resource "aws_appsync_api" "events" {
  name = var.events_api_name
  event_config {
    auth_provider { auth_type = "AWS_IAM" }
    auth_provider { auth_type = "API_KEY" }
    connection_auth_mode        { auth_type = "API_KEY" }
    default_publish_auth_mode   { auth_type = "AWS_IAM" }
    default_subscribe_auth_mode { auth_type = "API_KEY" }
  }
}

resource "aws_appsync_channel_namespace" "inbox" {
  api_id = aws_appsync_api.events.api_id
  name   = "inbox"                       # must equal BLINKA_REALTIME__NAMESPACE
  publish_auth_mode   { auth_type = "AWS_IAM" }   # browser can never publish
  subscribe_auth_mode { auth_type = "API_KEY" }
}

resource "aws_appsync_api_key" "events" {
  api_id  = aws_appsync_api.events.api_id
  expires = var.events_api_key_expires   # never timestamp(): perpetual diff
}

data "aws_iam_policy_document" "backend_realtime_publish" {
  statement {
    actions   = ["appsync:EventPublish", "appsync:EventConnect"]
    resources = [aws_appsync_api.events.api_arn, "${aws_appsync_api.events.api_arn}/*"]
  }
}

# Today: the developer IAM user. Deploy: attach the same document to the instance role.
resource "aws_iam_user_policy" "backend_realtime" {
  name   = "blinka-backend-realtime"
  user   = var.backend_iam_user
  policy = data.aws_iam_policy_document.backend_realtime_publish.json
}

output "events_http_domain" {
  value       = aws_appsync_api.events.dns["HTTP"]
  description = "Set as BLINKA_REALTIME__HTTP_DOMAIN in backend/.env and NEXT_PUBLIC_APPSYNC_EVENTS_ENDPOINT=https://<value>/event in frontend/.env.local."
}
output "events_realtime_domain" {
  value       = aws_appsync_api.events.dns["REALTIME"]
  description = "Realtime WebSocket domain (Amplify derives it from the HTTP endpoint)."
}
output "events_api_key" {
  value       = aws_appsync_api_key.events.key
  sensitive   = true
  description = "Set as NEXT_PUBLIC_APPSYNC_EVENTS_API_KEY in frontend/.env.local."
}
```

- Follow the conventions in `infra/evidence.tf`:
  - `blinka-` kebab-case resource names, snake_case local names
  - policies as `data "aws_iam_policy_document"`
  - short "why" comments
  - no tags
- The channel namespace ARN form is `arn:aws:appsync:{region}:{acct}:apis/{apiId}/channelNamespace/inbox`. `"${api_arn}/*"` covers it.
- After the first `terraform apply`, confirm the `dns` map keys are `HTTP` and `REALTIME` with `terraform console` → `aws_appsync_api.events.dns`. If they differ, adjust the outputs.

## Dependencies

- The existing provider and profile setup (`infra/providers.tf`) and `var.backend_iam_user` (`infra/variables.tf:25-29`).

## Integration Notes

- **Backend (module 03):** `BLINKA_REALTIME__ENABLED=true`, `BLINKA_REALTIME__HTTP_DOMAIN=<events_http_domain>`, `BLINKA_REALTIME__REGION=us-east-1`.
- **Frontend (module 07):** `NEXT_PUBLIC_APPSYNC_EVENTS_ENDPOINT=https://<events_http_domain>/event`, `NEXT_PUBLIC_APPSYNC_EVENTS_REGION=us-east-1`, `NEXT_PUBLIC_APPSYNC_EVENTS_API_KEY=<terraform output -raw events_api_key>`.
- **Security trade-off (accepted):** anyone holding the public API key and a user's UUID can subscribe to that user's channel. Nobody can publish without IAM.
