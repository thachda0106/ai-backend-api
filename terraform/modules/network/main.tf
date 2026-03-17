# ── VPC ───────────────────────────────────────────────────────────────────────
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.project}-${var.environment}-vpc"
    Project     = var.project
    Environment = var.environment
  }
}

# ── Subnets ───────────────────────────────────────────────────────────────────
resource "aws_subnet" "public" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.public_subnet_cidrs[count.index]
  availability_zone = var.azs[count.index]

  map_public_ip_on_launch = true

  tags = {
    Name        = "${var.project}-${var.environment}-public-${count.index + 1}"
    Project     = var.project
    Environment = var.environment
    Tier        = "public"
  }
}

resource "aws_subnet" "private" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.azs[count.index]

  map_public_ip_on_launch = false

  tags = {
    Name        = "${var.project}-${var.environment}-private-${count.index + 1}"
    Project     = var.project
    Environment = var.environment
    Tier        = "private"
  }
}

# ── Internet Gateway ──────────────────────────────────────────────────────────
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "${var.project}-${var.environment}-igw"
    Project     = var.project
    Environment = var.environment
  }
}

# ── NAT Gateway (single AZ — cost-optimised for dev; scale to multi-AZ via count) ──
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name        = "${var.project}-${var.environment}-nat-eip"
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id # Place NAT GW in first public subnet

  depends_on = [aws_internet_gateway.main]

  tags = {
    Name        = "${var.project}-${var.environment}-nat"
    Project     = var.project
    Environment = var.environment
  }
}

# ── Route Tables ──────────────────────────────────────────────────────────────
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name        = "${var.project}-${var.environment}-public-rt"
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name        = "${var.project}-${var.environment}-private-rt"
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# ── Security Groups ───────────────────────────────────────────────────────────

# ALB: accept HTTP/HTTPS from the internet
resource "aws_security_group" "alb" {
  name        = "${var.project}-${var.environment}-alb-sg"
  description = "Application Load Balancer — public internet ingress"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project}-${var.environment}-alb-sg"
    Project     = var.project
    Environment = var.environment
  }
}

# API: accept traffic from ALB only
resource "aws_security_group" "api" {
  name        = "${var.project}-${var.environment}-api-sg"
  description = "API ECS tasks — ingress from ALB only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "API port from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project}-${var.environment}-api-sg"
    Project     = var.project
    Environment = var.environment
  }
}

# Redis: accept traffic from API only
resource "aws_security_group" "redis" {
  name        = "${var.project}-${var.environment}-redis-sg"
  description = "ElastiCache Redis — ingress from API tasks only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Redis port from API"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project}-${var.environment}-redis-sg"
    Project     = var.project
    Environment = var.environment
  }
}

# Qdrant: accept REST and gRPC from API only
resource "aws_security_group" "qdrant" {
  name        = "${var.project}-${var.environment}-qdrant-sg"
  description = "Qdrant ECS tasks — ingress from API tasks only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Qdrant REST from API"
    from_port       = 6333
    to_port         = 6333
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id]
  }

  ingress {
    description     = "Qdrant gRPC from API"
    from_port       = 6334
    to_port         = 6334
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project}-${var.environment}-qdrant-sg"
    Project     = var.project
    Environment = var.environment
  }
}

# EFS: accept NFS from API and Qdrant tasks
resource "aws_security_group" "efs" {
  name        = "${var.project}-${var.environment}-efs-sg"
  description = "EFS mount targets — NFS ingress from API and Qdrant tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "NFS from API tasks"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id]
  }

  ingress {
    description     = "NFS from Qdrant tasks"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.qdrant.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project}-${var.environment}-efs-sg"
    Project     = var.project
    Environment = var.environment
  }
}
