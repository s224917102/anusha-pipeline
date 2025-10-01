FROM nginx:1.29.1-alpine-slim

# Update system packages to get security fixes
RUN apk update && apk upgrade

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY . /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]