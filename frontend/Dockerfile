FROM nginx:1.29.1-alpine-slim

# Upgrade base packages
RUN apk --no-cache upgrade

# Copy your custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy frontend static files
COPY . /usr/share/nginx/html

# Add entrypoint script to inject env vars into env.js
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]