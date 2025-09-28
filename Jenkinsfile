pipeline {
  agent any

  triggers {
    // Poll Git every ~2 minutes
    pollSCM('H/2 * * * *')
  }

  options {
    disableConcurrentBuilds()
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    // Keep PATH broad; but we also resolve absolute binaries inside each step.
    PATH = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

    // ===== Registry (Docker Hub) =====
    DOCKERHUB_NS       = 's224917102'
    DOCKERHUB_CREDS    = 'dockerhub-s224917102'
    REGISTRY           = 'docker.io'
    PRODUCT_IMG        = "${REGISTRY}/${DOCKERHUB_NS}/product_service"
    ORDER_IMG          = "${REGISTRY}/${DOCKERHUB_NS}/order_service"
    FRONTEND_IMG       = "${REGISTRY}/${DOCKERHUB_NS}/frontend"

    // ===== Local images (built by docker compose build) =====
    LOCAL_IMG_PRODUCT  = 'localhost/week09_example02_product_service:latest'
    LOCAL_IMG_ORDER    = 'localhost/week09_example02_order_service:latest'
    LOCAL_IMG_FRONTEND = 'localhost/week09_example02_frontend:latest'

    // ===== K8s (local) =====
    KUBE_CONTEXT  = 'docker-desktop'   // or 'minikube'
    NAMESPACE     = 'default'
    K8S_DIR       = 'k8s'

    // ===== SonarCloud (names must match Jenkins global config) =====
    SONAR_SERVER_NAME   = 'SonarQube'     // Manage Jenkins → System → SonarQube servers (Name)
    SONAR_SCANNER_NAME  = 'SonarScanner'  // Manage Jenkins → Global Tool Configuration (Name)
    // Create a Secret Text credential named SONAR_TOKEN in Jenkins (token from SonarCloud)

    // ===== Project paths =====
    PRODUCT_DIR  = 'backend/product_service'
    ORDER_DIR    = 'backend/order_service'
    FRONTEND_DIR = 'frontend'
  }

  stages {

    // 1) BUILD
    stage('Build') {
      steps {
        checkout scm
        sh '''#!/usr/bin/env bash
set -euo pipefail

# ----- Resolve docker & compose (absolute) -----
DOCKER_BIN=""
if [ -x /usr/local/bin/docker ]; then DOCKER_BIN=/usr/local/bin/docker
elif [ -x /opt/homebrew/bin/docker ]; then DOCKER_BIN=/opt/homebrew/bin/docker
elif command -v docker >/dev/null 2>&1; then DOCKER_BIN="$(command -v docker)"
else
  echo "[ERROR] docker not found"; exit 127
fi

if ${DOCKER_BIN} compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE="${DOCKER_BIN} compose"
elif [ -x /usr/local/bin/docker-compose ]; then
  DOCKER_COMPOSE="/usr/local/bin/docker-compose"
elif [ -x /opt/homebrew/bin/docker-compose ]; then
  DOCKER_COMPOSE="/opt/homebrew/bin/docker-compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE="$(command -v docker-compose)"
else
  DOCKER_COMPOSE=""
fi

echo "[CHECK] PATH=$PATH"
echo "[CHECK] DOCKER_BIN=${DOCKER_BIN}"
echo "[CHECK] DOCKER_COMPOSE=${DOCKER_COMPOSE:-<none>} (ok if empty)"

GIT_SHA="$(git rev-parse --short HEAD)"
IMAGE_TAG="${GIT_SHA}-${BUILD_NUMBER}"
RELEASE_TAG="v${BUILD_NUMBER}.${GIT_SHA}"
echo "[BUILD] IMAGE_TAG=${IMAGE_TAG} | RELEASE_TAG=${RELEASE_TAG}"

# Build with compose if available + compose file exists
if [ -n "${DOCKER_COMPOSE}" ] && { [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; }; then
  echo "[BUILD] Using ${DOCKER_COMPOSE} to build images"
  ${DOCKER_COMPOSE} build --pull --no-cache
else
  echo "[BUILD] No compose available or compose file missing; assuming local images already exist."
fi

echo "[BUILD] Re-tag local images to Docker Hub using dynamic IMAGE_TAG"
${DOCKER_BIN} tag ${LOCAL_IMG_PRODUCT}  ${PRODUCT_IMG}:${IMAGE_TAG}
${DOCKER_BIN} tag ${LOCAL_IMG_PRODUCT}  ${PRODUCT_IMG}:latest

${DOCKER_BIN} tag ${LOCAL_IMG_ORDER}    ${ORDER_IMG}:${IMAGE_TAG}
${DOCKER_BIN} tag ${LOCAL_IMG_ORDER}    ${ORDER_IMG}:latest

${DOCKER_BIN} tag ${LOCAL_IMG_FRONTEND} ${FRONTEND_IMG}:${IMAGE_TAG}
${DOCKER_BIN} tag ${LOCAL_IMG_FRONTEND} ${FRONTEND_IMG}:latest
'''
      }
    }

    // 2) TEST (unit with DB containers + integration for product and order only)
    stage('Test') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail

# ----- Resolve docker & compose -----
DOCKER_BIN=""
if [ -x /usr/local/bin/docker ]; then DOCKER_BIN=/usr/local/bin/docker
elif [ -x /opt/homebrew/bin/docker ]; then DOCKER_BIN=/opt/homebrew/bin/docker
elif command -v docker >/dev/null 2>&1; then DOCKER_BIN="$(command -v docker)"
else
  echo "[ERROR] docker not found"; exit 127
fi

if ${DOCKER_BIN} compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE="${DOCKER_BIN} compose"
elif [ -x /usr/local/bin/docker-compose ]; then
  DOCKER_COMPOSE="/usr/local/bin/docker-compose"
elif [ -x /opt/homebrew/bin/docker-compose ]; then
  DOCKER_COMPOSE="/opt/homebrew/bin/docker-compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE="$(command -v docker-compose)"
else
  DOCKER_COMPOSE=""
fi

command -v python3 >/dev/null 2>&1 || { echo "[ERROR] python3 not found"; exit 127; }

echo "[TEST] Launching Postgres containers for unit tests"
${DOCKER_BIN} rm -f product_db order_db >/dev/null 2>&1 || true

${DOCKER_BIN} run -d --name product_db -p 5432:5432 \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=products \
  postgres:15

${DOCKER_BIN} run -d --name order_db -p 5433:5432 \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=orders \
  postgres:15

echo "[TEST] Waiting for product_db..."
for i in $(seq 1 30); do
  ${DOCKER_BIN} exec product_db pg_isready -U postgres && break || sleep 2
  [ "$i" -eq 30 ] && echo "product_db not ready" && exit 1
done

echo "[TEST] Waiting for order_db..."
for i in $(seq 1 30); do
  ${DOCKER_BIN} exec order_db pg_isready -U postgres && break || sleep 2
  [ "$i" -eq 30 ] && echo "order_db not ready" && exit 1
done

echo "[TEST] Unit tests (product_service)"
py() { python3 -m venv "$1" && . "$1/bin/activate" && pip install -U pip && shift && pip install "$@" ; }

if [ -d ${PRODUCT_DIR} ]; then
  py .venv_prod -r ${PRODUCT_DIR}/requirements.txt || true
  if [ -f ${PRODUCT_DIR}/requirements-dev.txt ]; then . .venv_prod/bin/activate && pip install -r ${PRODUCT_DIR}/requirements-dev.txt; fi
  . .venv_prod/bin/activate
  export POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=products POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
  pytest -q ${PRODUCT_DIR}/tests --junitxml=product_unit.xml
fi

echo "[TEST] Unit tests (order_service)"
if [ -d ${ORDER_DIR} ]; then
  py .venv_order -r ${ORDER_DIR}/requirements.txt || true
  if [ -f ${ORDER_DIR}/requirements-dev.txt ]; then . .venv_order/bin/activate && pip install -r ${ORDER_DIR}/requirements-dev.txt; fi
  . .venv_order/bin/activate
  export POSTGRES_HOST=localhost POSTGRES_PORT=5433 POSTGRES_DB=orders POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
  pytest -q ${ORDER_DIR}/tests --junitxml=order_unit.xml
fi

echo "[TEST] Stopping DB containers after unit tests"
${DOCKER_BIN} rm -f product_db order_db >/dev/null 2>&1 || true

# Integration tests (only if compose exists)
if [ -n "${DOCKER_COMPOSE}" ] && { [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; }; then
  echo "[TEST] Starting integration stack via ${DOCKER_COMPOSE}"
  ${DOCKER_COMPOSE} up -d --remove-orphans
  sleep 10

  echo "[TEST] Integration tests"
  py .venv_int requests pytest
  . .venv_int/bin/activate
  export PRODUCT_BASE=${PRODUCT_BASE:-http://localhost:8000}
  export ORDER_BASE=${ORDER_BASE:-http://localhost:8001}
  pytest -q tests/integration/test_product_integration.py tests/integration/test_order_integration.py --junitxml=integration.xml

  echo "[TEST] Tearing down compose stack"
  ${DOCKER_COMPOSE} down -v
else
  echo "[TEST][WARN] Compose not available; skipping integration tests."
  echo "<testsuite/>" > integration.xml
fi
'''
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'product_unit.xml,order_unit.xml,integration.xml'
        }
      }
    }

    // 3) CODE QUALITY (SonarCloud)
    stage('Code Quality') {
      environment { SONAR_TOKEN = credentials('SONAR_TOKEN') }
      steps {
        withSonarQubeEnv("${SONAR_SERVER_NAME}") {
          script {
            def scannerBin = tool "${SONAR_SCANNER_NAME}"
            withEnv(["PATH+SCANNER=${scannerBin}/bin"]) {
              sh '''#!/usr/bin/env bash
set -euo pipefail

command -v python3 >/dev/null 2>&1 || { echo "[ERROR] python3 not found"; exit 127; }
command -v sonar-scanner >/dev/null 2>&1 || { echo "[ERROR] sonar-scanner not found (check Global Tool Configuration)"; exit 127; }

# Recreate coverage (simple approach)
if [ -d ${PRODUCT_DIR} ]; then
  python3 -m venv .venv_cov_prod
  . .venv_cov_prod/bin/activate
  pip install -U pip pytest pytest-cov -r ${PRODUCT_DIR}/requirements.txt || true
  pytest -q ${PRODUCT_DIR}/tests --cov=${PRODUCT_DIR} --cov-report=xml:cov_prod.xml
fi

if [ -d ${ORDER_DIR} ]; then
  python3 -m venv .venv_cov_order
  . .venv_cov_order/bin/activate
  pip install -U pip pytest pytest-cov -r ${ORDER_DIR}/requirements.txt || true
  pytest -q ${ORDER_DIR}/tests --cov=${ORDER_DIR} --cov-report=xml:cov_order.xml
fi

# pick one coverage file
if [ -f cov_prod.xml ]; then mv cov_prod.xml coverage.xml; fi
if [ -f cov_order.xml ] && [ ! -f coverage.xml ]; then mv cov_order.xml coverage.xml; fi
[ -f coverage.xml ] || echo "<coverage/>" > coverage.xml

GIT_SHA="$(git rev-parse --short HEAD)"
IMAGE_TAG="${GIT_SHA}-${BUILD_NUMBER}"

echo "[QUALITY] SonarScanner (uses sonar-project.properties)"
sonar-scanner \
  -Dsonar.projectVersion="${IMAGE_TAG}" \
  -Dsonar.login="$SONAR_TOKEN"
'''
            }
          }
        }
        timeout(time: 5, unit: 'MINUTES') {
          waitForQualityGate abortPipeline: true
        }
      }
    }

    // 4) SECURITY (Trivy)
    stage('Security') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail

DOCKER_BIN=""
if [ -x /usr/local/bin/docker ]; then DOCKER_BIN=/usr/local/bin/docker
elif [ -x /opt/homebrew/bin/docker ]; then DOCKER_BIN=/opt/homebrew/bin/docker
elif command -v docker >/dev/null 2}&1; then DOCKER_BIN="$(command -v docker)"
else
  echo "[ERROR] docker not found"; exit 127
fi

GIT_SHA="$(git rev-parse --short HEAD)"
IMAGE_TAG="${GIT_SHA}-${BUILD_NUMBER}"

echo "[SECURITY] Trivy fs (source) — fail on HIGH,CRITICAL"
${DOCKER_BIN} run --rm -v "$(pwd)":/src aquasec/trivy:0.55.0 fs --exit-code 1 --severity HIGH,CRITICAL /src

echo "[SECURITY] Trivy image scans — fail on HIGH,CRITICAL"
for img in ${PRODUCT_IMG}:${IMAGE_TAG} ${ORDER_IMG}:${IMAGE_TAG} ${FRONTEND_IMG}:${IMAGE_TAG}; do
  echo "Scanning $img"
  ${DOCKER_BIN} run --rm aquasec/trivy:0.55.0 image --exit-code 1 --severity HIGH,CRITICAL "$img"
done
'''
      }
    }

    // 5) DEPLOY (local Kubernetes)
    stage('Deploy') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail

# Resolve kubectl absolute path
if [ -x /usr/local/bin/kubectl ]; then KUBECTL_BIN=/usr/local/bin/kubectl
elif [ -x /opt/homebrew/bin/kubectl ]; then KUBECTL_BIN=/opt/homebrew/bin/kubectl
elif command -v kubectl >/dev/null 2>&1; then KUBECTL_BIN="$(command -v kubectl)"
else
  echo "[ERROR] kubectl not found"; exit 127
fi

GIT_SHA="$(git rev-parse --short HEAD)"
IMAGE_TAG="${GIT_SHA}-${BUILD_NUMBER}"

echo "[DEPLOY] Local Kubernetes context: ${KUBE_CONTEXT}"
${KUBECTL_BIN} config use-context ${KUBE_CONTEXT}
${KUBECTL_BIN} create namespace ${NAMESPACE} --dry-run=client -o yaml | ${KUBECTL_BIN} apply -f -

for f in configmaps.yaml secrets.yaml product-db.yaml order-db.yaml product-service.yaml order-service.yaml frontend.yaml; do
  if [ -f "${K8S_DIR}/$f" ]; then
    ${KUBECTL_BIN} apply -n ${NAMESPACE} -f "${K8S_DIR}/$f"
  fi
done

${KUBECTL_BIN} set image deploy/product-service product-service=${PRODUCT_IMG}:${IMAGE_TAG} -n ${NAMESPACE} || true
${KUBECTL_BIN} set image deploy/order-service   order-service=${ORDER_IMG}:${IMAGE_TAG}   -n ${NAMESPACE} || true
${KUBECTL_BIN} set image deploy/frontend        frontend=${FRONTEND_IMG}:${IMAGE_TAG}     -n ${NAMESPACE} || true

echo "[DEPLOY] Waiting for rollouts"
${KUBECTL_BIN} rollout status deploy/product-service -n ${NAMESPACE} --timeout=180s || true
${KUBECTL_BIN} rollout status deploy/order-service   -n ${NAMESPACE} --timeout=180s || true
${KUBECTL_BIN} rollout status deploy/frontend        -n ${NAMESPACE} --timeout=180s || true

${KUBECTL_BIN} get all -n ${NAMESPACE}
'''
      }
    }

    // 6) RELEASE (push to Docker Hub + git tag)
    stage('Release') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${DOCKERHUB_CREDS}", usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          sh '''#!/usr/bin/env bash
set -euo pipefail

DOCKER_BIN=""
if [ -x /usr/local/bin/docker ]; then DOCKER_BIN=/usr/local/bin/docker
elif [ -x /opt/homebrew/bin/docker ]; then DOCKER_BIN=/opt/homebrew/bin/docker
elif command -v docker >/dev/null 2>&1; then DOCKER_BIN="$(command -v docker)"
else
  echo "[ERROR] docker not found"; exit 127
fi

GIT_SHA="$(git rev-parse --short HEAD)"
IMAGE_TAG="${GIT_SHA}-${BUILD_NUMBER}"
RELEASE_TAG="v${BUILD_NUMBER}.${GIT_SHA}"

echo "[RELEASE] Login & push dynamic, latest, and immutable tags"
echo "$DH_PASS" | ${DOCKER_BIN} login -u "$DH_USER" --password-stdin

for i in ${PRODUCT_IMG} ${ORDER_IMG} ${FRONTEND_IMG}; do
  ${DOCKER_BIN} push $i:${IMAGE_TAG}
  ${DOCKER_BIN} push $i:latest
done

${DOCKER_BIN} tag ${PRODUCT_IMG}:${IMAGE_TAG}  ${PRODUCT_IMG}:${RELEASE_TAG}
${DOCKER_BIN} tag ${ORDER_IMG}:${IMAGE_TAG}    ${ORDER_IMG}:${RELEASE_TAG}
${DOCKER_BIN} tag ${FRONTEND_IMG}:${IMAGE_TAG} ${FRONTEND_IMG}:${RELEASE_TAG}

for i in ${PRODUCT_IMG} ${ORDER_IMG} ${FRONTEND_IMG}; do
  ${DOCKER_BIN} push $i:${RELEASE_TAG}
done

echo "[RELEASE] Create annotated git tag"
git config user.email "ci@jenkins"
git config user.name  "Jenkins CI"
git tag -a "${RELEASE_TAG}" -m "Release ${RELEASE_TAG}" || true
git push origin "${RELEASE_TAG}" || true
'''
        }
      }
    }

    // 7) MONITORING (post-deploy smoke)
    stage('Monitoring') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail

# kubectl absolute path
if [ -x /usr/local/bin/kubectl ]; then KUBECTL_BIN=/usr/local/bin/kubectl
elif [ -x /opt/homebrew/bin/kubectl ]; then KUBECTL_BIN=/opt/homebrew/bin/kubectl
elif command -v kubectl >/dev/null 2>&1; then KUBECTL_BIN="$(command -v kubectl)"
else
  echo "[ERROR] kubectl not found"; exit 127
fi
command -v curl >/dev/null 2>&1 || { echo "[ERROR] curl not found"; exit 127; }

echo "[MONITOR] Smoke checks via port-forward to /health"

PRODUCT_SVC=$(${KUBECTL_BIN} get svc -n ${NAMESPACE} -l app=product-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
ORDER_SVC=$(${KUBECTL_BIN} get svc -n ${NAMESPACE} -l app=order-service   -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

if [ -n "$PRODUCT_SVC" ]; then
  ${KUBECTL_BIN} port-forward "svc/${PRODUCT_SVC}" 18000:8000 -n ${NAMESPACE} >/tmp/pf_prod.log 2>&1 &
  PF1=$!; sleep 3
  curl -fsS http://localhost:18000/health || { echo "Product /health failed"; kill "$PF1" || true; exit 1; }
  kill "$PF1" || true
fi

if [ -n "$ORDER_SVC" ]; then
  ${KUBECTL_BIN} port-forward "svc/${ORDER_SVC}" 18001:8001 -n ${NAMESPACE} >/tmp/pf_order.log 2>&1 &
  PF2=$!; sleep 3
  curl -fsS http://localhost:18001/health || { echo "Order /health failed"; kill "$PF2" || true; exit 1; }
  kill "$PF2" || true
fi
'''
      }
    }
  }

  post {
    success { echo "Pipeline succeeded." }
    failure { echo "Pipeline failed - see logs." }
    always  { echo "Pipeline completed." }
  }
}