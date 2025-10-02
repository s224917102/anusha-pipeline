FROM nginx:1.29.1-alpine-slim

# Upgrade base packages
RUN apk --no-cache upgrade

# Copy your custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy frontend static files
COPY . /usr/share/nginx/html

EXPOSE 80