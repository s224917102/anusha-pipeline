stage('Test') {
  options { timeout(time: 20, unit: 'MINUTES') } // hard cap for this stage
  steps {
    sh '''#!/usr/bin/env bash
      set -euo pipefail

      echo "[TEST] Clean up any old DB containers"
      docker rm -f product_db order_db >/dev/null 2>&1 || true

      echo "[TEST] Start Postgres containers (product:5432, order:5433)"
      docker run -d --name product_db -p 5432:5432 \
        -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=products \
        postgres:15
      docker run -d --name order_db -p 5433:5432 \
        -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=orders \
        postgres:15

      echo "[TEST] Wait for DBs to be ready (pg_isready)"
      for name in product_db order_db; do
        for i in $(seq 1 30); do
          if docker exec "$name" pg_isready -U postgres >/dev/null 2>&1; then
            echo " - $name is ready"
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

      # helper to create a venv quickly
      py() { python3 -m venv "$1" && . "$1/bin/activate" && pip install -U pip wheel >/dev/null; }

      echo "[TEST] === product_service unit tests ==="
      if [ -d ${PRODUCT_DIR} ]; then
        py .venv_prod
        . .venv_prod/bin/activate
        pip install -r ${PRODUCT_DIR}/requirements.txt >/dev/null
        [ -f ${PRODUCT_DIR}/requirements-dev.txt ] && pip install -r ${PRODUCT_DIR}/requirements-dev.txt >/dev/null || true
        # ensure pytest-timeout is installed so hangs fail fast
        pip install pytest pytest-timeout >/dev/null

        export POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=products POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
        # Fail fast, show slow tests, enforce per-test timeout
        PYTEST_ADDOPTS="-q -x --maxfail=1 --durations=10 --timeout=60 --timeout-method=thread"
        # disable auto-loading 3rd-party pytest plugins that can slow/hang on Jenkins
        export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

        pytest ${PRODUCT_DIR}/tests --junitxml=product_unit.xml $PYTEST_ADDOPTS
      fi

      echo "[TEST] === order_service unit tests ==="
      if [ -d ${ORDER_DIR} ]; then
        py .venv_order
        . .venv_order/bin/activate
        pip install -r ${ORDER_DIR}/requirements.txt >/dev/null
        [ -f ${ORDER_DIR}/requirements-dev.txt ] && pip install -r ${ORDER_DIR}/requirements-dev.txt >/dev/null || true
        pip install pytest pytest-timeout >/dev/null

        export POSTGRES_HOST=localhost POSTGRES_PORT=5433 POSTGRES_DB=orders POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
        PYTEST_ADDOPTS="-q -x --maxfail=1 --durations=10 --timeout=60 --timeout-method=thread"
        export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

        pytest ${ORDER_DIR}/tests --junitxml=order_unit.xml $PYTEST_ADDOPTS
      fi

      echo "[TEST] Stop DB containers"
      docker rm -f product_db order_db >/dev/null 2>&1 || true

      echo "[TEST] === integration tests (compose) ==="
      # Bring up only if the test files exist
      if [ -f tests/integration/test_product_integration.py ] || [ -f tests/integration/test_order_integration.py ]; then
        (docker compose up -d --remove-orphans || docker-compose up -d --remove-orphans)
        sleep 10

        py .venv_int
        . .venv_int/bin/activate
        pip install pytest pytest-timeout requests >/dev/null
        export PRODUCT_BASE=${PRODUCT_BASE:-http://localhost:8000}
        export ORDER_BASE=${ORDER_BASE:-http://localhost:8001}
        PYTEST_ADDOPTS="-q -x --maxfail=1 --durations=10 --timeout=60 --timeout-method=thread"
        export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

        pytest tests/integration/test_product_integration.py tests/integration/test_order_integration.py \
          --junitxml=integration.xml $PYTEST_ADDOPTS || (docker compose down -v || docker-compose down -v; exit 1)

        (docker compose down -v || docker-compose down -v)
      else
        echo "[TEST] No integration test files found — skipping compose up"
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
