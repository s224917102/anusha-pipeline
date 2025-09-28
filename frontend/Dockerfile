# week09/example-2/frontend/Dockerfile
FROM nginx:1.27-alpine

# your nginx.conf should contain: user nginx; and listen 80;
COPY nginx.conf /etc/nginx/conf.d/default.conf

# static assets owned by nginx user
COPY --chown=nginx:nginx . /usr/share/nginx/html

RUN apk add --no-cache curl

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -fsS http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
