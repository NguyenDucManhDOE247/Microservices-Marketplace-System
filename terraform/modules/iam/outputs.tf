output "eks_cluster_role_arn" {
  description = "ARN of EKS cluster IAM role"
  value       = aws_iam_role.eks_cluster.arn
}

output "eks_node_role_arn" {
  description = "ARN of EKS node group IAM role"
  value       = aws_iam_role.eks_node.arn
}

output "jenkins_instance_profile_name" {
  description = "Name of Jenkins EC2 instance profile"
  value       = aws_iam_instance_profile.jenkins.name
}

output "jenkins_role_arn" {
  description = "ARN of Jenkins IAM role"
  value       = aws_iam_role.jenkins.arn
}
