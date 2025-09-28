pipeline {
  agent any

  // Optional: poll the repo every 2 minutes (you can also keep this in the job UI)
  triggers {
    pollSCM('H/2 * * * *')
  }

  options {
    disableConcurrentBuilds()
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    // --- Tools path hints for macOS Jenkins controller nodes ---
    PATH = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH}"

    // ========== Docker Hub ==========
    DOCKERHUB_NS    = 's224917102'
    DOCKERHUB_CREDS = 'dockerhub-s224917102'
    REGISTRY        = 'docker.io'
    PRODUCT_IMG     = "${REGISTRY}/${DOCKERHUB_NS}/product_service"
    ORDER_IMG       = "${REGISTRY}/${DOCKERHUB_NS}/order_service"
    FRONTEND_IMG    = "${REGISTRY}/${DOCKERHUB_NS}/frontend"

    // ========== Local images built by docker compose ==========
    // Matches what you see with `docker images`
    PROD_SRC = 'week09_example02_product_service:latest'
    ORD_SRC  = 'week09_example02_order_service:latest'
    FE_SRC   = 'week09_example02_frontend:latest'

    // ========== Kubernetes (local) ==========
    KUBE_CONTEXT  = 'docker-desktop'    // change to 'minikube' if that's what you use
    NAMESPACE     = 'default'
    K8S_DIR       = 'k8s'

    // ========== SonarQube/SonarCloud ==========
    // Jenkins: Manage Jenkins → System → SonarQube servers: Name: "SonarQube", URL: https://sonarcloud.io
    // Jenkins: Manage Jenkins → Global Tool Configuration → SonarQube Scanner: Name "SonarScanner"
    SONARQUBE = 'SonarQube'
    SCANNER   = 'SonarScanner'

    // ========== Project paths (used by tests) ==========
    PRODUCT_DIR  = 'backend/product_service'
    ORDER_DIR    = 'backend/order_service'
    FRONTEND_DIR = 'frontend'

    // ========== Derived at runtime ==========
    GIT_SHA     = ''
    IMAGE_TAG   = ''   // <sha>-<build>   (e.g., 57312be-10)
    RELEASE_TAG = ''   // v<build>.<sha>  (e.g., v10.57312be)
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

        sh '''
          set -euo pipefail
          echo "[CHECK] PATH=$PATH"
          echo "[CHECK] docker=$(command -v docker || true)"
          echo "[CHECK] docker compose=$(docker compose version 2>/dev/null | head -1 || true)"
          echo "[CHECK] kubectl=$(command -v kubectl || true)"

          # Build images with docker compose if compose file exists
          if [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; then
            echo "[BUILD] Using docker compose to build images"
            docker compose build --pull
          else
            echo "[BUILD] No docker-compose file found; assuming local images already exist."
          fi

          echo "[BUILD] Re-tag local images to Docker Hub using dynamic IMAGE_TAG: ${IMAGE_TAG}"

          # Sanity: ensure local images exist
          docker image inspect "${PROD_SRC}" >/dev/null
          docker image inspect "${ORD_SRC}"  >/dev/null
          docker image inspect "${FE_SRC}"   >/dev/null

          # Tag -> product
          docker tag "${PROD_SRC}" "${PRODUCT_IMG}:${IMAGE_TAG}"
          docker tag "${PROD_SRC}" "${PRODUCT_IMG}:latest"

          # Tag -> order
          docker tag "${ORD_SRC}" "${ORDER_IMG}:${IMAGE_TAG}"
          docker tag "${ORD_SRC}" "${ORDER_IMG}:latest"

          # Tag -> frontend
          docker tag "${FE_SRC}" "${FRONTEND_IMG}:${IMAGE_TAG}"
          docker tag "${FE_SRC}" "${FRONTEND_IMG}:latest"
        '''
      }
    }

    stage('Test') {
      steps {
        sh '''
          set -euo pipefail

          echo "[TEST] Launch Postgres containers for unit tests"
          docker rm -f product_db order_db >/dev/null 2>&1 || true

          docker run -d --name product_db -p 5432:5432 \
            -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=products \
            postgres:15

          docker run -d --name order_db -p 5433:5432 \
            -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=orders \
            postgres:15

          echo "[TEST] Wait for DBs"
          for i in $(seq 1 30); do docker exec product_db pg_isready -U postgres && break || sleep 2; done
          for i in $(seq 1 30); do docker exec order_db   pg_isready -U postgres && break || sleep 2; done

          # Simple Python venv helper
          py() { python3 -m venv "$1" && . "$1/bin/activate" && pip install -U pip && shift && pip install "$@" ; }

          echo "[TEST] Unit tests (product_service)"
          if [ -d "${PRODUCT_DIR}" ]; then
            py .venv_prod -r ${PRODUCT_DIR}/requirements.txt || true
            . .venv_prod/bin/activate
            export POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=products POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            pytest -q ${PRODUCT_DIR}/tests --junitxml=product_unit.xml
          fi

          echo "[TEST] Unit tests (order_service)"
          if [ -d "${ORDER_DIR}" ]; then
            py .venv_order -r ${ORDER_DIR}/requirements.txt || true
            . .venv_order/bin/activate
            export POSTGRES_HOST=localhost POSTGRES_PORT=5433 POSTGRES_DB=orders POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            pytest -q ${ORDER_DIR}/tests --junitxml=order_unit.xml
          fi

          echo "[TEST] Stop DB containers"
          docker rm -f product_db order_db >/dev/null 2>&1 || true

          echo "[TEST] Start integration stack (compose)"
          if [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; then
            docker compose up -d --remove-orphans
            sleep 10
          fi

          echo "[TEST] Integration tests (product + order)"
          py .venv_int requests pytest
          . .venv_int/bin/activate
          export PRODUCT_BASE=${PRODUCT_BASE:-http://localhost:8000}
          export ORDER_BASE=${ORDER_BASE:-http://localhost:8001}
          pytest -q tests/integration/test_product_integration.py tests/integration/test_order_integration.py --junitxml=integration.xml || true

          echo "[TEST] Tear down integration stack"
          if [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; then
            docker compose down -v
          fi
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
        // If you have sonar-project.properties in repo, just run the scanner.
        withSonarQubeEnv("${SONARQUBE}") {
          withEnv(["PATH+SCANNER=${tool SCANNER}/bin"]) {
            sh '''
              set -euo pipefail
              echo "[QUALITY] Running sonar-scanner (uses sonar-project.properties if present)"
              sonar-scanner
            '''
          }
        }
      }
    }

    stage('Security') {
      steps {
        sh '''
          set -euo pipefail
          echo "[SECURITY] Trivy filesystem scan (fail on HIGH,CRITICAL)"
          docker run --rm -v "$(pwd)":/src aquasec/trivy:0.55.0 fs --exit-code 1 --severity HIGH,CRITICAL /src

          echo "[SECURITY] Trivy image scan (local images just tagged)"
          for img in \
            "${PRODUCT_IMG}:${IMAGE_TAG}" \
            "${ORDER_IMG}:${IMAGE_TAG}" \
            "${FRONTEND_IMG}:${IMAGE_TAG}"
          do
            echo "Scanning $img"
            docker run --rm aquasec/trivy:0.55.0 image --exit-code 1 --severity HIGH,CRITICAL "$img"
          done
        '''
      }
    }

    stage('Deploy') {
      steps {
        sh '''
          set -euo pipefail
          echo "[DEPLOY] Using kube context: ${KUBE_CONTEXT}"
          kubectl config use-context "${KUBE_CONTEXT}"
          kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

          # Apply base manifests if present
          for f in configmaps.yaml secrets.yaml product-db.yaml order-db.yaml product-service.yaml order-service.yaml frontend.yaml; do
            [ -f "${K8S_DIR}/$f" ] && kubectl apply -n "${NAMESPACE}" -f "${K8S_DIR}/$f" || true
          done

          # Point deployments to freshly-tagged images
          kubectl set image deploy/product-service product-service=${PRODUCT_IMG}:${IMAGE_TAG} -n "${NAMESPACE}" || true
          kubectl set image deploy/order-service   order-service=${ORDER_IMG}:${IMAGE_TAG}   -n "${NAMESPACE}" || true
          kubectl set image deploy/frontend        frontend=${FRONTEND_IMG}:${IMAGE_TAG}     -n "${NAMESPACE}" || true

          echo "[DEPLOY] Wait for rollouts (best-effort)"
          kubectl rollout status deploy/product-service -n "${NAMESPACE}" --timeout=180s || true
          kubectl rollout status deploy/order-service   -n "${NAMESPACE}" --timeout=180s || true
          kubectl rollout status deploy/frontend        -n "${NAMESPACE}" --timeout=180s || true

          kubectl get all -n "${NAMESPACE}"
        '''
      }
    }

    stage('Release') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${DOCKERHUB_CREDS}", usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          sh '''
            set -euo pipefail
            echo "[RELEASE] Login to Docker Hub and push tags"
            echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin

            for i in "${PRODUCT_IMG}" "${ORDER_IMG}" "${FRONTEND_IMG}"; do
              docker push "$i:${IMAGE_TAG}"
              docker push "$i:latest"
            done

            # Immutable release tag
            docker tag "${PRODUCT_IMG}:${IMAGE_TAG}"  "${PRODUCT_IMG}:${RELEASE_TAG}"
            docker tag "${ORDER_IMG}:${IMAGE_TAG}"    "${ORDER_IMG}:${RELEASE_TAG}"
            docker tag "${FRONTEND_IMG}:${IMAGE_TAG}" "${FRONTEND_IMG}:${RELEASE_TAG}"

            for i in "${PRODUCT_IMG}" "${ORDER_IMG}" "${FRONTEND_IMG}"; do
              docker push "$i:${RELEASE_TAG}"
            done

            echo "[RELEASE] Git tag (best-effort)"
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
          echo "[MONITOR] Port-forward + /health checks"

          PRODUCT_SVC=$(kubectl get svc -n "${NAMESPACE}" -l app=product-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
          ORDER_SVC=$(kubectl get svc -n "${NAMESPACE}" -l app=order-service   -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

          if [ -n "$PRODUCT_SVC" ]; then
            kubectl port-forward svc/${PRODUCT_SVC} 18000:8000 -n "${NAMESPACE}" >/tmp/pf_prod.log 2>&1 &
            PF1=$!; sleep 3
            curl -fsS http://localhost:18000/health || (echo "Product /health failed" && kill $PF1 || true && exit 1)
            kill $PF1 || true
          else
            echo "[MONITOR] Product service not found"
          fi

          if [ -n "$ORDER_SVC" ]; then
            kubectl port-forward svc/${ORDER_SVC} 18001:8001 -n "${NAMESPACE}" >/tmp/pf_order.log 2>&1 &
            PF2=$!; sleep 3
            curl -fsS http://localhost:18001/health || (echo "Order /health failed" && kill $PF2 || true && exit 1)
            kill $PF2 || true
          else
            echo "[MONITOR] Order service not found"
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
