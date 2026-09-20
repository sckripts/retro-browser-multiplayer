FROM python:3.14.7-slim-trixie@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2

COPY services/session-manager/requirements-runtime.txt /tmp/requirements-runtime.txt
RUN python -m pip install --no-cache-dir --require-hashes \
        --requirement /tmp/requirements-runtime.txt \
    && rm /tmp/requirements-runtime.txt

COPY services/session-manager/src /opt/retrobrowser/session-manager
ENV PYTHONPATH=/opt/retrobrowser/session-manager

LABEL org.opencontainers.image.title="RetroBrowser Session Manager" \
      org.opencontainers.image.description="Private lobby and runtime orchestration control plane" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/YOUR_GITHUB_OWNER/retrobrowser"

USER 1000:1000
ENTRYPOINT ["python", "-m", "retro_sessions"]
