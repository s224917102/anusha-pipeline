FROM nginx:1.29.1-alpine-slim

# Upgrade base packages (with --no-cache, avoids caching index files)

RUN apk --no-cache upgrade

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY . /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]