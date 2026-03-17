# ── SNS Topic ─────────────────────────────────────────────────────────────────
resource "aws_sns_topic" "alarms" {
  name = "${var.project}-${var.environment}-alarms"

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# ── ECS CPU Alarm ─────────────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  alarm_name          = "${var.project}-${var.environment}-ecs-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = var.cpu_threshold
  alarm_description   = "ECS API CPU utilisation > ${var.cpu_threshold}%"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.api_service_name
  }

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# ── ECS Memory Alarm ──────────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "ecs_memory_high" {
  alarm_name          = "${var.project}-${var.environment}-ecs-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = var.memory_threshold
  alarm_description   = "ECS API memory utilisation > ${var.memory_threshold}%"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.api_service_name
  }

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# ── ALB 5xx Error Alarm ───────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${var.project}-${var.environment}-alb-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = var.error_5xx_threshold
  alarm_description   = "ALB 5xx errors > ${var.error_5xx_threshold} per minute"
  treat_missing_data  = "notBreaching" # No false positives during quiet periods

  alarm_actions = [aws_sns_topic.alarms.arn]

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.tg_arn_suffix
  }

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}
