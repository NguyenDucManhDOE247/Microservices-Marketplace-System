#!/usr/bin/env groovy

def gv

pipeline {
    agent any
    
    environment {
        AWS_REGION = "ap-southeast-1"
        EKS_CLUSTER = "osm-cluster"
        K8S_PATH    = "k8s"
        // AWS_ACCOUNT_ID and ECR_REGISTRY are resolved dynamically in Init stage
        // using the IAM role attached to the Jenkins EC2 instance
    }
    
    stages {
        stage("Skip CI Check") {
            steps {
                script {
                    def commitMsg = sh(script: "git log -1 --pretty=%B", returnStdout: true).trim()
                    if (commitMsg.contains("[skip ci]")) {
                        currentBuild.description = "Skipped: [skip ci] commit"
                        currentBuild.result = 'ABORTED'
                        throw new org.jenkinsci.plugins.workflow.steps.FlowInterruptedException(
                            hudson.model.Result.ABORTED
                        )
                    }
                }
            }
        }

        stage("Init") {
            steps {
                script {
                    env.AWS_ACCOUNT_ID = sh(
                        returnStdout: true,
                        script: 'aws sts get-caller-identity --query Account --output text'
                    ).trim()
                    env.ECR_REGISTRY = "${env.AWS_ACCOUNT_ID}.dkr.ecr.${env.AWS_REGION}.amazonaws.com"
                    gv = load "script.groovy"
                    gv.initBranchConfig()
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

        stage("Validate") {
            when {
                expression { BRANCH_NAME.startsWith("refactor/") }
            }
            steps {
                script {
                    gv.validateCode()
                }
            }
        }

        stage("Read Version") {
            when {
                expression { BRANCH_NAME == "main" }
            }
            steps {
                script {
                    gv.readAppVersion()
                }
            }
        }

        stage("Run Tests") {
            when {
                expression { BRANCH_NAME == "main" || BRANCH_NAME == "dev" }
            }
            steps {
                script {
                    gv.runTests()
                }
            }
        }

        stage("Build Docker Images") {
            when {
                expression { BRANCH_NAME == "main" || BRANCH_NAME == "dev" }
            }
            steps {
                script {
                    gv.buildDockerImages()
                }
            }
        }

        stage("Push to ECR") {
            when {
                expression { BRANCH_NAME == "main" || BRANCH_NAME == "dev" }
            }
            steps {
                script {
                    gv.pushDockerImages()
                }
            }
        }
        
        stage("Deploy to Kubernetes") {
            when {
                expression { BRANCH_NAME == "main" || BRANCH_NAME == "dev" }
            }
            steps {
                script {
                    gv.deployToKubernetes()
                }
            }
        }
        
        stage("Verify Deployment") {
            when {
                expression { BRANCH_NAME == "main" || BRANCH_NAME == "dev" }
            }
            steps {
                script {
                    gv.verifyDeployment()
                }
            }
        }

        stage("Bump Version") {
            when {
                expression { BRANCH_NAME == "main" }
            }
            steps {
                script {
                    gv.bumpVersion()
                }
            }
        }
    }
    
    post {
        success {
            echo "Pipeline for branch '${BRANCH_NAME}' executed successfully!"
        }
        failure {
            echo "Pipeline for branch '${BRANCH_NAME}' failed!"
        }
    }
}