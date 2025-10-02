#!/bin/sh
set -e

# Inject environment variables into env.js file dynamically
echo "window.PRODUCT_API_URL='${PRODUCT_API_URL:-http://localhost:8000}';" > /usr/share/nginx/html/env.js
echo "window.ORDER_API_URL='${ORDER_API_URL:-http://localhost:8001}';" >> /usr/share/nginx/html/env.js

echo "[ENTRYPOINT] Injected API URLs into env.js:"
cat /usr/share/nginx/html/env.js

# Start Nginx
exec nginx -g "daemon off;"