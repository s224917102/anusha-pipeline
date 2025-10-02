pipeline {
  agent any

  options {
    disableConcurrentBuilds()
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    PATH = "/opt/homebrew/opt/python@3.11/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

    // add line to trigger
    
    DOCKERHUB_CREDS = 'dockerhub-s224917102'

    // Local tags built in Build stage
    LOCAL_IMG_PRODUCT  = 'week09_example02_product_service:latest'
    LOCAL_IMG_ORDER    = 'week09_example02_order_service:latest'
    LOCAL_IMG_FRONTEND = 'week09_example02_frontend:latest'

    // Azure rresources
    AZURE_CREDENTIALS = 'AZURE_CREDENTIALS'
    ACR_NAME="anushakatuwalacr"
    ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
    NAMESPACE="default"
    RG_PRODUCTION="anushakatuwal-rg"
    AKS_PRODUCTION="anushakatuwal-aks"

    PRODUCT_IMG     = "${ACR_LOGIN_SERVER}/product_service"
    ORDER_IMG       = "${ACR_LOGIN_SERVER}/order_service"
    FRONTEND_IMG    = "${ACR_LOGIN_SERVER}/frontend"

    // sonarqube credentials
    SONARQUBE = 'SonarQube'
    SONAR_PROJECT_KEY  = 's224917102_DevOpsPipeline'
    SONAR_PROJECT_NAME = 'DevOpsPipeline'
    SONAR_SOURCES      = '.'

    PRODUCT_DIR  = 'backend/product_service'
    ORDER_DIR    = 'backend/order_service'
    FRONTEND_DIR = 'frontend'
    K8S_DIR       = 'k8s'

    TRIVY_VER    = '0.55.0'
  }

  stages {

    /* ========================= BUILD (build images) ========================= */
    stage('Build') {
      steps {
        checkout scm
        script {
          env.GIT_SHA     = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
          env.IMAGE_TAG   = "${env.GIT_SHA}-${env.BUILD_NUMBER}"
          env.RELEASE_TAG = "v${env.BUILD_NUMBER}.${env.GIT_SHA}"
        }
        sh '''#!/usr/bin/env bash
          set -euo pipefail

          export DOCKER_BUILDKIT=1
          PLATFORM="linux/amd64"

          echo "[BUILD] Cleaning up old containers..."
          compose () { docker compose "$@" || docker-compose "$@"; }
          compose down -v --remove-orphans || true
          docker rm -f product_db_container order_db_container >/dev/null 2>&1 || true

          echo "[BUILD] Using buildx for ${PLATFORM}"
          docker buildx create --use --name multiarch || docker buildx use multiarch
          docker buildx inspect --bootstrap

          echo "[BUILD] Build & tag images"
          docker buildx build --platform=${PLATFORM} -t ${LOCAL_IMG_PRODUCT} ${PRODUCT_DIR} --load
          docker buildx build --platform=${PLATFORM} -t ${LOCAL_IMG_ORDER}   ${ORDER_DIR} --load
          docker buildx build --platform=${PLATFORM} -t ${LOCAL_IMG_FRONTEND} ${FRONTEND_DIR} --load

          echo "[BUILD] Tagging for registry"
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
      options { timeout(time: 25, unit: 'MINUTES') }
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail

          echo "[TEST] Cleaning up old DB containers..."
          docker rm -f product_db order_db >/dev/null 2>&1 || true

          echo "[TEST] Starting fresh Postgres containers with healthchecks"
          docker run -d --name product_db \
            -e POSTGRES_USER=postgres \
            -e POSTGRES_PASSWORD=postgres \
            -e POSTGRES_DB=products \
            --health-cmd='pg_isready -U postgres' \
            --health-interval=5s \
            --health-retries=12 \
            -p 0:5432 postgres:15

          docker run -d --name order_db \
            -e POSTGRES_USER=postgres \
            -e POSTGRES_PASSWORD=postgres \
            -e POSTGRES_DB=orders \
            --health-cmd='pg_isready -U postgres' \
            --health-interval=5s \
            --health-retries=12 \
            -p 0:5432 postgres:15

          echo "[TEST] Resolving dynamic host ports"
          PROD_PORT=$(docker inspect -f '{{ (index (index .NetworkSettings.Ports "5432/tcp") 0).HostPort }}' product_db)
          ORDER_PORT=$(docker inspect -f '{{ (index (index .NetworkSettings.Ports "5432/tcp") 0).HostPort }}' order_db)

          echo "Product DB on localhost:${PROD_PORT}"
          echo "Order DB   on localhost:${ORDER_PORT}"

          echo "[TEST] Waiting for health checks..."
          for name in product_db order_db; do
            for i in $(seq 1 30); do
              STATUS=$(docker inspect -f '{{.State.Health.Status}}' $name)
              if [ "$STATUS" = "healthy" ]; then
                echo " - $name healthy"
                break
              fi
              echo "Waiting for $name ($STATUS)..."
              sleep 2
            done
          done

          echo "[TEST] Running product tests"
          if [ -d ${PRODUCT_DIR} ]; then
            python3.11 -m venv .venv_prod
            . .venv_prod/bin/activate
            pip install -U pip wheel >/dev/null
            pip install -r ${PRODUCT_DIR}/requirements.txt -r ${PRODUCT_DIR}/requirements-dev.txt || true
            export POSTGRES_HOST=localhost POSTGRES_PORT=$PROD_PORT POSTGRES_DB=products POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            pytest -q --junitxml=product_unit.xml ${PRODUCT_DIR}/tests
            deactivate
          fi

          echo "[TEST] Running order tests"
          if [ -d ${ORDER_DIR} ]; then
            python3.11 -m venv .venv_order
            . .venv_order/bin/activate
            pip install -U pip wheel >/dev/null
            pip install -r ${ORDER_DIR}/requirements.txt -r ${ORDER_DIR}/requirements-dev.txt || true
            export POSTGRES_HOST=localhost POSTGRES_PORT=$ORDER_PORT POSTGRES_DB=orders POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            pytest -q --junitxml=order_unit.xml ${ORDER_DIR}/tests
            deactivate
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
          withCredentials([string(credentialsId: 'SONAR_TOKEN', variable: 'SONAR_TOKEN')]) {
            sh '''#!/usr/bin/env bash
              set -euo pipefail
              echo "[QUALITY] Sonar analysis via Dockerized scanner (bundled Java)"
              if [ ! -f "sonar-project.properties" ]; then
                echo "[QUALITY][ERROR] sonar-project.properties not found at repo root."
                exit 1
              fi
              TOKEN="${SONAR_TOKEN:-${SONAR_AUTH_TOKEN:-}}"
              [ -z "$TOKEN" ] && { echo "[QUALITY][ERROR] No token available. Provide Jenkins secret 'SONAR_TOKEN'."; exit 1; }
              HURL="${SONAR_HOST_URL:-https://sonarcloud.io}"
              OUT="$(curl -sS -u "${TOKEN}:" "${HURL%/}/api/authentication/validate" || true)"
              echo "$OUT" | grep -q '"valid":true' || { echo "[QUALITY][ERROR] Invalid Sonar token for ${HURL}: $OUT"; exit 1; }
              docker run --rm --platform=linux/amd64 \
                -e SONAR_HOST_URL="$HURL" -e SONAR_TOKEN="$TOKEN" \
                -v "$PWD:/usr/src" -w /usr/src \
                sonarsource/sonar-scanner-cli:latest
            '''
          }
        }
      }
    }


    /* ========================= SECURITY ======================= */
    stage('Security') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${DOCKERHUB_CREDS}", usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          sh '''#!/usr/bin/env bash
            set -euo pipefail
            EXIT=0

            echo "[SECURITY] Prepare cache & reports dirs"
            mkdir -p security-reports .trivycache
            TRIVY_IMG="aquasec/trivy:${TRIVY_VER}"

            # Login so Trivy can pull if needed
            echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin || true

            echo "[SECURITY] Rebuild local images for scanning"
            docker build -t ${LOCAL_IMG_PRODUCT} ${PRODUCT_DIR}
            docker build -t ${LOCAL_IMG_ORDER}   ${ORDER_DIR}
            docker build -t ${LOCAL_IMG_FRONTEND} ${FRONTEND_DIR}

            echo "[SECURITY] FS scan (advisory) → JSON & SARIF"
            docker run --rm \
              -v "$PWD":/src -w /src \
              -v "$PWD/.trivycache":/root/.cache/ \
              "$TRIVY_IMG" fs --scanners vuln,misconfig,secret \
                --format json  --output security-reports/trivy-fs.json \
                --no-progress /src || true

            docker run --rm \
              -v "$PWD":/src -w /src \
              -v "$PWD/.trivycache":/root/.cache/ \
              "$TRIVY_IMG" fs --scanners vuln,misconfig,secret \
                --format sarif --output security-reports/trivy-fs.sarif \
                --no-progress /src || true

            echo "[SECURITY] Image scans (blocking on HIGH/CRITICAL) against local images"
            IMAGES="${LOCAL_IMG_PRODUCT} ${LOCAL_IMG_ORDER} ${LOCAL_IMG_FRONTEND}"

            for IMG in $IMAGES; do
              echo " - scanning $IMG"
              docker run --rm \
                -v /var/run/docker.sock:/var/run/docker.sock \
                -v "$PWD/.trivycache":/root/.cache/ \
                "$TRIVY_IMG" image \
                  --exit-code 1 \
                  --severity HIGH,CRITICAL \
                  --no-progress \
                  "$IMG" || EXIT=$?
            done

            exit ${EXIT:-0}
          '''
        }
        archiveArtifacts artifacts: 'security-reports/*', allowEmptyArchive: true, fingerprint: true
      }
    }


  /* ======================================================================== */
   stage('Deploy') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail

          compose () {
            if docker compose version >/dev/null 2>&1; then
              docker compose "$@"
            else
              docker-compose "$@"
            fi
          }

          wait_http () {
            url="$1"; tries="${2:-90}"
            i=0
            until curl -fsS "$url" >/dev/null 2>&1; do
              i=$((i+1))
              [ $i -ge $tries ] && return 1
              sleep 1
            done
          }

          echo "[DEPLOY] Staging with docker-compose (no rebuilds)"
          if [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; then
            compose up -d --remove-orphans
            compose ps || true

            # Frontend
            wait_http "http://localhost:3001/" 180 || FAIL_FRONTEND=1
            # Prometheus
            wait_http "http://localhost:9090/" 180 || FAIL_PROM=1
            # Grafana
            wait_http "http://localhost:3000/" 180 || FAIL_GRAF=1

            if [ "${FAIL_PRODUCT:-0}" -ne 0 ] || [ "${FAIL_ORDER:-0}" -ne 0 ] || \
               [ "${FAIL_FRONTEND:-0}" -ne 0 ] || [ "${FAIL_PROM:-0}" -ne 0 ] || \
               [ "${FAIL_GRAF:-0}" -ne 0 ]; then
              echo "[DEPLOY][ERROR] Staging health checks failed. Attempting rollback to :latest."

              # Ensure the reports folder exists before saving logs
              mkdir -p reports
              compose logs --no-color > reports/compose-failed.log || true
              COMPOSE_IGNORE_ORPHANS=true IMAGE_TAG=latest compose up -d || true
              exit 1
            fi

            echo "[DEPLOY] Staging environment is healthy."
          else
            echo "[DEPLOY][WARN] No docker-compose file present. Skipping staging deploy."
          fi
        '''
      }
    }

    stage('Release') {
        steps {
          withCredentials([string(credentialsId: 'AZURE_CREDENTIALS', variable: 'AZURE_CRED_JSON')]) {
            sh '''#!/usr/bin/env bash
                set -euo pipefail
                echo "$AZURE_CRED_JSON" > azure.json

                CLIENT_ID=$(jq -r .clientId azure.json)
                CLIENT_SECRET=$(jq -r .clientSecret azure.json)
                TENANT_ID=$(jq -r .tenantId azure.json)
                SUBSCRIPTION_ID=$(jq -r .subscriptionId azure.json)

                echo "[RELEASE] Logging into Azure with Service Principal"
                az login --service-principal \
                  --username "$CLIENT_ID" \
                  --password "$CLIENT_SECRET" \
                  --tenant "$TENANT_ID"

                az acr login --name ${ACR_NAME}
                az account set --subscription b0495cce-c2ce-414b-8f9b-4a8a5e500256

                echo "[RELEASE] Pushing images to ACR"
                for img in ${PRODUCT_IMG} ${ORDER_IMG} ${FRONTEND_IMG}; do
                  docker push $img:latest
                  docker tag $img:${IMAGE_TAG} $img:${RELEASE_TAG}
                  docker push $img:${RELEASE_TAG}
                done

                echo "[RELEASE] Get AKS credentials"
                az aks get-credentials --resource-group ${RG_PRODUCTION} --name ${AKS_PRODUCTION} --overwrite-existing

                echo "[RELEASE] Ensure namespace exists"
                kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

                # --- Apply Infra ---
                for f in configmaps.yaml secrets.yaml product-db.yaml order-db.yaml; do
                  [ -f "${K8S_DIR}/$f" ] && kubectl apply -n ${NAMESPACE} -f "${K8S_DIR}/$f" || true
                done

                # --- Apply Apps ---
                for f in product-service.yaml order-service.yaml frontend-configmaps.yaml frontend.yaml; do
                  [ -f "${K8S_DIR}/$f" ] && kubectl apply -n ${NAMESPACE} -f "${K8S_DIR}/$f" || true
                done

                # --- Apply Monitoring ---
                for f in prometheus-configmap.yaml prometheus-rbac.yaml prometheus-deployment.yaml grafana-deployment.yaml; do
                  [ -f "${K8S_DIR}/$f" ] && kubectl apply -n ${NAMESPACE} -f "${K8S_DIR}/$f" || true
                done

                # --- Rollout Checks ---
                echo "[RELEASE] Checking rollout status"
                for deploy in product-service order-service frontend prometheus-server grafana; do
                  echo "Waiting for rollout: $deploy"
                  if ! kubectl rollout status deploy/$deploy -n ${NAMESPACE} --timeout=180s; then
                    echo "[ERROR] Deployment $deploy failed to roll out."
                    kubectl describe deploy/$deploy -n ${NAMESPACE} || true
                    kubectl get pods -n ${NAMESPACE} -l app=$deploy -o wide || true
                    exit 1
                  fi
                done

                # --- Verify Services with Curl ---
                echo "[RELEASE] Checking service endpoints"
                check_service () {
                  svc=$1; port=$2; path=$3
                  echo "Resolving $svc..."
                  ADDR=""
                  for i in $(seq 1 30); do
                    ADDR=$(kubectl get svc $svc -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
                    [ -n "$ADDR" ] && break
                    echo "Waiting for $svc external IP..."
                    sleep 10
                  done
                  [ -z "$ADDR" ] && { echo "[ERROR] $svc did not get an external IP"; exit 1; }

                  echo "$svc available at $ADDR:$port"
                  if ! curl -fsS "http://$ADDR:$port$path" >/dev/null; then
                    echo "[ERROR] $svc check failed at http://$ADDR:$port$path"
                    exit 1
                  fi
                }

                # App services: expect health endpoints
                check_service product-service   8000 "/"
                check_service order-service     8001 "/"

                # Monitoring: just check base URL responds
                check_service prometheus-service 80 "/" 
                check_service grafana-service    80 "/" 

                # --- Inject service IPs into frontend main.js ---
                echo "[RELEASE] Resolving service external IPs..."
                PRODUCT_IP=$(kubectl get svc product-service -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
                ORDER_IP=$(kubectl get svc order-service -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
                CUSTOMER_IP=$(kubectl get svc customer-service -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "N/A")

                echo "[RELEASE] Injecting IPs into frontend/main.js"
                sed -i "s|_PRODUCT_API_URL_|http://${PRODUCT_IP}:8000|g" ${FRONTEND_DIR}/main.js
                sed -i "s|_ORDER_API_URL_|http://${ORDER_IP}:8001|g" ${FRONTEND_DIR}/main.js

                echo "--- Modified main.js content ---"
                head -n 20 ${FRONTEND_DIR}/main.js
                echo "--------------------------------"

                # --- Rebuild & redeploy frontend with updated main.js ---
                echo "[RELEASE] Rebuilding frontend with injected IPs"
                docker build -t ${FRONTEND_IMG}:${IMAGE_TAG} ${FRONTEND_DIR}
                docker push ${FRONTEND_IMG}:${IMAGE_TAG}

                echo "[RELEASE] Rolling out updated frontend"
                kubectl set image deploy/frontend frontend-container=${FRONTEND_IMG}:${IMAGE_TAG} -n ${NAMESPACE}
                kubectl rollout status deploy/frontend -n ${NAMESPACE} --timeout=180s

                echo "Waiting for rollout: frontend"
                check_service frontend          3001 "/" 

                echo "[RELEASE] All services deployed and verified."
                kubectl get pods -n ${NAMESPACE}
                kubectl get svc -n ${NAMESPACE}

                az logout
            '''
          }
        }
    }


    stage('Monitoring & Alerting (Prometheus)') {
      environment {
        COUNT = '10'   // how many requests to generate
        WIN   = '5m'   // query window for PromQL
      }
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail

          echo "== Resolving Prometheus EXTERNAL-IP =="
          PROM_IP=$(kubectl get svc prometheus-service -n ${NAMESPACE} \
            -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)

          if [ -z "$PROM_IP" ]; then
            echo "[ERROR] Prometheus service has no EXTERNAL-IP yet."
            exit 1
          fi
          PROM_URL="http://${PROM_IP}:80"
          echo "Prometheus URL: $PROM_URL"

          echo "== Resolving Product & Order EXTERNAL-IPs =="
          PRODUCT_IP=$(kubectl get svc product-service -n ${NAMESPACE} \
            -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
          ORDER_IP=$(kubectl get svc order-service -n ${NAMESPACE} \
            -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)

          if [ -z "$PRODUCT_IP" ] || [ -z "$ORDER_IP" ]; then
            echo "[ERROR] Product or Order service EXTERNAL-IP not ready."
            exit 1
          fi

          PRODUCT_URL="http://${PRODUCT_IP}:8000"
          ORDER_URL="http://${ORDER_IP}:8001"

          echo "== Generating ${COUNT} requests =="
          for i in $(seq 1 "${COUNT}"); do
            curl -s "${PRODUCT_URL}/health" >/dev/null || true
            curl -s "${ORDER_URL}/health" >/dev/null || true
          done

          echo "Traffic complete. Waiting for Prometheus scrape..."
          sleep 10

          echo "== Querying Prometheus =="
          PROD_REQ=$(curl -fsSG "${PROM_URL}/api/v1/query" \
            --data-urlencode "query=sum(increase(http_requests_total{app_name=\\"product_service\\"}[${WIN}]))" \
            | jq -r '.data.result[0].value[1] // "0"')

          ORDER_REQ=$(curl -fsSG "${PROM_URL}/api/v1/query" \
            --data-urlencode "query=sum(increase(http_requests_total{app_name=\\"order_service\\"}[${WIN}]))" \
            | jq -r '.data.result[0].value[1] // "0"')

          ORDER_RATE=$(curl -fsSG "${PROM_URL}/api/v1/query" \
            --data-urlencode "query=rate(order_creation_total{app_name=\\"order_service\\"}[1m])" \
            | jq -r '.data.result[0].value[1] // "0"')

          TARGETS=$(curl -fsS "${PROM_URL}/api/v1/targets" \
            | jq -r '.data.activeTargets[]? | "\\(.labels.job) @ \\(.labels.instance): \\(.health)"')

          echo "== Monitoring Summary =="
          echo "Prometheus UI: ${PROM_URL}"
          echo "Product requests in ${WIN}: ${PROD_REQ}"
          echo "Order requests in ${WIN}:   ${ORDER_REQ}"
          echo "Order creation rate (/s):   ${ORDER_RATE}"
          echo "Targets:"
          echo "${TARGETS}" | sed 's/^/  - /'
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
