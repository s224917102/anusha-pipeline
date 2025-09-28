pipeline {
  agent any

  options {
    disableConcurrentBuilds()
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  triggers {
    pollSCM('H/2 * * * *')   // every ~2 minutes
  }

  environment {
    // ===== Fixed tool paths on your Mac =====
    // Adjust here if your binaries live elsewhere.
    DOCKER_BIN  = '/usr/local/bin/docker'
    KUBECTL_BIN = '/usr/local/bin/kubectl'
    SAFE_PATH   = '/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin'

    // ===== Docker Hub =====
    DOCKERHUB_NS    = 's224917102'
    DOCKERHUB_CREDS = 'dockerhub-s224917102'
    REGISTRY        = 'docker.io'
    PRODUCT_IMG     = "${REGISTRY}/${DOCKERHUB_NS}/product_service"
    ORDER_IMG       = "${REGISTRY}/${DOCKERHUB_NS}/order_service"
    FRONTEND_IMG    = "${REGISTRY}/${DOCKERHUB_NS}/frontend"

    // ===== Local images from docker compose build (no localhost/ prefix) =====
    LOCAL_IMG_PRODUCT  = 'week09_example02_product_service:latest'
    LOCAL_IMG_ORDER    = 'week09_example02_order_service:latest'
    LOCAL_IMG_FRONTEND = 'week09_example02_frontend:latest'

    // ===== K8s (local) =====
    KUBE_CONTEXT  = 'docker-desktop'
    NAMESPACE     = 'default'
    K8S_DIR       = 'k8s'

    // ===== SonarQube/SonarCloud =====
    SONARQUBE = 'SonarQube'
    SCANNER   = 'SonarScanner'
    SONAR_PROJECT_KEY  = 'sit753-anusha'
    SONAR_PROJECT_NAME = 'SIT753 Microservices'
    SONAR_SOURCES      = '.'
  }

  stages {

    stage('Build') {
      steps {
        checkout scm
        sh '''
          set -e
          export PATH="${SAFE_PATH}"
          echo "[CHECK] PATH=$PATH"
          echo "[CHECK] docker=$(command -v "${DOCKER_BIN}" || true)"
          echo "[CHECK] kubectl=$(command -v "${KUBECTL_BIN}" || true)"
          "${DOCKER_BIN}" compose version | head -1 || true

          GIT_SHA="$(git rev-parse --short HEAD)"
          IMAGE_TAG="${GIT_SHA}-${BUILD_NUMBER}"
          RELEASE_TAG="v${BUILD_NUMBER}.${GIT_SHA}"
          printf "IMAGE_TAG=%s\nRELEASE_TAG=%s\n" "$IMAGE_TAG" "$RELEASE_TAG" > .ci_env
          echo "[BUILD] IMAGE_TAG=$IMAGE_TAG | RELEASE_TAG=$RELEASE_TAG"

          if [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; then
            echo "[BUILD] docker compose build --pull"
            "${DOCKER_BIN}" compose build --pull
          else
            echo "[BUILD] No compose file found; skipping build."
          fi

          # Re-tag local images to Docker Hub using dynamic tag
          . ./.ci_env
          set -eu
          "${DOCKER_BIN}" tag ${LOCAL_IMG_PRODUCT}  ${PRODUCT_IMG}:${IMAGE_TAG}
          "${DOCKER_BIN}" tag ${LOCAL_IMG_PRODUCT}  ${PRODUCT_IMG}:latest
          "${DOCKER_BIN}" tag ${LOCAL_IMG_ORDER}    ${ORDER_IMG}:${IMAGE_TAG}
          "${DOCKER_BIN}" tag ${LOCAL_IMG_ORDER}    ${ORDER_IMG}:latest
          "${DOCKER_BIN}" tag ${LOCAL_IMG_FRONTEND} ${FRONTEND_IMG}:${IMAGE_TAG}
          "${DOCKER_BIN}" tag ${LOCAL_IMG_FRONTEND} ${FRONTEND_IMG}:latest
        '''
      }
    }

    stage('Test') {
      steps {
        sh '''
          set -euo pipefail
          export PATH="${SAFE_PATH}"
          . ./.ci_env

          echo "[TEST] Starting DB containers"
          "${DOCKER_BIN}" rm -f product_db order_db >/dev/null 2>&1 || true

          "${DOCKER_BIN}" run -d --name product_db -p 5432:5432 \
            -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=products \
            postgres:15

          "${DOCKER_BIN}" run -d --name order_db -p 5433:5432 \
            -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=orders \
            postgres:15

          echo "[TEST] Waiting for Postgres"
          for i in $(seq 1 30); do "${DOCKER_BIN}" exec product_db pg_isready -U postgres && break || sleep 2; [ $i -eq 30 ] && exit 1; done
          for i in $(seq 1 30); do "${DOCKER_BIN}" exec order_db   pg_isready -U postgres && break || sleep 2; [ $i -eq 30 ] && exit 1; done

          py() { python3 -m venv "$1" && . "$1/bin/activate" && pip install -U pip && shift && pip install "$@" ; }

          # product_service unit
          if [ -d backend/product_service ]; then
            py .venv_prod -r backend/product_service/requirements.txt || true
            [ -f backend/product_service/requirements-dev.txt ] && . .venv_prod/bin/activate && pip install -r backend/product_service/requirements-dev.txt || true
            . .venv_prod/bin/activate
            export POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=products POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            pytest -q backend/product_service/tests --junitxml=product_unit.xml
          fi

          # order_service unit
          if [ -d backend/order_service ]; then
            py .venv_order -r backend/order_service/requirements.txt || true
            [ -f backend/order_service/requirements-dev.txt ] && . .venv_order/bin/activate && pip install -r backend/order_service/requirements-dev.txt || true
            . .venv_order/bin/activate
            export POSTGRES_HOST=localhost POSTGRES_PORT=5433 POSTGRES_DB=orders POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            pytest -q backend/order_service/tests --junitxml=order_unit.xml
          fi

          echo "[TEST] Stop DB containers"
          "${DOCKER_BIN}" rm -f product_db order_db >/dev/null 2>&1 || true

          echo "[TEST] Integration with docker compose"
          "${DOCKER_BIN}" compose up -d --remove-orphans
          sleep 10

          py .venv_int requests pytest
          . .venv_int/bin/activate
          export PRODUCT_BASE=${PRODUCT_BASE:-http://localhost:8000}
          export ORDER_BASE=${ORDER_BASE:-http://localhost:8001}
          pytest -q tests/integration/test_product_integration.py tests/integration/test_order_integration.py --junitxml=integration.xml

          echo "[TEST] Tear down"
          "${DOCKER_BIN}" compose down -v
        '''
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'product_unit.xml,order_unit.xml,integration.xml'
        }
      }
    }

    stage('Code Quality') {
      steps {
        withSonarQubeEnv("${SONARQUBE}") {
          withEnv(["PATH+SCANNER=${tool SCANNER}/bin:${env.SAFE_PATH}"]) {
            sh '''
              set -euo pipefail
              export PATH="${SAFE_PATH}:${PATH}"
              . ./.ci_env
              echo "[QUALITY] Sonar analysis"
              sonar-scanner \
                -Dsonar.projectKey=${SONAR_PROJECT_KEY} \
                -Dsonar.projectName="${SONAR_PROJECT_NAME}" \
                -Dsonar.projectVersion=${IMAGE_TAG} \
                -Dsonar.sources=${SONAR_SOURCES} \
                -Dsonar.python.version=3.10 \
                -Dsonar.exclusions=**/.git/**,**/__pycache__/**,**/.venv/**,**/*.png,**/*.jpg,**/*.svg \
                -Dsonar.tests=backend/product_service/tests,backend/order_service/tests \
                -Dsonar.test.inclusions=**/tests/**
            '''
          }
        }
      }
    }

    stage('Security') {
      steps {
        sh '''
          set -euo pipefail
          export PATH="${SAFE_PATH}"
          . ./.ci_env
          echo "[SECURITY] Trivy fs scan"
          "${DOCKER_BIN}" run --rm -v "$(pwd)":/src aquasec/trivy:0.55.0 fs --exit-code 1 --severity HIGH,CRITICAL /src

          echo "[SECURITY] Trivy image scans"
          for img in ${PRODUCT_IMG}:${IMAGE_TAG} ${ORDER_IMG}:${IMAGE_TAG} ${FRONTEND_IMG}:${IMAGE_TAG}; do
            echo "Scanning $img"
            "${DOCKER_BIN}" run --rm aquasec/trivy:0.55.0 image --exit-code 1 --severity HIGH,CRITICAL "$img"
          done
        '''
      }
    }

    stage('Deploy') {
      steps {
        sh '''
          set -euo pipefail
          export PATH="${SAFE_PATH}"
          . ./.ci_env
          echo "[DEPLOY] Using context ${KUBE_CONTEXT}"
          "${KUBECTL_BIN}" config use-context ${KUBE_CONTEXT}
          "${KUBECTL_BIN}" create namespace ${NAMESPACE} --dry-run=client -o yaml | "${KUBECTL_BIN}" apply -f -

          for f in configmaps.yaml secrets.yaml product-db.yaml order-db.yaml product-service.yaml order-service.yaml frontend.yaml; do
            [ -f "${K8S_DIR}/$f" ] && "${KUBECTL_BIN}" apply -n ${NAMESPACE} -f "${K8S_DIR}/$f" || true
          done

          "${KUBECTL_BIN}" set image deploy/product-service product-service=${PRODUCT_IMG}:${IMAGE_TAG} -n ${NAMESPACE} || true
          "${KUBECTL_BIN}" set image deploy/order-service   order-service=${ORDER_IMG}:${IMAGE_TAG}   -n ${NAMESPACE} || true
          "${KUBECTL_BIN}" set image deploy/frontend        frontend=${FRONTEND_IMG}:${IMAGE_TAG}     -n ${NAMESPACE} || true

          "${KUBECTL_BIN}" rollout status deploy/product-service -n ${NAMESPACE} --timeout=180s || true
          "${KUBECTL_BIN}" rollout status deploy/order-service   -n ${NAMESPACE} --timeout=180s || true
          "${KUBECTL_BIN}" rollout status deploy/frontend        -n ${NAMESPACE} --timeout=180s || true

          "${KUBECTL_BIN}" get all -n ${NAMESPACE}
        '''
      }
    }

    stage('Release') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${DOCKERHUB_CREDS}", usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          sh '''
            set -euo pipefail
            export PATH="${SAFE_PATH}"
            . ./.ci_env

            echo "[RELEASE] Login & push"
            echo "$DH_PASS" | "${DOCKER_BIN}" login -u "$DH_USER" --password-stdin

            for i in ${PRODUCT_IMG} ${ORDER_IMG} ${FRONTEND_IMG}; do
              "${DOCKER_BIN}" push $i:${IMAGE_TAG}
              "${DOCKER_BIN}" push $i:latest
            done

            "${DOCKER_BIN}" tag ${PRODUCT_IMG}:${IMAGE_TAG}  ${PRODUCT_IMG}:${RELEASE_TAG}
            "${DOCKER_BIN}" tag ${ORDER_IMG}:${IMAGE_TAG}    ${ORDER_IMG}:${RELEASE_TAG}
            "${DOCKER_BIN}" tag ${FRONTEND_IMG}:${IMAGE_TAG} ${FRONTEND_IMG}:${RELEASE_TAG}
            for i in ${PRODUCT_IMG} ${ORDER_IMG} ${FRONTEND_IMG}; do
              "${DOCKER_BIN}" push $i:${RELEASE_TAG}
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
        sh '''
          set -euo pipefail
          export PATH="${SAFE_PATH}"
          . ./.ci_env
          echo "[MONITOR] Port-forward + /health"

          PRODUCT_SVC=$("${KUBECTL_BIN}" get svc -n ${NAMESPACE} -l app=product-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
          ORDER_SVC=$("${KUBECTL_BIN}" get svc -n ${NAMESPACE} -l app=order-service   -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

          if [ -n "$PRODUCT_SVC" ]; then
            "${KUBECTL_BIN}" port-forward svc/${PRODUCT_SVC} 18000:8000 -n ${NAMESPACE} >/tmp/pf_prod.log 2>&1 &
            PF1=$!; sleep 3
            curl -fsS http://localhost:18000/health || (echo "Product /health failed" && kill $PF1 || true && exit 1)
            kill $PF1 || true
          fi

          if [ -n "$ORDER_SVC" ]; then
            "${KUBECTL_BIN}" port-forward svc/${ORDER_SVC} 18001:8001 -n ${NAMESPACE} >/tmp/pf_order.log 2>&1 &
            PF2=$!; sleep 3
            curl -fsS http://localhost:18001/health || (echo "Order /health failed" && kill $PF2 || true && exit 1)
            kill $PF2 || true
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
