FROM golang:1.24-alpine AS builder

WORKDIR /src

COPY .minio-community-source/ .

ENV CGO_ENABLED=0
ENV GOOS=linux
ENV GOARCH=amd64

RUN go build -trimpath -o /out/minio .


FROM alpine:3.22

RUN apk add --no-cache ca-certificates

COPY --from=builder /out/minio /usr/local/bin/minio

RUN mkdir -p /data

EXPOSE 9000
EXPOSE 9001

VOLUME ["/data"]

ENTRYPOINT ["/usr/local/bin/minio"]

CMD ["server", "/data", "--console-address", ":9001"]