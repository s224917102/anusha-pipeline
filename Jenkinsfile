pipeline {
  agent any

  options {
    disableConcurrentBuilds()
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    // PATH for typical macOS Jenkins agent
    PATH = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

    // Docker Hub + image names
    DOCKERHUB_NS    = 's224917102'
    DOCKERHUB_CREDS = 'dockerhub-s224917102'
    REGISTRY        = 'docker.io'
    PRODUCT_IMG     = "${REGISTRY}/${DOCKERHUB_NS}/product_service"
    ORDER_IMG       = "${REGISTRY}/${DOCKERHUB_NS}/order_service"
    FRONTEND_IMG    = "${REGISTRY}/${DOCKERHUB_NS}/frontend"

    // Local images built by compose
    LOCAL_IMG_PRODUCT  = 'week09_example02_product_service:latest'
    LOCAL_IMG_ORDER    = 'week09_example02_order_service:latest'
    LOCAL_IMG_FRONTEND = 'week09_example02_frontend:latest'

    // K8s (if/when you deploy)
    KUBE_CONTEXT  = 'docker-desktop'
    NAMESPACE     = 'default'
    K8S_DIR       = 'k8s'

    // SonarQube
    SONARQUBE = 'SonarQube'
    SCANNER   = 'SonarScanner'   // kept for completeness; we run scanner in Docker
    SONAR_PROJECT_KEY  = 's224917102_DevOpsPipeline'
    SONAR_PROJECT_NAME = 'DevOpsPipeline'
    SONAR_SOURCES      = '.'

    // Paths
    PRODUCT_DIR  = 'backend/product_service'
    ORDER_DIR    = 'backend/order_service'
    FRONTEND_DIR = 'frontend'
  }

  stages {

    stage('Build') {
      steps {
        checkout scm

        script {
          env.GIT_SHA     = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
          env.IMAGE_TAG   = "${env.GIT_SHA}-${env.BUILD_NUMBER}"
          env.RELEASE_TAG = "v${env.BUILD_NUMBER}.${env.GIT_SHA}"
          echo "[BUILD] Computed IMAGE_TAG=${env.IMAGE_TAG} | RELEASE_TAG=${env.RELEASE_TAG}"
        }

        sh '''#!/usr/bin/env bash
          set -euo pipefail
          echo "[CHECK] PATH=$PATH"
          echo "[CHECK] docker=$(command -v docker || true)"
          echo "[CHECK] docker compose=$(docker compose version | head -1 || true)"
          echo "[CHECK] kubectl=$(command -v kubectl || true)"

          if [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; then
            echo "[BUILD] Using docker compose to build images"
            docker compose build --pull
          else
            echo "[BUILD] No docker-compose file found; skipping compose build."
          fi

          echo "[BUILD] Re-tag local images → Docker Hub names"
          docker image inspect ${LOCAL_IMG_PRODUCT}  >/dev/null
          docker image inspect ${LOCAL_IMG_ORDER}    >/dev/null
          docker image inspect ${LOCAL_IMG_FRONTEND} >/dev/null

          docker tag ${LOCAL_IMG_PRODUCT}  ${PRODUCT_IMG}:${IMAGE_TAG}
          docker tag ${LOCAL_IMG_PRODUCT}  ${PRODUCT_IMG}:latest

          docker tag ${LOCAL_IMG_ORDER}    ${ORDER_IMG}:${IMAGE_TAG}
          docker tag ${LOCAL_IMG_ORDER}    ${ORDER_IMG}:latest

          docker tag ${LOCAL_IMG_FRONTEND} ${FRONTEND_IMG}:${IMAGE_TAG}
          docker tag ${LOCAL_IMG_FRONTEND} ${FRONTEND_IMG}:latest
        '''
      }
    }

    stage('Test') {
      options { timeout(time: 25, unit: 'MINUTES') }
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail

          echo "[TEST][UNIT] Clean old DBs"
          docker rm -f product_db order_db >/dev/null 2>&1 || true

          echo "[TEST][UNIT] Start Postgres"
          docker run -d --name product_db -p 5432:5432 \
            -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=products \
            postgres:15
          docker run -d --name order_db -p 5433:5432 \
            -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=orders \
            postgres:15

          echo "[TEST][UNIT] Wait for DBs"
          for name in product_db order_db; do
            for i in $(seq 1 30); do
              if docker exec "$name" pg_isready -U postgres >/dev/null 2>&1; then
                echo " - $name ready"
                break
              fi
              sleep 2
              if [ "$i" -eq 30 ]; then
                echo "ERROR: $name not ready after 60s"
                docker logs "$name" || true
                exit 1
              fi
            done
          done

          py() { python3 -m venv "$1" && . "$1/bin/activate" && python -m pip install -U pip wheel >/dev/null; }

          echo "[TEST][UNIT] Product"
          if [ -d ${PRODUCT_DIR} ]; then
            py .venv_prod
            . .venv_prod/bin/activate
            python -m pip install -r ${PRODUCT_DIR}/requirements.txt >/dev/null
            if [ -f ${PRODUCT_DIR}/requirements-dev.txt ]; then
              python -m pip install -r ${PRODUCT_DIR}/requirements-dev.txt >/dev/null
            fi
            python -m pip install "pytest>=8,<9" "pytest-timeout==2.3.1" >/dev/null
            echo "[CHECK] pytest-timeout present:"
            python - <<'PY'
import importlib.util
print(importlib.util.find_spec("pytest_timeout") is not None)
PY
            export POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=products POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            pytest -p pytest_timeout ${PRODUCT_DIR}/tests --junitxml=product_unit.xml -q --maxfail=1 --timeout=60 --timeout-method=thread
          fi

          echo "[TEST][UNIT] Order"
          if [ -d ${ORDER_DIR} ]; then
            py .venv_order
            . .venv_order/bin/activate
            python -m pip install -r ${ORDER_DIR}/requirements.txt >/dev/null
            if [ -f ${ORDER_DIR}/requirements-dev.txt ]; then
              python -m pip install -r ${ORDER_DIR}/requirements-dev.txt >/dev/null
            fi
            python -m pip install "pytest>=8,<9" "pytest-timeout==2.3.1" >/dev/null
            echo "[CHECK] pytest-timeout present:"
            python - <<'PY'
import importlib.util
print(importlib.util.find_spec("pytest_timeout") is not None)
PY
            export POSTGRES_HOST=localhost POSTGRES_PORT=5433 POSTGRES_DB=orders POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            pytest -p pytest_timeout ${ORDER_DIR}/tests --junitxml=order_unit.xml -q --maxfail=1 --timeout=60 --timeout-method=thread
          fi

          echo "[TEST][INTEG] Compose up (services + DBs) for integration tests"
          if [ -d tests/integration ]; then
            # Make sure placeholder env vars exist for product service (Azure mocks use these)
            export AZURE_STORAGE_ACCOUNT_NAME="localtest"
            export AZURE_STORAGE_ACCOUNT_KEY="localkey"
            export AZURE_STORAGE_CONTAINER_NAME="images"
            export AZURE_SAS_TOKEN_EXPIRY_HOURS="1"

            docker compose up -d --remove-orphans

            echo "[TEST][INTEG] Wait for product service /health"
            for i in $(seq 1 60); do
              if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
                echo " - product_service is up"
                break
              fi
              sleep 2
              if [ "$i" -eq 60 ]; then
                echo "ERROR: product_service didn't become healthy"
                docker compose logs product_service || true
                docker compose down -v || true
                exit 1
              fi
            done

            py .venv_int
            . .venv_int/bin/activate
            python -m pip install "pytest>=8,<9" "pytest-timeout==2.3.1" requests >/dev/null
            echo "[CHECK] pytest-timeout present:"
            python - <<'PY'
import importlib.util
print(importlib.util.find_spec("pytest_timeout") is not None)
PY
            export PRODUCT_BASE="http://localhost:8000"
            export ORDER_BASE="http://localhost:8001"
            pytest -p pytest_timeout tests/integration --junitxml=integration.xml -q --maxfail=1 --timeout=90 --timeout-method=thread || (docker compose down -v || true; exit 1)

            docker compose down -v || true
          else
            echo "[TEST][INTEG] No tests/integration directory — skipping."
          fi
        '''
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'product_unit.xml,order_unit.xml,integration.xml'
          sh 'docker rm -f product_db order_db >/dev/null 2>&1 || true'
        }
      }
    }

    stage('Code Quality') {
      steps {
        withSonarQubeEnv("${SONARQUBE}") {
          sh '''#!/usr/bin/env bash
            set -euo pipefail
            echo "[QUALITY] Sonar analysis (Dockerized scanner includes Java)"
            docker run --rm \
              -e SONAR_HOST_URL="$SONAR_HOST_URL" \
              -e SONAR_TOKEN="$SONAR_AUTH_TOKEN" \
              -v "$PWD:/usr/src" \
              -w /usr/src \
              sonarsource/sonar-scanner-cli:latest \
              -Dsonar.projectKey=${SONAR_PROJECT_KEY} \
              -Dsonar.projectName="${SONAR_PROJECT_NAME}" \
              -Dsonar.projectVersion=${IMAGE_TAG} \
              -Dsonar.sources=${SONAR_SOURCES} \
              -Dsonar.python.version=3.10 \
              -Dsonar.exclusions=**/.git/**,**/__pycache__/**,**/.venv/**,**/*.png,**/*.jpg,**/*.svg \
              -Dsonar.tests=${PRODUCT_DIR}/tests,${ORDER_DIR}/tests \
              -Dsonar.test.inclusions=**/tests/**
          '''
        }
      }
    }

    stage('Security') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail
          echo "[SECURITY] Trivy fs"
          docker run --rm -v "$(pwd)":/src aquasec/trivy:0.55.0 fs --exit-code 1 --severity HIGH,CRITICAL /src
          echo "[SECURITY] Trivy images"
          for img in ${PRODUCT_IMG}:${IMAGE_TAG} ${ORDER_IMG}:${IMAGE_TAG} ${FRONTEND_IMG}:${IMAGE_TAG}; do
            docker run --rm aquasec/trivy:0.55.0 image --exit-code 1 --severity HIGH,CRITICAL "$img"
          done
        '''
      }
    }

    stage('Deploy') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail
          echo "[DEPLOY] Context ${KUBE_CONTEXT}"
          kubectl config use-context ${KUBE_CONTEXT}
          kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

          for f in configmaps.yaml secrets.yaml product-db.yaml order-db.yaml product-service.yaml order-service.yaml frontend.yaml; do
            [ -f "${K8S_DIR}/$f" ] && kubectl apply -n ${NAMESPACE} -f "${K8S_DIR}/$f" || true
          done

          kubectl set image deploy/product-service product-service=${PRODUCT_IMG}:${IMAGE_TAG} -n ${NAMESPACE} || true
          kubectl set image deploy/order-service   order-service=${ORDER_IMG}:${IMAGE_TAG}   -n ${NAMESPACE} || true
          kubectl set image deploy/frontend        frontend=${FRONTEND_IMG}:${IMAGE_TAG}     -n ${NAMESPACE} || true

          kubectl rollout status deploy/product-service -n ${NAMESPACE} --timeout=180s || true
          kubectl rollout status deploy/order-service   -n ${NAMESPACE} --timeout=180s || true
          kubectl rollout status deploy/frontend        -n ${NAMESPACE} --timeout=180s || true
        '''
      }
    }

    stage('Release') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${DOCKERHUB_CREDS}", usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          sh '''#!/usr/bin/env bash
            set -euo pipefail
            echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin
            for i in ${PRODUCT_IMG} ${ORDER_IMG} ${FRONTEND_IMG}; do
              docker push $i:${IMAGE_TAG}
              docker push $i:latest
            done
            docker tag ${PRODUCT_IMG}:${IMAGE_TAG}  ${PRODUCT_IMG}:${RELEASE_TAG}
            docker tag ${ORDER_IMG}:${IMAGE_TAG}    ${ORDER_IMG}:${RELEASE_TAG}
            docker tag ${FRONTEND_IMG}:${IMAGE_TAG} ${FRONTEND_IMG}:${RELEASE_TAG}
            for i in ${PRODUCT_IMG} ${ORDER_IMG} ${FRONTEND_IMG}; do
              docker push $i:${RELEASE_TAG}
            done

            git config user.email "ci@jenkins"
            git config user.name  "Jenkins CI"
            git tag -a "${RELEASE_TAG}" -m "Release ${RELEASE_TAG}" || true
            git push origin "${RELEASE_TAG}" || true
          '''
        }
      }
    }

    stage('Monitoring') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail
          echo "[MONITOR] Quick health checks (if services exist)"
          PRODUCT_SVC=$(kubectl get svc -n ${NAMESPACE} -l app=product-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
          ORDER_SVC=$(kubectl get svc -n ${NAMESPACE} -l app=order-service   -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

          if [ -n "$PRODUCT_SVC" ]; then
            kubectl port-forward svc/${PRODUCT_SVC} 18000:8000 -n ${NAMESPACE} >/tmp/pf_prod.log 2>&1 &
            PF1=$!; sleep 3
            curl -fsS http://localhost:18000/health || (echo "Product /health failed" && kill $PF1 || true && exit 1)
            kill $PF1 || true
          fi

          if [ -n "$ORDER_SVC" ]; then
            kubectl port-forward svc/${ORDER_SVC} 18001:8001 -n ${NAMESPACE} >/tmp/pf_order.log 2>&1 &
            PF2=$!; sleep 3
            curl -fsS http://localhost:18001/health || (echo "Order /health failed" && kill $PF2 || true && exit 1)
            kill $PF2 || true
          fi
        '''
      }
    }
  }

  post {
    success { echo "Pipeline succeeded - ${IMAGE_TAG} (${RELEASE_TAG})" }
    failure { echo "Pipeline failed - see logs." }
    always  { echo "Pipeline completed." }
  }
}
