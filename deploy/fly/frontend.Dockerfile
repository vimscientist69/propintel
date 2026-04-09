FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/dashboard/package.json frontend/dashboard/package-lock.json ./
RUN npm ci

COPY frontend/dashboard /app
RUN npm run build

FROM nginx:1.27-alpine

RUN apk add --no-cache gettext

COPY deploy/fly/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

ENV BACKEND_UPSTREAM=propintel-api:8000

CMD ["/bin/sh", "-c", "envsubst '$BACKEND_UPSTREAM' < /etc/nginx/conf.d/default.conf > /tmp/default.conf && cp /tmp/default.conf /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
