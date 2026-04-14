def gv

pipeline {
    agent any
    
    environment {
        AWS_ACCOUNT_ID = "825621302666"
        AWS_REGION = "ap-southeast-1"
        ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        EKS_CLUSTER = "osm-cluster"
        IMAGE_TAG = "latest"
        K8S_PATH = "k8s"
    }
    
    stages {
        stage("Init") {
            steps {
                script {
                    gv = load "script.groovy"
                }
            }
        }
        
        stage("Checkout Code") {
            steps {
                script {
                    gv.checkoutCode()
                }
            }
        }

        stage("Build and Push Docker Images") {
            steps {
                script {
                    gv.buildAndPushDockerImages()
                }
            }
        }
        
        stage("Deploy to Kubernetes") {
            steps {
                script {
                    gv.deployToKubernetes()
                }
            }
        }
        
        stage("Verify Deployment") {
            steps {
                script {
                    gv.verifyDeployment()
                }
            }
        }
    }
    
    post {
        success {
            echo "CI/CD pipeline executed successfully!"
        }
        failure {
            echo "CI/CD pipeline failed!"
        }
    }
}