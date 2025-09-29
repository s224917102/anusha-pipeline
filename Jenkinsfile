pipeline {
  agent any

  environment {
    IMAGE_TAG = ""
    RELEASE_TAG = ""
    DOCKER_DEFAULT_PLATFORM = "linux/amd64"
  }

  stages {
    stage('Build') {
      steps {
        script {
          checkout scm
          IMAGE_TAG = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
          RELEASE_TAG = "v${env.BUILD_NUMBER}.${IMAGE_TAG}"
          echo "[BUILD] IMAGE_TAG=${IMAGE_TAG} | RELEASE_TAG=${RELEASE_TAG}"

          sh "docker --version"
          sh "docker compose version"

          echo "[BUILD] Building images (amd64)"
          sh """
            DOCKER_DEFAULT_PLATFORM=linux/amd64 docker compose build --no-cache
          """

          echo "[BUILD] Tagging images"
          sh """
            docker tag week09_example02_product_service:latest week09_example02_product_service:${IMAGE_TAG}
            docker tag week09_example02_order_service:latest week09_example02_order_service:${IMAGE_TAG}
            docker tag week09_example02_frontend:latest week09_example02_frontend:${IMAGE_TAG}
          """
        }
      }
    }

    stage('Test') {
      steps {
        timeout(time: 25, unit: 'MINUTES') {
          script {
            echo "[TEST] Free ports if busy"
            sh "docker rm -f product_db order_db || true"

            echo "[TEST][UNIT] Start Postgres (amd64) on high ports"
            sh "docker run -d --name product_db -e POSTGRES_PASSWORD=pass -p 55432:5432 --platform=linux/amd64 postgres:15"
            sh "docker run -d --name order_db -e POSTGRES_PASSWORD=pass -p 55433:5432 --platform=linux/amd64 postgres:15"
            sleep 5

            echo "[TEST][UNIT] Run Product Service tests"
            sh "pytest backend/product_service/tests --junitxml=product_unit.xml"

            echo "[TEST][UNIT] Run Order Service tests"
            sh "pytest backend/order_service/tests --junitxml=order_unit.xml"

            echo "[TEST][UNIT] Stop DB containers"
            sh "docker rm -f product_db order_db || true"

            if (fileExists('tests/integration/docker-compose.yml')) {
              echo "[TEST][INT] Running integration tests with docker compose"
              sh """
                DOCKER_DEFAULT_PLATFORM=linux/amd64 docker compose -f tests/integration/docker-compose.yml up --build --abort-on-container-exit
                docker compose -f tests/integration/docker-compose.yml down -v
              """
            } else {
              echo "[TEST][INT] No integration tests found, skipping"
            }
          }
        }
      }
      post {
        always {
          junit 'product_unit.xml'
          junit 'order_unit.xml'
          sh "docker rm -f product_db order_db || true"
        }
      }
    }

    stage('Code Quality') {
      steps {
        withSonarQubeEnv('SonarQube') {
          sh """
            export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 || true
            export PATH=\$JAVA_HOME/bin:\$PATH
            sonar-scanner \
              -Dsonar.projectKey=anusha-pipeline \
              -Dsonar.sources=backend \
              -Dsonar.python.version=3.10
          """
        }
      }
    }

    stage('Security') {
      steps {
        sh "trivy image week09_example02_product_service:latest || true"
        sh "trivy image week09_example02_order_service:latest || true"
        sh "trivy image week09_example02_frontend:latest || true"
      }
    }

    stage('Deploy') {
      steps {
        echo "[DEPLOY] Deploy using Kubernetes"
        sh """
          kubectl apply -f week09/example-3/k8s/product-service.yaml
          kubectl apply -f week09/example-3/k8s/order-service.yaml
          kubectl apply -f week09/example-3/k8s/frontend.yaml
        """
      }
    }

    stage('Release') {
      steps {
        echo "[RELEASE] Tagging release ${RELEASE_TAG}"
        sh "git tag ${RELEASE_TAG}"
        sh "git push origin ${RELEASE_TAG}"
      }
    }

    stage('Monitoring') {
      steps {
        echo "[MONITORING] Checking Prometheus targets"
        sh "curl -s http://localhost:9090/-/healthy || true"
      }
    }
  }

  post {
    always {
      echo "Pipeline completed."
    }
    success {
      echo "Pipeline succeeded."
    }
    failure {
      echo "Pipeline failed - see logs."
    }
  }
}
