# week09/example-2/frontend/Dockerfile

FROM nginx:1.27-alpine

# Ensure static files are owned by the nginx user
COPY --chown=nginx:nginx . /usr/share/nginx/html

# Your server block should listen on 80 (see note below)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Optional: install curl for a reliable healthcheck
RUN apk add --no-cache curl

EXPOSE 80

# Simple container healthcheck
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -fsS http://127.0.0.1/ || exit 1

# Run NGINX in the foreground
CMD ["nginx", "-g", "daemon off;"]
