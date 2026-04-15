output "mongodb_private_ip" {
  description = "MongoDB EC2 private IP address"
  value       = aws_instance.mongodb.private_ip
}

output "mongodb_instance_id" {
  description = "MongoDB EC2 instance ID"
  value       = aws_instance.mongodb.id
}

output "jenkins_public_ip" {
  description = "Jenkins EC2 public IP address"
  value       = aws_instance.jenkins.public_ip
}

output "jenkins_instance_id" {
  description = "Jenkins EC2 instance ID"
  value       = aws_instance.jenkins.id
}

output "mongodb_security_group_id" {
  description = "MongoDB security group ID"
  value       = aws_security_group.mongodb.id
}

output "jenkins_security_group_id" {
  description = "Jenkins security group ID"
  value       = aws_security_group.jenkins.id
}
