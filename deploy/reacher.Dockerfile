# Build the exact MIT-licensed source inspected for this project. Build on a larger
# machine/CI and transfer the image if compiling Rust exceeds the VPS's memory.
FROM rust:1-bookworm AS builder
ARG REACHER_COMMIT=681791d3d9a854dfcaadb5eb13e5a2f3cb4eed67
RUN git clone https://github.com/reacherhq/check-if-email-exists.git /src && cd /src && git checkout "$REACHER_COMMIT"
WORKDIR /src
ENV SQLX_OFFLINE=true CARGO_BUILD_JOBS=1
RUN cargo build --locked --release --bin reacher_backend

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libssl3 && rm -rf /var/lib/apt/lists/* && useradd --uid 10002 --create-home reacher
WORKDIR /home/reacher
COPY --from=builder /src/target/release/reacher_backend ./reacher_backend
COPY --from=builder /src/LICENSE.md ./REACHER-LICENSE.md
COPY deploy/reacher.toml ./backend_config.toml
USER reacher
EXPOSE 8080
CMD ["./reacher_backend"]
