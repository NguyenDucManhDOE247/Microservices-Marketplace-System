#!/usr/bin/env groovy

def gv

pipeline {
    agent any
    
    environment {
        AWS_ACCOUNT_ID = "825621302666"
        AWS_REGION = "ap-southeast-1"
        ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        EKS_CLUSTER = "osm-cluster"
        K8S_PATH = "k8s"
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