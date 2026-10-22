FROM chainguard/minio-client:latest AS mc
FROM chainguard/minio:latest
COPY --from=mc /usr/bin/mc /usr/bin/mc
