FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY frontend/dashboard/package.json frontend/dashboard/package-lock.json ./
RUN npm ci

COPY frontend/dashboard /app
RUN npm run build

FROM node:20-alpine

RUN npm install -g serve

WORKDIR /app
COPY --from=build /app/dist /app/dist

EXPOSE 8080

CMD ["serve", "-s", "dist", "-l", "8080"]
