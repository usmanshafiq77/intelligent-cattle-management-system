FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit

COPY . .

ARG EXPO_PUBLIC_APP_ENV=staging
ARG EXPO_PUBLIC_API_BASE_URL
ARG EXPO_PUBLIC_API_BASE_URL_WEB
ARG EXPO_PUBLIC_API_BASE_URL_ANDROID
ARG EXPO_PUBLIC_API_DEBUG=false

ENV EXPO_PUBLIC_APP_ENV=$EXPO_PUBLIC_APP_ENV \
    EXPO_PUBLIC_API_BASE_URL=$EXPO_PUBLIC_API_BASE_URL \
    EXPO_PUBLIC_API_BASE_URL_WEB=$EXPO_PUBLIC_API_BASE_URL_WEB \
    EXPO_PUBLIC_API_BASE_URL_ANDROID=$EXPO_PUBLIC_API_BASE_URL_ANDROID \
    EXPO_PUBLIC_API_DEBUG=$EXPO_PUBLIC_API_DEBUG

RUN npm run export:web

FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist/web /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:8080/healthz >/dev/null || exit 1
