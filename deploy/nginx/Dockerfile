FROM node:20-alpine AS h5-build
WORKDIR /build
COPY h5/package*.json ./
RUN npm ci
COPY h5/ ./
RUN npm run build

FROM node:20-alpine AS admin-build
WORKDIR /build
COPY admin/package*.json ./
RUN npm ci
COPY admin/ ./
RUN npm run build

FROM nginx:alpine
COPY deploy/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=h5-build /build/dist /usr/share/nginx/html
COPY --from=admin-build /build/dist /usr/share/nginx/html/admin
