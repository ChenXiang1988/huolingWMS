# 多阶段：node 构建前端 → 产物放进 nginx
FROM node:20-alpine AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

# 两套产物分目录存放：/admin/ 是后台，/owner/ 是货主门户。
# 分开存放是"两个登录端"的物理前提——不会因为一份 index.html 兜底而串门。
COPY --from=build /app/dist/admin /usr/share/nginx/html/admin
COPY --from=build /app/dist/owner /usr/share/nginx/html/owner
COPY docker/nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
