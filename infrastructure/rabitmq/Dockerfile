FROM rabbitmq:3.8-management

COPY docker-healthcheck.sh /
HEALTHCHECK --interval=5s --timeout=5s --retries=5 CMD ["/bin/bash", "/docker-healthcheck.sh"]