FROM chainguard/minio-client:latest@sha256:dbdb3b237441a5985c65af5a4bceed052fd01f872dae5d22d8ca5460d09c91ab AS mc
FROM chainguard/minio:latest@sha256:fb893e36fc369d41e92f678b17ec27378fa5bf0576aeef7ac15460c13629ab5a
COPY --from=mc /usr/bin/mc /usr/bin/mc
