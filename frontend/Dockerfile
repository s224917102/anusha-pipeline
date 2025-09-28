# Pin a modern nginx and bump libexpat to a fixed version
FROM nginx:1.27-alpine

# Upgrade expat to >= 2.7.2-r0 (fixes the HIGH you saw)
RUN apk add --no-cache 'expat>=2.7.2-r0'

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY . /usr/share/nginx/html

EXPOSE 80
CMD ["nginx","-g","daemon off;"]
