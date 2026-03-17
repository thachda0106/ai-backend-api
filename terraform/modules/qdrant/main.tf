# ── EFS File System ───────────────────────────────────────────────────────────
resource "aws_efs_file_system" "qdrant" {
  creation_token   = "${var.project}-${var.environment}-qdrant"
  encrypted        = true
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  tags = {
    Name        = "${var.project}-${var.environment}-qdrant-efs"
    Project     = var.project
    Environment = var.environment
  }
}

# EFS mount targets — one per private subnet
resource "aws_efs_mount_target" "qdrant" {
  count           = length(var.private_subnet_ids)
  file_system_id  = aws_efs_file_system.qdrant.id
  subnet_id       = var.private_subnet_ids[count.index]
  security_groups = [var.efs_sg_id]
}

# ── CloudWatch Log Group ──────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "qdrant" {
  name              = "/ecs/${var.project}-${var.environment}/qdrant"
  retention_in_days = 30

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# ── ECS Task Definition ───────────────────────────────────────────────────────
locals {
  qdrant_env = concat(
    [
      { name = "QDRANT__STORAGE__STORAGE_PATH", value = "/qdrant/storage" },
      { name = "QDRANT__STORAGE__SNAPSHOTS_PATH", value = "/qdrant/storage/snapshots" },
      { name = "QDRANT__SERVICE__GRPC_PORT", value = "6334" },
      { name = "QDRANT__LOG_LEVEL", value = "INFO" },
    ],
    var.qdrant_api_key != "" ? [{ name = "QDRANT__SERVICE__API_KEY", value = var.qdrant_api_key }] : []
  )
}

resource "aws_ecs_task_definition" "qdrant" {
  family                   = "${var.project}-${var.environment}-qdrant"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn

  # EFS volume for persistent vector storage
  volume {
    name = "qdrant-storage"

    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.qdrant.id
      transit_encryption = "ENABLED"
    }
  }

  container_definitions = jsonencode([
    {
      name      = "qdrant"
      image     = var.qdrant_image
      essential = true

      portMappings = [
        { containerPort = 6333, protocol = "tcp" }, # REST
        { containerPort = 6334, protocol = "tcp" }  # gRPC
      ]

      mountPoints = [
        {
          containerPath = "/qdrant/storage"
          sourceVolume  = "qdrant-storage"
          readOnly      = false
        }
      ]

      environment = local.qdrant_env

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.qdrant.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "qdrant"
        }
      }
    }
  ])

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# ── ECS Service ───────────────────────────────────────────────────────────────
resource "aws_ecs_service" "qdrant" {
  name            = "${var.project}-${var.environment}-qdrant"
  cluster         = var.ecs_cluster_id
  task_definition = aws_ecs_task_definition.qdrant.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  # EFS support requires Fargate platform version 1.4.0+
  platform_version = "1.4.0"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.qdrant_sg_id]
    assign_public_ip = false
  }

  # Wait for EFS mount targets before starting service
  depends_on = [aws_efs_mount_target.qdrant]

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}
