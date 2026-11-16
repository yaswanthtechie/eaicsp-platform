# Images are pinned by digest so `make up --build` does not re-pull and recreate MinIO
# whenever upstream moves :latest (see #313).
#
# To update a pin:
#   docker pull chainguard/minio:latest
#   docker inspect --format "{{index .RepoDigests 0}}" chainguard/minio:latest
#   docker pull chainguard/minio-client:latest
#   docker inspect --format "{{index .RepoDigests 0}}" chainguard/minio-client:latest
#
# Paste each sha256 below, then run `make up` twice and confirm MinIO is not recreated.

FROM chainguard/minio-client:latest@sha256:dbdb3b237441a5985c65af5a4bceed052fd01f872dae5d22d8ca5460d09c91ab AS mc

FROM chainguard/minio:latest@sha256:fb893e36fc369d41e92f678b17ec27378fa5bf0576aeef7ac15460c13629ab5a

COPY --from=mc /usr/bin/mc /usr/bin/mc
