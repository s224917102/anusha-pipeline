pipeline {
  agent any

  options {
    disableConcurrentBuilds()
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    PATH = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

    // ---------- Docker / Registry ----------
    DOCKERHUB_NS    = 's224917102'
    DOCKERHUB_CREDS = 'dockerhub-s224917102'
    REGISTRY        = 'docker.io'
    DOCKER_DEFAULT_PLATFORM = 'linux/amd64'

    PRODUCT_IMG   = "${REGISTRY}/${DOCKERHUB_NS}/product_service"
    ORDER_IMG     = "${REGISTRY}/${DOCKERHUB_NS}/order_service"
    FRONTEND_IMG  = "${REGISTRY}/${DOCKERHUB_NS}/frontend"

    LOCAL_IMG_PRODUCT  = 'week09_example02_product_service:latest'
    LOCAL_IMG_ORDER    = 'week09_example02_order_service:latest'
    LOCAL_IMG_FRONTEND = 'week09_example02_frontend:latest'

    // ---------- K8s ----------
    KUBE_CONTEXT  = 'docker-desktop'
    NAMESPACE     = 'default'
    K8S_DIR       = 'k8s'

    // ---------- Sonar ----------
    SONARQUBE          = 'SonarQube'
    SONAR_PROJECT_KEY  = 's224917102_DevOpsPipeline'
    SONAR_PROJECT_NAME = 'DevOpsPipeline'
    SONAR_SOURCES      = '.'

    // ---------- Paths ----------
    PRODUCT_DIR  = 'backend/product_service'
    ORDER_DIR    = 'backend/order_service'
    FRONTEND_DIR = 'frontend'

    // ---------- Tools ----------
    TRIVY_VER    = '0.55.0'
  }

  stages {
    /* ========================= BUILD ========================= */
    stage('Build') {
      steps {
        checkout scm
        script {
          env.GIT_SHA     = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
          env.IMAGE_TAG   = "${env.GIT_SHA}-${env.BUILD_NUMBER}"
          env.RELEASE_TAG = "v${env.BUILD_NUMBER}.${env.GIT_SHA}"
          echo "[BUILD] IMAGE_TAG=${env.IMAGE_TAG} | RELEASE_TAG=${env.RELEASE_TAG}"
        }
        sh '''#!/usr/bin/env bash
          set -euo pipefail
          export DOCKER_DEFAULT_PLATFORM="${DOCKER_DEFAULT_PLATFORM}"
          export DOCKER_BUILDKIT=1

          echo "[BUILD] Compose build (amd64, --no-cache)"
          if [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; then
            DOCKER_DEFAULT_PLATFORM="${DOCKER_DEFAULT_PLATFORM}" docker compose build --no-cache
          fi

          echo "[BUILD] Explicit docker builds"
          docker build --pull --platform="${DOCKER_DEFAULT_PLATFORM}" -t ${LOCAL_IMG_PRODUCT} ${PRODUCT_DIR}
          docker build --pull --platform="${DOCKER_DEFAULT_PLATFORM}" -t ${LOCAL_IMG_ORDER}   ${ORDER_DIR}
          docker build --pull --platform="${DOCKER_DEFAULT_PLATFORM}" -t ${LOCAL_IMG_FRONTEND} ${FRONTEND_DIR}

          echo "[BUILD] Tag for registry"
          docker tag ${LOCAL_IMG_PRODUCT}  ${PRODUCT_IMG}:${IMAGE_TAG}
          docker tag ${LOCAL_IMG_PRODUCT}  ${PRODUCT_IMG}:latest
          docker tag ${LOCAL_IMG_ORDER}    ${ORDER_IMG}:${IMAGE_TAG}
          docker tag ${LOCAL_IMG_ORDER}    ${ORDER_IMG}:latest
          docker tag ${LOCAL_IMG_FRONTEND} ${FRONTEND_IMG}:${IMAGE_TAG}
          docker tag ${LOCAL_IMG_FRONTEND} ${FRONTEND_IMG}:latest
        '''
      }
    }

    /* ========================= TEST ========================= */
    stage('Test') {
      options { timeout(time: 30, unit: 'MINUTES') }
      steps {
        sh '''#!/usr/bin/env bash
          set -euxo pipefail
          export DOCKER_DEFAULT_PLATFORM="${DOCKER_DEFAULT_PLATFORM}"

          make_venv () {
            vdir="$1"; shift
            python3 -m venv "$vdir"
            . "$vdir/bin/activate"
            python -m pip install -U pip wheel >/dev/null
            [ $# -gt 0 ] && python -m pip install "$@" >/dev/null || true
            deactivate
          }

          wait_db () {
            name="$1"
            for i in $(seq 1 60); do   # doubled wait to 120s
              if docker exec "$name" pg_isready -U postgres >/dev/null 2>&1; then
                echo " - $name ready"
                return 0
              fi
              echo "   waiting for $name ($i/60)..."
              sleep 2
            done
            echo "ERROR: $name not ready after 120s"
            docker logs "$name" || true
            return 1
          }

          echo "[TEST] Clean up any old DBs"
          docker rm -f product_db order_db >/dev/null 2>&1 || true

          echo "[TEST] Start Postgres containers"
          docker run -d --name product_db -p 55432:5432 --platform="${DOCKER_DEFAULT_PLATFORM}" \
            -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=products \
            postgres:15
          docker run -d --name order_db -p 55433:5432 --platform="${DOCKER_DEFAULT_PLATFORM}" \
            -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=orders \
            postgres:15

          wait_db product_db
          wait_db order_db

          echo "[TEST] Run Product service unit tests"
          if [ -d ${PRODUCT_DIR}/tests ]; then
            make_venv ".venv_prod" "pytest>=8,<9" "pytest-timeout==2.3.1" "psycopg2-binary"
            . .venv_prod/bin/activate
            pip install -r ${PRODUCT_DIR}/requirements.txt -r ${PRODUCT_DIR}/requirements-dev.txt || true
            export POSTGRES_HOST=localhost POSTGRES_PORT=55432 POSTGRES_DB=products POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            pytest -q -p pytest_timeout ${PRODUCT_DIR}/tests --junitxml=product_unit.xml --timeout=90 --timeout-method=thread
            deactivate
          fi

          echo "[TEST] Run Order service unit tests"
          if [ -d ${ORDER_DIR}/tests ]; then
            make_venv ".venv_order" "pytest>=8,<9" "pytest-timeout==2.3.1" "psycopg2-binary"
            . .venv_order/bin/activate
            pip install -r ${ORDER_DIR}/requirements.txt -r ${ORDER_DIR}/requirements-dev.txt || true
            export POSTGRES_HOST=localhost POSTGRES_PORT=55433 POSTGRES_DB=orders POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            pytest -q -p pytest_timeout ${ORDER_DIR}/tests --junitxml=order_unit.xml --timeout=90 --timeout-method=thread
            deactivate
          fi

          echo "[TEST] Stop DB containers"
          docker rm -f product_db order_db >/dev/null 2>&1 || true

          echo "[TEST] Integration tests (if present)"
          if [ -d tests/integration ]; then
            DOCKER_DEFAULT_PLATFORM="${DOCKER_DEFAULT_PLATFORM}" docker compose up -d --remove-orphans
            sleep 5

            wait_http () { url="$1"; max="${2:-120}"; i=0; until curl -fsS "$url" >/dev/null 2>&1; do i=$((i+1)); [ $i -ge $max ] && return 1; echo "waiting for $url ($i/$max)..."; sleep 1; done; }
            wait_http "http://localhost:8000/health" 120
            wait_http "http://localhost:8001/health" 120

            make_venv ".venv_int" "pytest>=8,<9" "pytest-timeout==2.3.1" requests
            . .venv_int/bin/activate
            export PRODUCT_BASE=http://localhost:8000
            export ORDER_BASE=http://localhost:8001
            pytest -q -p pytest_timeout tests/integration --junitxml=integration.xml --timeout=120 --timeout-method=thread
            deactivate
            docker compose down -v
          else
            echo "[TEST] No integration tests found"
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

    /* ========================= CODE QUALITY ========================= */
    stage('Code Quality') {
      steps {
        withSonarQubeEnv("${SONARQUBE}") {
          withCredentials([string(credentialsId: 'SONAR_TOKEN', variable: 'SONAR_TOKEN')]) {
            sh '''#!/usr/bin/env bash
              set -euo pipefail
              echo "[QUALITY] Running Sonar scanner"
              docker run --rm --platform=linux/amd64 \
                -e SONAR_HOST_URL="${SONAR_HOST_URL:-https://sonarcloud.io}" \
                -e SONAR_TOKEN="$SONAR_TOKEN" \
                -v "$PWD:/usr/src" -w /usr/src \
                sonarsource/sonar-scanner-cli:latest
            '''
          }
        }
      }
    }

    /* ========================= SECURITY ========================= */
    stage('Security') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euxo pipefail
          mkdir -p security-reports .trivycache
          TRIVY_IMG="aquasec/trivy:${TRIVY_VER}"

          docker run --rm --platform="${DOCKER_DEFAULT_PLATFORM}" \
            -v "$PWD":/src -w /src \
            -v "$PWD/.trivycache":/root/.cache/ \
            "$TRIVY_IMG" fs --scanners vuln,misconfig,secret \
              --format json --output security-reports/trivy-fs.json \
              --no-progress /src || true

          for IMG in ${PRODUCT_IMG}:${IMAGE_TAG} ${ORDER_IMG}:${IMAGE_TAG} ${FRONTEND_IMG}:${IMAGE_TAG}; do
            echo "Scanning $IMG"
            docker run --rm --platform="${DOCKER_DEFAULT_PLATFORM}" \
              -v "$PWD/.trivycache":/root/.cache/ \
              "$TRIVY_IMG" image --exit-code 1 --severity HIGH,CRITICAL --no-progress "$IMG"
          done
        '''
        archiveArtifacts artifacts: 'security-reports/*', allowEmptyArchive: true, fingerprint: true
      }
    }

    /* ========================= DEPLOY ========================= */
    stage('Deploy') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euxo pipefail
          export DOCKER_DEFAULT_PLATFORM="${DOCKER_DEFAULT_PLATFORM}"

          docker compose up -d --remove-orphans
          sleep 5
          curl -fsS http://localhost:8000/health || exit 1
          curl -fsS http://localhost:8001/health || exit 1
        '''
      }
    }

    /* ========================= RELEASE ========================= */
    stage('Release') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${DOCKERHUB_CREDS}", usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          sh '''#!/usr/bin/env bash
            set -euxo pipefail
            echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin
            for img in ${PRODUCT_IMG} ${ORDER_IMG} ${FRONTEND_IMG}; do
              docker push $img:${IMAGE_TAG}
              docker push $img:latest
              docker tag $img:${IMAGE_TAG} $img:${RELEASE_TAG}
              docker push $img:${RELEASE_TAG}
            done

            kubectl config use-context ${KUBE_CONTEXT}
            kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
            kubectl apply -n ${NAMESPACE} -f ${K8S_DIR} || true
          '''
        }
      }
    }

    /* ========================= MONITORING ========================= */
    stage('Monitoring') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euxo pipefail
          PRODUCT_SVC=$(kubectl get svc -n ${NAMESPACE} -l app=product-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
          ORDER_SVC=$(kubectl get svc -n ${NAMESPACE} -l app=order-service   -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

          if [ -n "$PRODUCT_SVC" ]; then
            kubectl port-forward svc/${PRODUCT_SVC} 18000:8000 -n ${NAMESPACE} >/tmp/pf_prod.log 2>&1 &
            PF1=$!; sleep 5
            curl -fsS http://localhost:18000/health || (echo "Product health check failed"; kill $PF1; exit 1)
            kill $PF1
          fi

          if [ -n "$ORDER_SVC" ]; then
            kubectl port-forward svc/${ORDER_SVC} 18001:8001 -n ${NAMESPACE} >/tmp/pf_order.log 2>&1 &
            PF2=$!; sleep 5
            curl -fsS http://localhost:18001/health || (echo "Order health check failed"; kill $PF2; exit 1)
            kill $PF2
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
