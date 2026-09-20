FROM python:3.14.7-slim-trixie@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2

COPY services/runtime-agent/requirements-runtime.txt /tmp/requirements-runtime.txt
RUN python -m pip install --no-cache-dir --require-hashes \
        --requirement /tmp/requirements-runtime.txt \
    && rm /tmp/requirements-runtime.txt

COPY services/runtime-agent/src /opt/retrobrowser/runtime-agent
ENV PYTHONPATH=/opt/retrobrowser/runtime-agent

LABEL org.opencontainers.image.title="RetroBrowser Runtime Agent" \
      org.opencontainers.image.description="Narrow Docker lifecycle boundary" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/YOUR_GITHUB_OWNER/retrobrowser"

ENTRYPOINT ["python", "-m", "retro_runtime"]
