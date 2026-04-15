# =============================================================================
# Root Module - Online Service Marketplace Infrastructure
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

# ----- VPC -----
module "vpc" {
  source = "./modules/vpc"

  project_name         = var.project_name
  vpc_cidr             = var.vpc_cidr
  availability_zones   = var.availability_zones
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  eks_cluster_name     = var.eks_cluster_name
}

# ----- IAM -----
module "iam" {
  source = "./modules/iam"

  project_name = var.project_name
  aws_region   = var.aws_region
  account_id   = data.aws_caller_identity.current.account_id
}

# ----- ECR -----
module "ecr" {
  source = "./modules/ecr"

  project_name = var.project_name
  services     = var.ecr_services
}

# ----- EKS -----
module "eks" {
  source = "./modules/eks"

  project_name        = var.project_name
  cluster_name        = var.eks_cluster_name
  cluster_version     = var.eks_cluster_version
  subnet_ids          = module.vpc.private_subnet_ids
  cluster_role_arn    = module.iam.eks_cluster_role_arn
  node_role_arn       = module.iam.eks_node_role_arn
  node_instance_type  = var.eks_node_instance_type
  node_desired        = var.eks_node_desired
  node_min            = var.eks_node_min
  node_max            = var.eks_node_max

  depends_on = [module.iam]
}

# ----- EC2 (MongoDB + Jenkins) -----
module "ec2" {
  source = "./modules/ec2"

  project_name               = var.project_name
  vpc_id                     = module.vpc.vpc_id
  private_subnet_id          = module.vpc.private_subnet_ids[0]
  public_subnet_id           = module.vpc.public_subnet_ids[0]
  key_pair_name              = var.key_pair_name
  mongodb_instance_type      = var.mongodb_instance_type
  jenkins_instance_type      = var.jenkins_instance_type
  jenkins_instance_profile   = module.iam.jenkins_instance_profile_name
  allowed_ssh_cidr           = var.allowed_ssh_cidr
  eks_node_security_group_id = module.eks.node_security_group_id
  eks_cluster_name           = var.eks_cluster_name
  aws_region                 = var.aws_region
  ecr_registry               = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"

  depends_on = [module.vpc, module.eks]
}

# ----- Jenkins → EKS API Access -----
resource "aws_security_group_rule" "jenkins_to_eks_api" {
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = module.eks.cluster_security_group_id
  source_security_group_id = module.ec2.jenkins_security_group_id
  description              = "Allow Jenkins to access EKS API"

  depends_on = [module.eks, module.ec2]
}
