FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 8101 8102 8103 8104
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -qO- http://localhost:8101/ >/dev/null || exit 1
