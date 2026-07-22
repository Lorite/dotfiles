# aw-server-rust + aw-sync in one image.
# There is no official ActivityWatch image and no Dockerfile in the aw-server-rust
# repo, so we grab the prebuilt binaries out of the official ActivityWatch release
# (multi-stage: download in a builder, copy just the two binaries into a slim final
# image — no Rust toolchain, no ~100 MB zip in the final layer).
ARG AW_VERSION=v0.13.2

FROM debian:stable-slim AS fetch
ARG AW_VERSION
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl unzip ca-certificates \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp
RUN curl -fsSL -o aw.zip \
      "https://github.com/ActivityWatch/activitywatch/releases/download/${AW_VERSION}/activitywatch-${AW_VERSION}-linux-x86_64.zip" \
 && unzip -q aw.zip \
 && srv="$(find . -type f -name aw-server-rust | head -1)" \
 && sync="$(find . -type f -name aw-sync | head -1)" \
 && test -n "$srv" && test -n "$sync" \
 && install -Dm0755 "$srv"  /out/aw-server-rust \
 && install -Dm0755 "$sync" /out/aw-sync

FROM debian:stable-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates libssl3 curl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=fetch /out/aw-server-rust /out/aw-sync /usr/local/bin/
# aw-server-rust stores its DB under $XDG_DATA_HOME/activitywatch/aw-server-rust
ENV XDG_DATA_HOME=/data
RUN mkdir -p /data
EXPOSE 5600
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:5600/api/0/info || exit 1
ENTRYPOINT ["aw-server-rust"]
CMD ["--host", "0.0.0.0", "--port", "5600"]
