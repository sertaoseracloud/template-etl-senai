output "eventbridge_role_arn" {
  description = "ARN of the EventBridge to Glue IAM role"
  value       = aws_iam_role.eventbridge_to_glue.arn
}
