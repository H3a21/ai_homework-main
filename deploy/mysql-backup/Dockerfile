FROM minio/mc:latest AS minio-client

FROM mysql:8.0

COPY --from=minio-client /usr/bin/mc /usr/local/bin/mc
COPY backup.sh restore.sh /usr/local/bin/

RUN chmod 0555 /usr/local/bin/mc /usr/local/bin/backup.sh /usr/local/bin/restore.sh \
    && mkdir -p /backup/mysql \
    && chown -R 1001:0 /backup

ENV HOME=/tmp \
    MC_CONFIG_DIR=/tmp/mc

USER 1001
ENTRYPOINT ["/usr/local/bin/backup.sh"]
CMD ["schedule"]
