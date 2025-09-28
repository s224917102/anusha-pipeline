pipeline {
  agent any

  options {
    disableConcurrentBuilds()
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    PATH = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

    DOCKERHUB_NS    = 's224917102'
    DOCKERHUB_CREDS = 'dockerhub-s224917102'
    REGISTRY        = 'docker.io'
    PRODUCT_IMG     = "${REGISTRY}/${DOCKERHUB_NS}/product_service"
    ORDER_IMG       = "${REGISTRY}/${DOCKERHUB_NS}/order_service"
    FRONTEND_IMG    = "${REGISTRY}/${DOCKERHUB_NS}/frontend"

    LOCAL_IMG_PRODUCT  = 'week09_example02_product_service:latest'
    LOCAL_IMG_ORDER    = 'week09_example02_order_service:latest'
    LOCAL_IMG_FRONTEND = 'week09_example02_frontend:latest'

    KUBE_CONTEXT  = 'docker-desktop'
    NAMESPACE     = 'default'
    K8S_DIR       = 'k8s'

    SONARQUBE = 'SonarQube'
    SCANNER   = 'SonarScanner'
    SONAR_PROJECT_KEY  = 'sit753-anusha'
    SONAR_PROJECT_NAME = 'SIT753 Microservices'
    SONAR_SOURCES      = '.'

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

          # ---------- helpers ----------
          make_venv () {
            vdir="$1"; shift
            python3 -m venv "$vdir"
            . "$vdir/bin/activate"
            python -m pip install -U pip wheel >/dev/null
            # install all given pkgs verbatim (quoted by caller when needed)
            python -m pip install "$@" >/dev/null
            deactivate
          }

          wait_db () {
            name="$1"
            for i in $(seq 1 30); do
              if docker exec "$name" pg_isready -U postgres >/dev/null 2>&1; then
                echo " - $name ready"
                return 0
              fi
              sleep 2
            done
            echo "ERROR: $name not ready after 60s"
            docker logs "$name" || true
            return 1
          }

          # ---------- unit: spin up DBs ----------
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
          wait_db product_db
          wait_db order_db

          # ---------- unit: product_service ----------
          echo "[TEST][UNIT] Product"
          if [ -d ${PRODUCT_DIR} ]; then
            make_venv ".venv_prod" "pytest>=8,<9" "pytest-timeout==2.3.1"
            . .venv_prod/bin/activate
            # install runtime + dev deps (use -r for files)
            [ -f ${PRODUCT_DIR}/requirements.txt ] && python -m pip install -r ${PRODUCT_DIR}/requirements.txt >/dev/null || true
            [ -f ${PRODUCT_DIR}/requirements-dev.txt ] && python -m pip install -r ${PRODUCT_DIR}/requirements-dev.txt >/dev/null || true

            export POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=products POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            # avoid random plugin autoload; then explicitly load timeout
            export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
            pytest -q -p pytest_timeout ${PRODUCT_DIR}/tests --junitxml=product_unit.xml --timeout=60 --timeout-method=thread
            deactivate
          fi

          # ---------- unit: order_service ----------
          echo "[TEST][UNIT] Order"
          if [ -d ${ORDER_DIR} ]; then
            make_venv ".venv_order" "pytest>=8,<9" "pytest-timeout==2.3.1"
            . .venv_order/bin/activate
            [ -f ${ORDER_DIR}/requirements.txt ] && python -m pip install -r ${ORDER_DIR}/requirements.txt >/dev/null || true
            [ -f ${ORDER_DIR}/requirements-dev.txt ] && python -m pip install -r ${ORDER_DIR}/requirements-dev.txt >/dev/null || true

            export POSTGRES_HOST=localhost POSTGRES_PORT=5433 POSTGRES_DB=orders POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
            pytest -q -p pytest_timeout ${ORDER_DIR}/tests --junitxml=order_unit.xml --timeout=60 --timeout-method=thread
            deactivate
          fi

          echo "[TEST][UNIT] Stop DB containers"
          docker rm -f product_db order_db >/dev/null 2>&1 || true

          # ---------- integration ----------
          echo "[TEST][INT] Compose up (if tests/integration exists)"
          if [ -d tests/integration ]; then
            (docker compose up -d --remove-orphans || docker-compose up -d --remove-orphans)

            wait_http () { url="$1"; max="$2"; i=0; until curl -fsS "$url" >/dev/null 2>&1; do i=$((i+1)); [ $i -ge $max ] && return 1; sleep 1; done; }

            if ! wait_http "http://localhost:8000/health" 90; then
              echo "[TEST][INT] product_service not ready in time"
              (docker compose logs product_service || docker-compose logs product_service) | tail -200 || true
              (docker compose down -v || docker-compose down -v) || true
              exit 1
            fi
            if ! wait_http "http://localhost:8001/health" 90; then
              echo "[TEST][INT] order_service not ready in time"
              (docker compose logs order_service || docker-compose logs order_service) | tail -200 || true
              (docker compose down -v || docker-compose down -v) || true
              exit 1
            fi

            INT_KEY=$(date +%s)
            make_venv ".venv_int_${INT_KEY}" "pytest>=8,<9" "pytest-timeout==2.3.1" requests
            . ".venv_int_${INT_KEY}/bin/activate"
            export PRODUCT_BASE=${PRODUCT_BASE:-http://localhost:8000}
            export ORDER_BASE=${ORDER_BASE:-http://localhost:8001}
            export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
            pytest -q -p pytest_timeout tests/integration --junitxml=integration.xml --timeout=90 --timeout-method=thread
            deactivate

            echo "[TEST][INT] Compose down"
            (docker compose down -v || docker-compose down -v)
          else
            echo "[TEST][INT] No tests/integration — skipping"
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
          withEnv(["PATH+SCANNER=${tool SCANNER}/bin"]) {
            sh '''#!/usr/bin/env bash
              set -euo pipefail
              echo "[QUALITY] Sonar analysis"
              sonar-scanner \
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
          echo "[MONITOR] Health checks"
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
