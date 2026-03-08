# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Serve stage using lightweight Nginx
FROM nginx:alpine

# Copy the built static assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Update NGINX config to handle React Router Single Page App paths 
# and proxy /api to the backend, disabling buffering for SSE
RUN echo 'server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html index.htm; \
        try_files $uri $uri/ /index.html; \
    } \
    location /api/ { \
        proxy_pass http://backend:8000/api/; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        # Handle Server-Sent Events correctly \
        proxy_set_header Connection ""; \
        proxy_http_version 1.1; \
        proxy_buffering off; \
        proxy_cache off; \
        # Increase timeout for complex LangGraph LLM completions \
        proxy_read_timeout 180s; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
