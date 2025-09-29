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

            # Apply manifests (best-effort)
            for f in configmaps.yaml secrets.yaml product-db.yaml order-db.yaml product-service.yaml order-service.yaml frontend.yaml; do
              [ -f "${K8S_DIR}/$f" ] && kubectl apply -n ${NAMESPACE} -f "${K8S_DIR}/$f" || true
            done

            # Helper to set image + rollout with rollback & retry
            update_img () {
              app_label="$1"; new_ref="$2"
              dep="$(kubectl get deploy -n ${NAMESPACE} -l app=${app_label} -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
              [ -z "$dep" ] && { echo "[RELEASE][WARN] No deployment for app=${app_label}"; return 0; }
              container="$(kubectl get deploy "$dep" -n ${NAMESPACE} -o jsonpath='{.spec.template.spec.containers[0].name}')"
              echo "[RELEASE] set image deploy/${dep} ${container}=${new_ref}"
              kubectl set image deploy/"$dep" "${container}=${new_ref}" -n ${NAMESPACE}

              if ! kubectl rollout status deploy/"$dep" -n ${NAMESPACE} --timeout=180s; then
                echo "[RELEASE][ERROR] Rollout failed for ${dep}. Rolling back…"
                kubectl rollout undo deploy/"$dep" -n ${NAMESPACE} || true
                kubectl rollout status deploy/"$dep" -n ${NAMESPACE} --timeout=120s || true

                echo "[RELEASE][WARN] Retrying rollout with :latest for ${dep}"
                kubectl set image deploy/"$dep" "${container}=${PRODUCT_IMG}:latest" -n ${NAMESPACE} || true
                if ! kubectl rollout status deploy/"$dep" -n ${NAMESPACE} --timeout=120s; then
                  echo "[RELEASE][FATAL] Fallback rollout failed for ${dep}"
                  exit 1
                fi
              fi
            }

            update_img product-service ${PRODUCT_IMG}:${IMAGE_TAG}
            update_img order-service   ${ORDER_IMG}:${IMAGE_TAG}
            update_img frontend        ${FRONTEND_IMG}:${IMAGE_TAG}

            echo "[RELEASE] Kubernetes release complete."
          '''
        }
      }
    }

    stage('Monitoring') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail
          echo "[MONITOR] Quick health checks via port-forward"

          PRODUCT_SVC=$(kubectl get svc -n ${NAMESPACE} -l app=product-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
          ORDER_SVC=$(kubectl get svc -n ${NAMESPACE} -l app=order-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

          if [ -n "$PRODUCT_SVC" ]; then
            kubectl port-forward svc/${PRODUCT_SVC} 18000:8000 -n ${NAMESPACE} >/tmp/pf_prod.log 2>&1 &
            PF1=$!; sleep 5
            curl -fsS http://localhost:18000/health || (echo "Product /health failed" && kill $PF1 || true && exit 1)
            kill $PF1 || true
          fi

          if [ -n "$ORDER_SVC" ]; then
            kubectl port-forward svc/${ORDER_SVC} 18001:8001 -n ${NAMESPACE} >/tmp/pf_order.log 2>&1 &
            PF2=$!; sleep 5
            curl -fsS http://localhost:18001/health || (echo "Order /health failed" && kill $PF2 || true && exit 1)
            kill $PF2 || true
          fi

          echo "[MONITOR] Health checks passed."
        '''
      }
    }
