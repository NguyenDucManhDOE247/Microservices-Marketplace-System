// =====================================================================
// Online Service Marketplace - CI/CD Pipeline Functions
// Branch-aware: refactor/* → validate | dev → osm-dev | main → osm
// =====================================================================

SERVICES = ["user-service", "product-service", "order-service", "payment-service", "frontend", "gateway"]
K8S_NAMESPACE = ""
IMAGE_TAG = ""
APP_VERSION = ""

// -------------------------------------------------------------------
// Init: determine namespace and image tag based on branch
// -------------------------------------------------------------------
def initBranchConfig() {
    if (BRANCH_NAME == "main") {
        K8S_NAMESPACE = "osm"
        IMAGE_TAG = "latest"
        echo "Branch: main → namespace: osm, tag: latest + version"
    } else if (BRANCH_NAME == "dev") {
        K8S_NAMESPACE = "osm-dev"
        IMAGE_TAG = "dev-${BUILD_NUMBER}"
        echo "Branch: dev → namespace: osm-dev, tag: dev-${BUILD_NUMBER}"
    } else {
        K8S_NAMESPACE = ""
        IMAGE_TAG = ""
        echo "Branch: ${BRANCH_NAME} → validate only, no build/deploy"
    }
}

// -------------------------------------------------------------------
// Checkout
// -------------------------------------------------------------------
def checkoutCode() {
    checkout scm
    echo "Checked out source code from branch: ${BRANCH_NAME}"
}

// -------------------------------------------------------------------
// Validate (refactor/* branches only)
// -------------------------------------------------------------------
def validateCode() {
    echo "Running validation for refactor branch: ${BRANCH_NAME}"

    // Validate package.json syntax for all services
    SERVICES.each { svc ->
        if (fileExists("${svc}/package.json")) {
            echo "Validating ${svc}/package.json..."
            sh "python3 -c \"import json; json.load(open('${svc}/package.json'))\" || true"
        }
    }

    // Validate Kubernetes manifests syntax
    if (fileExists("${K8S_PATH}/namespace.yaml")) {
        echo "Validating Kubernetes manifests..."
        sh "kubectl apply --dry-run=client -f ${K8S_PATH}/ || true"
    }

    // Validate Terraform if present
    if (fileExists("terraform/main.tf")) {
        echo "Validating Terraform configuration..."
        dir("terraform") {
            sh "terraform fmt -check -recursive || true"
            sh "terraform validate || true"
        }
    }

    echo "Validation completed"
}

// -------------------------------------------------------------------
// Version management (main branch only)
// -------------------------------------------------------------------
def readAppVersion() {
    def packageJson = readJSON file: "user-service/package.json"
    APP_VERSION = packageJson.version
    echo "Current application version: ${APP_VERSION}"

    // For main branch: tag with version + latest
    IMAGE_TAG = APP_VERSION
    echo "Docker image tag set to: ${IMAGE_TAG}"
}

def bumpVersion() {
    echo "Bumping patch version..."

    // Parse current version
    def (major, minor, patch) = APP_VERSION.tokenize('.').collect { it.toInteger() }
    def newVersion = "${major}.${minor}.${patch + 1}"
    echo "Version bump: ${APP_VERSION} → ${newVersion}"

    // Update version in all service package.json files
    SERVICES.each { svc ->
        if (fileExists("${svc}/package.json")) {
            sh "sed -i 's/\"version\": \"${APP_VERSION}\"/\"version\": \"${newVersion}\"/' ${svc}/package.json"
        }
    }

    // Commit and push version bump
    withCredentials([usernamePassword(credentialsId: 'github-credentials', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_TOKEN')]) {
        sh """
            git config user.email "jenkins@osm-pipeline.com"
            git config user.name "Jenkins CI"
            git add */package.json
            git commit -m "ci: bump version to ${newVersion} [skip ci]"
            git push https://\${GIT_USER}:\${GIT_TOKEN}@github.com/NguyenDucManhDOE247/Microservices-Marketplace-System.git HEAD:main
        """
    }

    echo "Version bumped to ${newVersion} and pushed to main"
}

// -------------------------------------------------------------------
// Run Jest tests for all backend services
// Uses Docker (node:22-slim) to avoid npm PATH issues on Jenkins agent.
// node:22-slim is Debian-based (glibc) - required by mongodb-memory-server.
// MongoDB binary is cached in /var/lib/jenkins/.mongoms-cache between runs.
// -------------------------------------------------------------------
def runTests() {
    def testServices = ["user-service", "product-service", "order-service", "payment-service"]
    echo "Running Jest tests for ${testServices.size()} services..."

    // Ensure MongoDB binary cache directory exists on Jenkins agent
    sh "mkdir -p /var/lib/jenkins/.mongoms-cache"

    testServices.each { svc ->
        echo "Testing: ${svc}"
        dir(svc) {
            sh """
                docker run --rm \\
                    -v \$(pwd):/app \\
                    -v /var/lib/jenkins/.mongoms-cache:/mongoms-cache \\
                    -w /app \\
                    -e CI=true \\
                    -e MONGOMS_DOWNLOAD_DIR=/mongoms-cache \\
                    node:22-slim \\
                    sh -c 'npm install && npm test'
            """
        }
    }

    echo "All tests passed"
}

// -------------------------------------------------------------------
// Build Docker images
// -------------------------------------------------------------------
def buildDockerImages() {
    echo "Building Docker images with tag: ${IMAGE_TAG}"
    SERVICES.each { svc ->
        echo "Building image for: ${svc}"
        sh "docker build -t ${ECR_REGISTRY}/osm-${svc}:${IMAGE_TAG} ./${svc}"

        // For main branch, also tag as latest
        if (BRANCH_NAME == "main" && IMAGE_TAG != "latest") {
            sh "docker tag ${ECR_REGISTRY}/osm-${svc}:${IMAGE_TAG} ${ECR_REGISTRY}/osm-${svc}:latest"
        }
    }
    echo "All images built successfully"
}

// -------------------------------------------------------------------
// Push Docker images to ECR
// -------------------------------------------------------------------
def pushDockerImages() {
    echo "Logging into ECR..."
    sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"

    echo "Pushing images to ECR with tag: ${IMAGE_TAG}"
    SERVICES.each { svc ->
        sh "docker push ${ECR_REGISTRY}/osm-${svc}:${IMAGE_TAG}"

        // For main branch, also push latest tag
        if (BRANCH_NAME == "main" && IMAGE_TAG != "latest") {
            sh "docker push ${ECR_REGISTRY}/osm-${svc}:latest"
        }
    }
    echo "All images pushed to ECR"
}

// -------------------------------------------------------------------
// Deploy to Kubernetes
// -------------------------------------------------------------------
// Install cluster-level prerequisites (idempotent - safe to run every time)
// -------------------------------------------------------------------
def installClusterPrerequisites() {
    echo "Checking and installing cluster prerequisites..."

    // Install NGINX Ingress Controller if not present
    sh """
        if ! kubectl get namespace ingress-nginx > /dev/null 2>&1; then
            echo "Installing NGINX Ingress Controller..."
            kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.1/deploy/static/provider/aws/deploy.yaml
            echo "Waiting for NGINX Ingress Controller to be ready..."
            kubectl wait --namespace ingress-nginx \
                --for=condition=ready pod \
                --selector=app.kubernetes.io/component=controller \
                --timeout=180s
        else
            echo "NGINX Ingress Controller already installed"
        fi
    """

    // Install metrics-server if not present (required for HPA)
    sh """
        if ! kubectl get deployment metrics-server -n kube-system > /dev/null 2>&1; then
            echo "Installing metrics-server..."
            kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
            echo "Waiting for metrics-server to be ready..."
            kubectl wait --namespace kube-system \
                --for=condition=ready pod \
                --selector=k8s-app=metrics-server \
                --timeout=120s
        else
            echo "metrics-server already installed"
        fi
    """

    echo "Cluster prerequisites verified"
}

// -------------------------------------------------------------------
def deployToKubernetes() {
    echo "Updating kubeconfig for EKS cluster ${EKS_CLUSTER}..."
    sh "aws eks update-kubeconfig --name ${EKS_CLUSTER} --region ${AWS_REGION}"

    // Install NGINX Ingress Controller + metrics-server if not already present
    installClusterPrerequisites()

    echo "Deploying to namespace: ${K8S_NAMESPACE}"

    // Create namespace if it doesn't exist
    sh "kubectl create namespace ${K8S_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -"

    if (BRANCH_NAME == "main") {
        // Apply namespace, ConfigMap and Secrets first so pods can reference them on startup
        sh "kubectl apply -f ${K8S_PATH}/namespace.yaml"
        sh "kubectl apply -f ${K8S_PATH}/configmap.yaml"
        sh "kubectl apply -f ${K8S_PATH}/secrets.yaml"
        // Apply everything else (idempotent - configmap/secrets applied again is fine)
        sh "kubectl apply -f ${K8S_PATH}/"
    } else if (BRANCH_NAME == "dev") {
        // Dev branch: copy manifests, replace namespace and image tags
        // Ingress is excluded: NGINX Ingress Controller is cluster-wide and does not
        // allow duplicate host+path combinations across namespaces. The Ingress in
        // namespace 'osm' already claims all paths; dev uses kubectl port-forward.
        sh """
            mkdir -p /tmp/k8s-dev
            cp ${K8S_PATH}/*.yaml /tmp/k8s-dev/
            rm -f /tmp/k8s-dev/ingress.yaml
            sed -i 's/namespace: osm\$/namespace: ${K8S_NAMESPACE}/g' /tmp/k8s-dev/*.yaml
            sed -i 's/:latest/:${IMAGE_TAG}/g' /tmp/k8s-dev/*.yaml
            kubectl apply -f /tmp/k8s-dev/namespace-dev.yaml
            kubectl apply -f /tmp/k8s-dev/configmap.yaml
            kubectl apply -f /tmp/k8s-dev/secrets.yaml
            kubectl apply -f /tmp/k8s-dev/
            rm -rf /tmp/k8s-dev
        """
    }

    echo "Deployment to ${K8S_NAMESPACE} completed successfully"
}

// -------------------------------------------------------------------
// Verify deployment
// -------------------------------------------------------------------
def verifyDeployment() {
    echo "Verifying deployment in namespace: ${K8S_NAMESPACE}..."
    sh "kubectl get pods -n ${K8S_NAMESPACE}"
    sh "kubectl get services -n ${K8S_NAMESPACE}"

    def deployments = ["user-service", "product-service", "order-service", "payment-service", "frontend", "gateway"]
    deployments.each { deploy ->
        sh "kubectl rollout status deployment/${deploy} -n ${K8S_NAMESPACE} --timeout=120s"
    }

    echo "All deployments verified in ${K8S_NAMESPACE}"
}

return this