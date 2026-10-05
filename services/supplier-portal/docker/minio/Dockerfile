FROM golang:1.24-alpine AS builder

ARG MINIO_REF

RUN test -n "$MINIO_REF" || \
    (echo "MINIO_REF build arg is required" && exit 1)

RUN apk add --no-cache git

WORKDIR /src

RUN git clone \
    --depth 1 \
    --branch "$MINIO_REF" \
    https://github.com/minio/minio.git .

ENV CGO_ENABLED=0

RUN go build \
    -trimpath \
    -o /out/minio .


FROM alpine:3.22

RUN apk add --no-cache ca-certificates

COPY --from=builder /out/minio /usr/local/bin/minio

RUN mkdir -p /data

EXPOSE 9000
EXPOSE 9001

VOLUME ["/data"]

ENTRYPOINT ["/usr/local/bin/minio"]

CMD ["server", "/data", "--console-address", ":9001"]