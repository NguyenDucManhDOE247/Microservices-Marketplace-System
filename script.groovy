def checkoutCode() {
    checkout scm
    echo "Checked out source code"
}

def buildAndPushDockerImages() {
    sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
    def services = ["user-service", "product-service", "order-service", "payment-service", "frontend", "gateway"]
    services.each { svc ->
        echo "Building and pushing image for: ${svc}"
        sh "docker build -t ${ECR_REGISTRY}/osm-${svc}:${IMAGE_TAG} ./${svc}"
        sh "docker push ${ECR_REGISTRY}/osm-${svc}:${IMAGE_TAG}"
    }
}

def deployToKubernetes() {
    echo "Updating kubeconfig for EKS cluster ${EKS_CLUSTER}..."
    sh "aws eks update-kubeconfig --name ${EKS_CLUSTER} --region ${AWS_REGION}"
    echo "Deploying all Kubernetes manifests from ${K8S_PATH}/"
    sh "kubectl apply -f ${K8S_PATH}/namespace.yaml"
    sh "kubectl apply -f ${K8S_PATH}/"
    echo "Deployment completed successfully"
}

def verifyDeployment() {
    echo "Verifying deployment..."
    sh "kubectl get pods -n osm"
    sh "kubectl get services -n osm"
    sh "kubectl rollout status deployment/user-service -n osm --timeout=120s"
    sh "kubectl rollout status deployment/product-service -n osm --timeout=120s"
    sh "kubectl rollout status deployment/order-service -n osm --timeout=120s"
    sh "kubectl rollout status deployment/payment-service -n osm --timeout=120s"
    sh "kubectl rollout status deployment/frontend -n osm --timeout=120s"
    sh "kubectl rollout status deployment/gateway -n osm --timeout=120s"
}

return this