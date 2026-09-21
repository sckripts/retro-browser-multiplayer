FROM ghcr.io/selkies-project/selkies/desktop:2.0.0rc1-ubuntu26.04@sha256:07ba642f431915158a7f4cec69d46303704816dced17d4ee95bd34b2a1ef23eb AS builder

USER root

ARG RETROARCH_VERSION=1.22.2
ARG RETROARCH_COMMIT=69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576
ARG RETROARCH_SOURCE_SHA256=b4bfa46ea5ce09008494099b967816de8da7a146ede2f7d1a52d5842a6aae215
ARG RETROARCH_ARTIFACT_SHA256=e7b3a9611e0d7bc429aac2cf92cafb7eeea3f730afaa7b0534805a01512ab73c
ARG MESEN_VERSION=0.9.9
ARG MESEN_COMMIT=f3a18bed018fa853627e0e15d02a3f2ba4960222
ARG MESEN_SOURCE_SHA256=9edba76d3fdbfe813834f83711a545004d34f8d1c28fbb68871b0f9e856a3fba
ARG MESEN_ARTIFACT_SHA256=1c3d682cdc8a47658235663ed92d39146f2c09ffcb565ed212c9260fb44d55e8
ARG BSNES_VERSION=2026-09-04
ARG BSNES_COMMIT=260f5234410d0899f8446882c63d17f891b686e0
ARG BSNES_SOURCE_SHA256=975645c62117d3ac32117ed7d1a12a1074d2a83020c93beef47ecf8bce4add44
ARG BSNES_ARTIFACT_SHA256=41f08812445a8ff08fbe3e9faf891ae685452d524e6569df15dbd90fa040d399
ARG BLASTEM_VERSION=2026-09-02
ARG BLASTEM_COMMIT=b4d75247ebad8852fd9bc385b423df704c6c5af5
ARG BLASTEM_SOURCE_SHA256=c1c216d39ab5d1401abd6da02938cb4b40fd52a033045ec49a25890b2dcc042d
ARG BLASTEM_ARTIFACT_SHA256=52044324adbbda37a36c4d916dfb3bb677bf1952444c48a64d78f1c472991714

# Build-only packages never enter the final stage. Runtime libraries come from
# the immutable Selkies base image shared by both stages.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        pkg-config \
        libasound2-dev \
        libgl-dev \
        libpulse-dev \
        libudev-dev \
        libx11-dev \
        libx11-xcb-dev \
        libxext-dev \
        libxi-dev \
        libxinerama-dev \
        libxrandr-dev \
    && rm -rf /var/lib/apt/lists/*

ENV SOURCE_DATE_EPOCH=1763597828 \
    PYTHONHASHSEED=0

WORKDIR /tmp/build

RUN curl --fail --location --silent --show-error \
        --output retroarch.tar.gz \
        "https://codeload.github.com/libretro/RetroArch/tar.gz/${RETROARCH_COMMIT}" \
    && echo "${RETROARCH_SOURCE_SHA256}  retroarch.tar.gz" | sha256sum --check \
    && mkdir retroarch \
    && tar --extract --gzip --file retroarch.tar.gz --directory retroarch --strip-components=1 \
    && cd retroarch \
    && ./configure \
        --prefix=/usr/local \
        --enable-x11 \
        --enable-opengl \
        --enable-alsa \
        --enable-pulse \
        --enable-udev \
        --enable-networking \
        --disable-wayland \
        --disable-vulkan \
        --disable-sdl \
        --disable-sdl2 \
        --disable-ffmpeg \
        --enable-rgui \
        --disable-xmb \
        --disable-ozone \
        --disable-materialui \
    && make -j"$(nproc)" \
    && install -Dm0755 retroarch /opt/retro-session/usr/local/bin/retroarch \
    && echo "${RETROARCH_ARTIFACT_SHA256}  /opt/retro-session/usr/local/bin/retroarch" \
        | sha256sum --check \
    && sha256sum /opt/retro-session/usr/local/bin/retroarch \
        > /opt/retro-session/retroarch.sha256

RUN curl --fail --location --silent --show-error \
        --output mesen.tar.gz \
        "https://codeload.github.com/libretro/Mesen/tar.gz/${MESEN_COMMIT}" \
    && echo "${MESEN_SOURCE_SHA256}  mesen.tar.gz" | sha256sum --check \
    && mkdir mesen \
    && tar --extract --gzip --file mesen.tar.gz --directory mesen --strip-components=1 \
    && make -C mesen/Libretro -j"$(nproc)" platform=unix \
    && install -Dm0755 mesen/Libretro/mesen_libretro.so \
        /opt/retro-session/opt/libretro/mesen_libretro.so \
    && echo "${MESEN_ARTIFACT_SHA256}  /opt/retro-session/opt/libretro/mesen_libretro.so" \
        | sha256sum --check \
    && sha256sum /opt/retro-session/opt/libretro/mesen_libretro.so \
        > /opt/retro-session/mesen_libretro.sha256

RUN curl --fail --location --silent --show-error \
        --output bsnes.tar.gz \
        "https://codeload.github.com/libretro/bsnes-libretro/tar.gz/${BSNES_COMMIT}" \
    && echo "${BSNES_SOURCE_SHA256}  bsnes.tar.gz" | sha256sum --check \
    && mkdir bsnes-source \
    && tar --extract --gzip --file bsnes.tar.gz --directory bsnes-source --strip-components=1 \
    && make -C bsnes-source/bsnes -j"$(nproc)" \
        target=libretro binary=library local=false platform=linux \
    && install -Dm0755 bsnes-source/bsnes/out/bsnes_libretro.so \
        /opt/retro-session/opt/libretro/bsnes_libretro.so \
    && echo "${BSNES_ARTIFACT_SHA256}  /opt/retro-session/opt/libretro/bsnes_libretro.so" \
        | sha256sum --check \
    && sha256sum /opt/retro-session/opt/libretro/bsnes_libretro.so \
        > /opt/retro-session/bsnes_libretro.sha256

RUN curl --fail --location --silent --show-error \
        --output blastem.tar.gz \
        "https://codeload.github.com/libretro/blastem/tar.gz/${BLASTEM_COMMIT}" \
    && echo "${BLASTEM_SOURCE_SHA256}  blastem.tar.gz" | sha256sum --check \
    && mkdir blastem-source \
    && tar --extract --gzip --file blastem.tar.gz --directory blastem-source --strip-components=1 \
    && make -C blastem-source -f Makefile.libretro -j"$(nproc)" platform=linux OPT=-O2 \
    && install -Dm0755 blastem-source/blastem_libretro.so \
        /opt/retro-session/opt/libretro/blastem_libretro.so \
    && echo "${BLASTEM_ARTIFACT_SHA256}  /opt/retro-session/opt/libretro/blastem_libretro.so" \
        | sha256sum --check \
    && sha256sum /opt/retro-session/opt/libretro/blastem_libretro.so \
        > /opt/retro-session/blastem_libretro.sha256

FROM ghcr.io/selkies-project/selkies/desktop:2.0.0rc1-ubuntu26.04@sha256:07ba642f431915158a7f4cec69d46303704816dced17d4ee95bd34b2a1ef23eb

USER root

COPY --from=builder /opt/retro-session/usr/local/bin/retroarch /usr/local/bin/retroarch
COPY --from=builder /opt/retro-session/opt/libretro/mesen_libretro.so /opt/libretro/mesen_libretro.so
COPY --from=builder /opt/retro-session/opt/libretro/bsnes_libretro.so /opt/libretro/bsnes_libretro.so
COPY --from=builder /opt/retro-session/opt/libretro/blastem_libretro.so /opt/libretro/blastem_libretro.so
COPY --from=builder /opt/retro-session/*.sha256 /opt/retro-session/
COPY images/retro-session/requirements-runtime.txt /opt/retro-session/requirements-runtime.txt
RUN python3 -m pip install --no-cache-dir --require-hashes --target /opt/retro-session/python --requirement /opt/retro-session/requirements-runtime.txt
COPY images/retro-session/session_entrypoint /opt/retrobrowser/session_entrypoint
COPY --chmod=0755 images/retro-session/entrypoint/run /etc/service/retroarch/run
COPY --chmod=0755 images/retro-session/entrypoint/finish /etc/service/retroarch/finish
COPY --chmod=0755 images/retro-session/entrypoint/finish /etc/service/selkies/finish
COPY --chmod=0755 images/retro-session/entrypoint/save-flusher-run /etc/service/save-flusher/run
COPY --chmod=0755 images/retro-session/entrypoint/metrics-proxy-run /etc/service/metrics-proxy/run
RUN install -d -m0755 /etc/retro-session
COPY --chmod=0444 images/retro-session/config/retroarch.cfg /etc/retro-session/retroarch.cfg
COPY --chmod=0444 images/retro-session/config/retroarch-core-options.cfg /etc/retro-session/retroarch-core-options.cfg
COPY --chmod=0444 images/retro-session/manifests/cores.yaml /etc/retro-session/cores.yaml

ENV PYTHONPATH=/opt/retrobrowser:/opt/retro-session/python \
    OMP_NUM_THREADS=2 \
    OMP_THREAD_LIMIT=2 \
    OMP_DYNAMIC=false \
    OMP_WAIT_POLICY=PASSIVE

# Builder paths differ from final paths; rewrite only the embedded check files.
RUN sed -i 's#/opt/retro-session/usr/local/bin/retroarch#/usr/local/bin/retroarch#' \
        /opt/retro-session/retroarch.sha256 \
    && sed -i 's#/opt/retro-session/opt/libretro/mesen_libretro.so#/opt/libretro/mesen_libretro.so#' \
        /opt/retro-session/mesen_libretro.sha256 \
    && sed -i 's#/opt/retro-session/opt/libretro/bsnes_libretro.so#/opt/libretro/bsnes_libretro.so#' \
        /opt/retro-session/bsnes_libretro.sha256 \
    && sed -i 's#/opt/retro-session/opt/libretro/blastem_libretro.so#/opt/libretro/blastem_libretro.so#' \
        /opt/retro-session/blastem_libretro.sha256 \
    && mkdir -p /run/roms /run/retro-session \
    && chown ubuntu:ubuntu /run/roms /run/retro-session \
    && chown -R ubuntu:ubuntu /etc/service/retroarch /etc/service/save-flusher \
        /etc/service/metrics-proxy \
    && rm -f /usr/local/bin/selkies-proot

LABEL org.opencontainers.image.title="RetroBrowser Retro Session" \
      org.opencontainers.image.description="Pinned RetroArch, Mesen, bsnes, and BlastEm session on Selkies" \
      org.opencontainers.image.licenses="GPL-3.0-only AND GPL-3.0-or-later AND MPL-2.0" \
      org.opencontainers.image.source="https://github.com/YOUR_GITHUB_OWNER/retrobrowser"

USER ubuntu
