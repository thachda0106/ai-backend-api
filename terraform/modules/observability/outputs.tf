output "sns_topic_arn" {
  description = "SNS topic ARN for alarm notifications"
  value       = aws_sns_topic.alarms.arn
}
