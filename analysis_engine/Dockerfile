FROM rust:1.99.1-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    clang \
    cmake \
    git \
    libclang-dev \
    libgdal-dev \
    libproj-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY src/ ./src/
RUN cargo build --release --locked

FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gdal-bin \
    libgdal32 \
    libproj25 \
    passwd \
    && rm -rf /var/lib/apt/lists/*

ENV HOST=0.0.0.0 \
    PORT=8003

WORKDIR /app
COPY --from=builder /build/target/release/vra-engine /usr/local/bin/vra-engine

RUN useradd --system --no-create-home --shell /usr/sbin/nologin app
USER app

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail --silent --show-error -X POST http://127.0.0.1:8003/health || exit 1

CMD ["vra-engine"]
