pipeline {
  agent any

  options {
    disableConcurrentBuilds()
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    PATH = "/opt/homebrew/opt/python@3.11/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

    DOCKERHUB_NS    = 's224917102'
    DOCKERHUB_CREDS = 'dockerhub-s224917102'
    REGISTRY        = 'docker.io'


    PRODUCT_IMG     = "${REGISTRY}/${DOCKERHUB_NS}/product_service"
    ORDER_IMG       = "${REGISTRY}/${DOCKERHUB_NS}/order_service"
    FRONTEND_IMG    = "${REGISTRY}/${DOCKERHUB_NS}/frontend"

    // Local tags built in Build stage
    LOCAL_IMG_PRODUCT  = 'week09_example02_product_service:latest'
    LOCAL_IMG_ORDER    = 'week09_example02_order_service:latest'
    LOCAL_IMG_FRONTEND = 'week09_example02_frontend:latest'

    KUBE_CONTEXT  = 'docker-desktop'
    NAMESPACE     = 'default'
    K8S_DIR       = 'k8s'

    SONARQUBE = 'SonarQube'
    SONAR_PROJECT_KEY  = 's224917102_DevOpsPipeline'
    SONAR_PROJECT_NAME = 'DevOpsPipeline'
    SONAR_SOURCES      = '.'

    PRODUCT_DIR  = 'backend/product_service'
    ORDER_DIR    = 'backend/order_service'
    FRONTEND_DIR = 'frontend'

    TRIVY_VER    = '0.55.0'
  }

  stages {

    /* ========================= BUILD (rebuild images) ========================= */
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

          echo "[BUILD] Smoke test with docker-compose"
          compose () { docker compose "$@" || docker-compose "$@"; }
          COMPOSE_IGNORE_ORPHANS=true IMAGE_TAG=${IMAGE_TAG} compose up -d
          sleep 15
          curl -fsS http://localhost:3001/ || { echo "Frontend not responding"; exit 1; }
          curl -fsS http://localhost:9090/-/healthy || { echo "Prometheus not healthy"; exit 1; }
          curl -fsS http://localhost:3000/login || { echo "Grafana not responding"; exit 1; }
          echo "[BUILD] All containers healthy."
          compose down -v
        '''
      }
    }

    /* ======================================================================== */

    /* ========================= TEST ========================= */
    stage('Test') {
      options { timeout(time: 25, unit: 'MINUTES') }
      steps {
        sh '''
          set -euo pipefail

          echo "[TEST] Python version check:"
          python3.11 --version || { echo "Python 3.11 not found"; exit 1; }

          make_venv () {
            vdir="$1"; shift
            python3.11 -m venv "$vdir"
            . "$vdir/bin/activate"
            python -m pip install -U pip wheel >/dev/null
            [ $# -gt 0 ] && python -m pip install "$@" >/dev/null || true
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

          docker rm -f product_db order_db >/dev/null 2>&1 || true

          docker run -d --name product_db -p 55432:5432 \
            -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=products \
            postgres:15
          docker run -d --name order_db -p 55433:5432 \
            -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=orders \
            postgres:15

          wait_db product_db
          wait_db order_db

          echo "[TEST] Running product tests"
          if [ -d ${PRODUCT_DIR} ]; then
            make_venv ".venv_prod" "pytest>=8,<9" "pytest-timeout==2.3.1"
            . .venv_prod/bin/activate
            pip install -r ${PRODUCT_DIR}/requirements.txt || true
            pip install -r ${PRODUCT_DIR}/requirements-dev.txt || true
            export POSTGRES_HOST=localhost POSTGRES_PORT=55432 POSTGRES_DB=products POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
            pytest -q -p pytest_timeout ${PRODUCT_DIR}/tests --junitxml=product_unit.xml --timeout=60
            deactivate
          fi

          echo "[TEST] Running order tests"
          if [ -d ${ORDER_DIR} ]; then
            make_venv ".venv_order" "pytest>=8,<9" "pytest-timeout==2.3.1"
            . .venv_order/bin/activate
            pip install -r ${ORDER_DIR}/requirements.txt || true
            pip install -r ${ORDER_DIR}/requirements-dev.txt || true
            export POSTGRES_HOST=localhost POSTGRES_PORT=55433 POSTGRES_DB=orders POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
            export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
            pytest -q -p pytest_timeout ${ORDER_DIR}/tests --junitxml=order_unit.xml --timeout=60
            deactivate
          fi

          docker rm -f product_db order_db >/dev/null 2>&1 || true
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

    /* ========================= SECURITY (local images) ======================= */
    /* ========================= SECURITY (local images) ======================= */
    /* ========================= SECURITY (local images) ======================= */
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
            wait_http "http://localhost:3001/" 90 || FAIL_FRONTEND=1
            # Prometheus
            wait_http "http://localhost:9090/" 90 || FAIL_PROM=1
            # Grafana
            wait_http "http://localhost:3000/" 90 || FAIL_GRAF=1

            if [ "${FAIL_PRODUCT:-0}" -ne 0 ] || [ "${FAIL_ORDER:-0}" -ne 0 ] || \
               [ "${FAIL_FRONTEND:-0}" -ne 0 ] || [ "${FAIL_PROM:-0}" -ne 0 ] || \
               [ "${FAIL_GRAF:-0}" -ne 0 ]; then
              echo "[DEPLOY][ERROR] Staging health checks failed. Attempting rollback to :latest."
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
            withCredentials([usernamePassword(credentialsId: "${DOCKERHUB_CREDS}", usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
            sh '''#!/usr/bin/env bash
                set -euo pipefail

                echo "[RELEASE] Login & push images"
                echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin

                for img in ${PRODUCT_IMG} ${ORDER_IMG} ${FRONTEND_IMG}; do
                docker push $img:${IMAGE_TAG}
                docker push $img:latest
                docker tag $img:${IMAGE_TAG} $img:${RELEASE_TAG}
                docker push $img:${RELEASE_TAG}
                done

                echo "[RELEASE] Deploy to local Kubernetes (${KUBE_CONTEXT})"
                kubectl config use-context ${KUBE_CONTEXT}
                kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

                echo "[RELEASE] Apply MetalLB config if present"
                
                if [ -f "${K8S_DIR}/metallb-config.yaml" ]; then
                  kubectl apply -f "${K8S_DIR}/metallb-config.yaml"
                else
                  echo "[RELEASE][WARN] No metallb-config.yaml found in ${K8S_DIR}, skipping"
                fi

                echo "[RELEASE] Apply infra (configmaps, secrets, databases)"
                for f in configmaps.yaml secrets.yaml product-db.yaml order-db.yaml; do
                [ -f "${K8S_DIR}/$f" ] && kubectl apply -n ${NAMESPACE} -f "${K8S_DIR}/$f" || true
                done

                echo "[RELEASE] Apply microservices (product, order, frontend)"
                for f in product-service.yaml order-service.yaml frontend.yaml; do
                [ -f "${K8S_DIR}/$f" ] && kubectl apply -n ${NAMESPACE} -f "${K8S_DIR}/$f" || true
                done

                echo "[RELEASE] Apply monitoring (Prometheus + Grafana)"
                for f in prometheus-configmap.yaml prometheus-rbac.yaml prometheus-deployment.yaml grafana-deployment.yaml; do
                [ -f "${K8S_DIR}/$f" ] && kubectl apply -n ${NAMESPACE} -f "${K8S_DIR}/$f" || true
                done

                echo "[RELEASE] Waiting for LoadBalancer IPs (Product, Order, Frontend, Prometheus, Grafana)"
                get_svc_address () {
                svc="$1"; ns="$2"
                ip=$(kubectl get svc "$svc" -n "$ns" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
                host=$(kubectl get svc "$svc" -n "$ns" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)
                port=$(kubectl get svc "$svc" -n "$ns" -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || true)

                if [ -n "$ip" ]; then
                    echo "$ip"
                elif [ -n "$host" ]; then
                    echo "$host"
                elif [ -n "$port" ]; then
                    echo "localhost:$port"
                else
                    echo ""
                fi
                }

                SERVICES=(product-service order-service frontend prometheus-service grafana-service)
                for svc in "${SERVICES[@]}"; do
                echo "Waiting for $svc address..."
                for i in $(seq 1 60); do
                    addr=$(get_svc_address "$svc" ${NAMESPACE})
                    if [ -n "$addr" ]; then
                    echo "[RELEASE] $svc available at $addr"
                    break
                    fi
                    echo "Attempt $i: still pending..."
                    sleep 5
                done
                done

                echo "[RELEASE] Kubernetes release complete."
                kubectl get svc -n ${NAMESPACE}
            '''
            }
        }
    }

    stage('Monitoring & Alerting (Prometheus)') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail

          echo "== Resolving Prometheus EXTERNAL-IP (MetalLB) =="
          PROM_IP=$(kubectl get svc prometheus-service -n ${NAMESPACE} \
            -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)

          if [ -z "$PROM_IP" ]; then
            echo "[ERROR] Prometheus service has no EXTERNAL-IP yet. Check MetalLB."
            exit 1
          fi
          PROM_URL="http://${PROM_IP}:80"

          echo "Prometheus URL: $PROM_URL"

          echo "== Generating traffic to Product and Order services =="
          PRODUCT_IP=$(kubectl get svc product-service -n ${NAMESPACE} \
            -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
            
          ORDER_IP=$(kubectl get svc order-service -n ${NAMESPACE} \
            -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)

          if [ -z "$PRODUCT_IP" ] || [ -z "$ORDER_IP" ]; then
            echo "[ERROR] Product or Order service EXTERNAL-IP not ready."
            exit 1
          fi

          PRODUCT_METRICS="http://${PRODUCT_IP}:8000/metrics"
          ORDER_METRICS="http://${ORDER_IP}:8001/metrics"

          echo "Hitting product-service (${PRODUCT_METRICS}) ${COUNT} times..."
          for i in $(seq 1 "${COUNT}"); do curl -s "${PRODUCT_IP}:8000/health" >/dev/null || true; done

          echo "Hitting order-service (${ORDER_METRICS}) ${COUNT} times..."
          for i in $(seq 1 "${COUNT}"); do curl -s "${ORDER_IP}:8001/health" >/dev/null || true; done

          echo "Traffic complete, waiting for Prometheus scrape..."
          sleep 10

          echo "== Querying Prometheus for metrics =="
          # Product requests
          PROD_REQ=$(curl -fsSG "${PROM_URL}/api/v1/query" \
            --data-urlencode "query=sum(increase(http_requests_total{app_name=\\"product_service\\"}[${WIN}]))" \
            | jq -r '.data.result[0].value[1] // "0"')

          # Order requests
          ORDER_REQ=$(curl -fsSG "${PROM_URL}/api/v1/query" \
            --data-urlencode "query=sum(increase(http_requests_total{app_name=\\"order_service\\"}[${WIN}]))" \
            | jq -r '.data.result[0].value[1] // "0"')

          # Order creation rate
          ORDER_RATE=$(curl -fsSG "${PROM_URL}/api/v1/query" \
            --data-urlencode "query=rate(order_creation_total{app_name=\\"order_service\\"}[1m])" \
            | jq -r '.data.result[0].value[1] // "0"')

          # Targets status
          TARGETS=$(curl -fsS "${PROM_URL}/api/v1/targets" \
            | jq -r '.data.activeTargets[]? | "\\(.labels.job) @ \\(.labels.instance): \\(.health)"')

          echo "== Monitoring Summary =="
          echo "Prometheus : ${PROM_URL}"
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
