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
    // ===== Registry (Docker Hub) =====
    DOCKERHUB_NS    = 's224917102'
    DOCKERHUB_CREDS = 'dockerhub-s224917102'
    REGISTRY        = 'docker.io'
    PRODUCT_IMG     = "${REGISTRY}/${DOCKERHUB_NS}/product_service"
    ORDER_IMG       = "${REGISTRY}/${DOCKERHUB_NS}/order_service"
    FRONTEND_IMG    = "${REGISTRY}/${DOCKERHUB_NS}/frontend"

    // ===== Local images (built by docker compose) =====
    LOCAL_IMG_PRODUCT  = 'localhost/week09_example02_product_service:latest'
    LOCAL_IMG_ORDER    = 'localhost/week09_example02_order_service:latest'
    LOCAL_IMG_FRONTEND = 'localhost/week09_example02_frontend:latest'

    // ===== K8s (local) =====
    KUBE_CONTEXT  = 'docker-desktop'   // or 'minikube'
    NAMESPACE     = 'default'
    K8S_DIR       = 'k8s'

    // ===== SonarCloud (names must match Jenkins global config) =====
    SONAR_SERVER_NAME = 'SonarQube'    // Manage Jenkins → System → SonarQube servers (name)
    SONAR_SCANNER_NAME = 'SonarScanner'// Manage Jenkins → Global Tool Configuration (tool name)

    // ===== Project paths =====
    PRODUCT_DIR  = 'backend/product_service'
    ORDER_DIR    = 'backend/order_service'
    FRONTEND_DIR = 'frontend'

    // ===== Derived at runtime =====
    GIT_SHA     = ''
    IMAGE_TAG   = ''     // <sha>-<build>   (e.g., e0f281c-42)
    RELEASE_TAG = ''     // v<build>.<sha>  (e.g., v42.e0f281c)
  }

  stages {

    // 1) BUILD
    stage('Build') {
      steps {
        checkout scm
        script {
          env.GIT_SHA     = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
          env.IMAGE_TAG   = "${env.GIT_SHA}-${env.BUILD_NUMBER}"
          env.RELEASE_TAG = "v${env.BUILD_NUMBER}.${env.GIT_SHA}"
        }
        sh '''
          set -euo pipefail
          echo "[BUILD] IMAGE_TAG=${IMAGE_TAG} | RELEASE_TAG=${RELEASE_TAG}"

          if [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; then
            docker compose build --pull --no-cache || docker-compose build --pull --no-cache
          else
            echo "[BUILD] No docker-compose file found; assuming local images already exist."
          fi

          echo "[BUILD] Re-tag local images to Docker Hub using dynamic IMAGE_TAG"
          docker tag ${LOCAL_IMG_PRODUCT}  ${PRODUCT_IMG}:${IMAGE_TAG}
          docker tag ${LOCAL_IMG_PRODUCT}  ${PRODUCT_IMG}:latest

          docker tag ${LOCAL_IMG_ORDER}    ${ORDER_IMG}:${IMAGE_TAG}
          docker tag ${LOCAL_IMG_ORDER}    ${ORDER_IMG}:latest

          docker tag ${LOCAL_IMG_FRONTEND} ${FRONTEND_IMG}:${IMAGE_TAG}
          docker tag ${LOCAL_IMG_FRONTEND} ${FRONTEND_IMG}:latest
        '''
      }
    }

    // 2) TEST (unit + integration for product and order only)
    stage('Test') {
      steps {
        sh '''
          set -euo pipefail
          echo "[TEST] Launching Postgres containers for unit tests"

          docker rm -f product_db order_db >/dev/null 2>&1 || true

          docker run -d --name product_db -p 5432:5432 \
            -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=products \
            postgres:15

          docker run -d --name order_db -p 5433:5432 \
            -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=orders \
            postgres:15

          echo "[TEST] Waiting for product_db..."
          for i in $(seq 1 30); do
            docker exec product_db pg_isready -U postgres && break || sleep 2
            [ $i -eq 30 ] && echo "product_db not ready" && exit 1
          done

          echo "[TEST] Waiting for order_db..."
          for i in $(seq 1 30); do
            docker exec order_db pg_isready -U postgres && break || sleep 2
            [ $i -eq 30 ] && echo "order_db not ready" && exit 1
          done

          echo "[TEST] Unit tests (product_service)"
          py() { python3 -m venv "$1" && . "$1/bin/activate" && pip install -U pip && shift && pip install "$@" ; }

          if [ -d ${PRODUCT_DIR} ]; then
            py .venv_prod -r ${PRODUCT_DIR}/requirements.txt || true
            [ -f ${PRODUCT_DIR}/requirements-dev.txt ] && . .venv_prod/bin/activate && pip install -r ${PRODUCT_DIR}/requirements-dev.txt || true
            . .venv_prod/bin/activate
            export POSTGRES_HOST=localhost
            export POSTGRES_PORT=5432
            export POSTGRES_DB=products
            export POSTGRES_USER=postgres
            export POSTGRES_PASSWORD=postgres
            pytest -q ${PRODUCT_DIR}/tests --junitxml=product_unit.xml
          fi

          echo "[TEST] Unit tests (order_service)"
          if [ -d ${ORDER_DIR} ]; then
            py .venv_order -r ${ORDER_DIR}/requirements.txt || true
            [ -f ${ORDER_DIR}/requirements-dev.txt ] && . .venv_order/bin/activate && pip install -r ${ORDER_DIR}/requirements-dev.txt || true
            . .venv_order/bin/activate
            export POSTGRES_HOST=localhost
            export POSTGRES_PORT=5433
            export POSTGRES_DB=orders
            export POSTGRES_USER=postgres
            export POSTGRES_PASSWORD=postgres
            pytest -q ${ORDER_DIR}/tests --junitxml=order_unit.xml
          fi

          echo "[TEST] Stopping DB containers after unit tests"
          docker rm -f product_db order_db >/dev/null 2>&1 || true

          echo "[TEST] Starting integration stack via docker-compose (product & order)"
          docker compose up -d --remove-orphans || docker-compose up -d --remove-orphans
          sleep 10

          echo "[TEST] Integration tests"
          py .venv_int requests pytest
          . .venv_int/bin/activate

          export PRODUCT_BASE=${PRODUCT_BASE:-http://localhost:8000}
          export ORDER_BASE=${ORDER_BASE:-http://localhost:8001}

          pytest -q tests/integration/test_product_integration.py tests/integration/test_order_integration.py --junitxml=integration.xml

          echo "[TEST] Tearing down compose stack"
          docker compose down -v || docker-compose down -v
        '''
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'product_unit.xml,order_unit.xml,integration.xml'
        }
      }
    }

    // 3) CODE QUALITY (SonarCloud scan + Quality Gate)
    stage('Code Quality') {
      environment { SONAR_TOKEN = credentials('SONAR_TOKEN') }
      steps {
        withSonarQubeEnv("${SONAR_SERVER_NAME}") {
          script {
            def scannerBin = tool "${SONAR_SCANNER_NAME}"
            withEnv(["PATH+SCANNER=${scannerBin}/bin"]) {
              sh '''
                set -euo pipefail
                echo "[QUALITY] Generate coverage for SonarCloud"

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

                # choose one coverage file (simple approach)
                if [ -f cov_prod.xml ]; then mv cov_prod.xml coverage.xml; fi
                if [ -f cov_order.xml ] && [ ! -f coverage.xml ]; then mv cov_order.xml coverage.xml; fi
                [ -f coverage.xml ] || echo "<coverage/>" > coverage.xml

                echo "[QUALITY] Run SonarScanner (sonar-project.properties supplies keys)"
                sonar-scanner \
                  -Dsonar.projectVersion=${IMAGE_TAG} \
                  -Dsonar.login=$SONAR_TOKEN
              '''
            }
          }
        }
        // Keep Quality Gate wait here to maintain 7 total stages
        timeout(time: 5, unit: 'MINUTES') {
          waitForQualityGate abortPipeline: true
        }
      }
    }

    // 4) SECURITY (Trivy)
    stage('Security') {
      steps {
        sh '''
          set -euo pipefail
          echo "[SECURITY] Trivy fs (source) — fail on HIGH,CRITICAL"
          docker run --rm -v "$(pwd)":/src aquasec/trivy:0.55.0 fs --exit-code 1 --severity HIGH,CRITICAL /src

          echo "[SECURITY] Trivy image scans — fail on HIGH,CRITICAL"
          for img in ${PRODUCT_IMG}:${IMAGE_TAG} ${ORDER_IMG}:${IMAGE_TAG} ${FRONTEND_IMG}:${IMAGE_TAG}; do
            echo "Scanning $img"
            docker run --rm aquasec/trivy:0.55.0 image --exit-code 1 --severity HIGH,CRITICAL "$img"
          done
        '''
      }
    }

    // 5) DEPLOY (local Kubernetes)
    stage('Deploy') {
      steps {
        sh '''
          set -euo pipefail
          echo "[DEPLOY] Local Kubernetes context: ${KUBE_CONTEXT}"
          kubectl config use-context ${KUBE_CONTEXT}
          kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

          for f in configmaps.yaml secrets.yaml product-db.yaml order-db.yaml product-service.yaml order-service.yaml frontend.yaml; do
            [ -f "${K8S_DIR}/$f" ] && kubectl apply -n ${NAMESPACE} -f "${K8S_DIR}/$f" || true
          done

          kubectl set image deploy/product-service product-service=${PRODUCT_IMG}:${IMAGE_TAG} -n ${NAMESPACE} || true
          kubectl set image deploy/order-service   order-service=${ORDER_IMG}:${IMAGE_TAG}   -n ${NAMESPACE} || true
          kubectl set image deploy/frontend        frontend=${FRONTEND_IMG}:${IMAGE_TAG}     -n ${NAMESPACE} || true

          echo "[DEPLOY] Waiting for rollouts"
          kubectl rollout status deploy/product-service -n ${NAMESPACE} --timeout=180s || true
          kubectl rollout status deploy/order-service   -n ${NAMESPACE} --timeout=180s || true
          kubectl rollout status deploy/frontend        -n ${NAMESPACE} --timeout=180s || true

          kubectl get all -n ${NAMESPACE}
        '''
      }
    }

    // 6) RELEASE (push images + git tag)
    stage('Release') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${DOCKERHUB_CREDS}", usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          sh '''
            set -euo pipefail
            echo "[RELEASE] Login & push dynamic, latest, and immutable tags"
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

            echo "[RELEASE] Create annotated git tag"
            git config user.email "ci@jenkins"
            git config user.name  "Jenkins CI"
            git tag -a "${RELEASE_TAG}" -m "Release ${RELEASE_TAG}" || true
            git push origin "${RELEASE_TAG}" || true
          '''
        }
      }
    }

    // 7) MONITORING (post-deploy smoke checks)
    stage('Monitoring') {
      steps {
        sh '''
          set -euo pipefail
          echo "[MONITOR] Smoke checks via port-forward to /health"

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
