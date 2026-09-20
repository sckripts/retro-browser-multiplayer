from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = (ROOT / "infra/compose/acceptance/compose.public-test.yml").read_text(encoding="utf-8")
GPU_OVERRIDE = (ROOT / "infra/compose/acceptance/compose.milestone3.gpu.yml").read_text(
    encoding="utf-8"
)
DIRECT_OVERRIDE = (ROOT / "infra/compose/acceptance/compose.milestone3.direct.yml").read_text(
    encoding="utf-8"
)
TCP_OVERRIDE = (ROOT / "infra/compose/acceptance/compose.milestone3.turn-tcp.yml").read_text(
    encoding="utf-8"
)
TLS_OVERRIDE = (ROOT / "infra/compose/acceptance/compose.milestone3.turn-tls.yml").read_text(
    encoding="utf-8"
)
TRAEFIK_STATIC = (ROOT / "infra/traefik/static/milestone3.yml").read_text(encoding="utf-8")
TRAEFIK_TEMPLATE = (ROOT / "infra/traefik/dynamic/milestone3.template.yml").read_text(
    encoding="utf-8"
)
START_SCRIPT = (ROOT / "infra/scripts/acceptance/milestone3-start.ps1").read_text(encoding="utf-8")
STOP_SCRIPT = (ROOT / "infra/scripts/acceptance/milestone3-stop.ps1").read_text(encoding="utf-8")
ENTRYPOINT = (ROOT / "images/retro-session/entrypoint/run").read_text(encoding="utf-8")
GITIGNORE = (ROOT / ".gitignore").read_text(encoding="utf-8")

COTURN_IMAGE = (
    "coturn/coturn:4.17.2-r0-debian@"
    "sha256:aa68aab64a3b929d57fc2924c98ea447bf996cf8dade2508e7b71eaf23f1f14e"
)
TURN_REST_IMAGE = (
    "ghcr.io/selkies-project/selkies/turn-rest:main@"
    "sha256:53e48365eee7a66886a75a9f37a4733895d864703928600bb5e4fa786e977f04"
)


def test_public_runtime_uses_secure_webrtc_and_private_credentials() -> None:
    required = (
        "SELKIES_MODE: webrtc",
        'SELKIES_ENABLE_DUAL_MODE: "false"',
        "SELKIES_SUBFOLDER: /stream/m3",
        "SELKIES_ALLOWED_ORIGINS: https://${M3_PUBLIC_HOSTNAME",
        "SELKIES_TURN_REST_URI: http://turn-rest:8008/",
        "SELKIES_TURN_REST_API_KEY: ${M3_TURN_REST_API_KEY:",
        'SELKIES_ENABLE_WEBRTC_STATISTICS: "true"',
        "SELKIES_WEBRTC_STATISTICS_DIR: /tmp\n",
        'SELKIES_VIDEO_BITRATE: "8000"',
        'SELKIES_ENABLE_INTERNAL_TURN: "false"',
    )
    for setting in required:
        assert setting in COMPOSE

    runtime = COMPOSE.split("\n  retro-session:\n", maxsplit=1)[1].split(
        "\n  turn-rest:\n", maxsplit=1
    )[0]
    assert "M3_TURN_SHARED_SECRET" not in runtime
    assert "ports:" not in runtime
    assert "      - turn" in runtime
    assert "/var/run/docker.sock" not in COMPOSE
    assert "privileged: true" not in COMPOSE


def test_coturn_is_immutable_hmac_authenticated_and_bounded() -> None:
    assert COTURN_IMAGE in COMPOSE
    coturn = COMPOSE.split("\n  coturn:\n", maxsplit=1)[1].split("\nnetworks:\n", maxsplit=1)[0]
    required = (
        "      - -n",
        "--external-ip=$$(detect-external-ip)",
        "--allowed-peer-ip=$$(detect-external-ip)",
        "--use-auth-secret",
        "--static-auth-secret=${M3_TURN_SHARED_SECRET:",
        "--fingerprint",
        "--unauthorized-ratelimit",
        "--pidfile=/tmp/turnserver.pid",
        "--no-multicast-peers",
        "--min-port=49160",
        "--max-port=49200",
        "${M3_TURN_PORT:-3478}:3478/tcp",
        "${M3_TURN_PORT:-3478}:3478/udp",
        "${M3_TURN_TLS_PORT:-5349}:5349/tcp",
        "49160-49200:49160-49200/udp",
        "cap_add:",
        "- NET_BIND_SERVICE",
    )
    for setting in required:
        assert setting in coturn
    assert "--allow-loopback-peers" not in coturn
    assert "--cli" not in coturn
    assert "--no-config" not in coturn
    assert "--no-tlsv1" not in coturn
    assert "--no-tlsv1_1" not in coturn
    assert "${M3_TURN_TLS_PORT:-5349}:5349/udp" not in coturn
    assert "49160-49200:49160-49200/tcp" not in coturn
    assert "DETECT_EXTERNAL_IP" not in coturn
    assert "DETECT_RELAY_IP" not in coturn
    assert "openrelayprojectsecret" not in COMPOSE
    assert "aliases:\n          - ${M3_TURN_HOST:" in coturn


def test_turn_rest_issues_short_lived_credentials_on_a_private_network() -> None:
    assert TURN_REST_IMAGE in COMPOSE
    credential_service = COMPOSE.split("\n  turn-rest:\n", maxsplit=1)[1].split(
        "\n  coturn:\n", maxsplit=1
    )[0]
    assert 'TURN_TTL: "3600"' in credential_service
    assert "TURN_SHARED_SECRET: ${M3_TURN_SHARED_SECRET:" in credential_service
    assert "TURN_API_KEY: ${M3_TURN_REST_API_KEY:" in credential_service
    assert "ports:" not in credential_service
    assert "credential" in credential_service
    assert "- /root/.gunicorn" in credential_service
    assert "socket.create_connection(('127.0.0.1', 8008), timeout=2)" in credential_service
    assert "urlopen('http://127.0.0.1:8008/'" not in credential_service
    assert "credential:" in COMPOSE
    assert "internal: true" in COMPOSE.split("credential:", maxsplit=1)[1]


def test_https_proxy_is_host_scoped_and_uses_external_certificates() -> None:
    edge = COMPOSE.split("\n  edge:\n", maxsplit=1)[1].split("\n  retro-session:\n", maxsplit=1)[0]
    assert 'user: "65534:65534"' in edge
    assert "${M3_HTTP_PORT:-80}:8080" in COMPOSE
    assert "${M3_HTTPS_PORT:-443}:8443" in COMPOSE
    assert "__M3_PUBLIC_HOSTNAME__" in TRAEFIK_TEMPLATE
    assert "Host(`__M3_PUBLIC_HOSTNAME__`)" in TRAEFIK_TEMPLATE
    assert "PathPrefix(`/stream/m3`)" in TRAEFIK_TEMPLATE
    assert "entryPoints:\n        - websecure" in TRAEFIK_TEMPLATE
    assert "certFile: /run/secrets/tls_cert" in TRAEFIK_TEMPLATE
    assert "keyFile: /run/secrets/tls_key" in TRAEFIK_TEMPLATE
    assert 'address: ":8443"' in TRAEFIK_STATIC
    assert "checkNewVersion: false" in TRAEFIK_STATIC
    assert "sendAnonymousUsage: false" in TRAEFIK_STATIC
    assert TRAEFIK_STATIC.count("aliasHeadersStrategy: reject") == 2
    assert "scheme: https" in TRAEFIK_STATIC
    assert "accessLog:" not in TRAEFIK_STATIC


def test_transport_overrides_cover_direct_udp_tcp_and_tls() -> None:
    assert 'SELKIES_TURN_REST_URI: ""' in DIRECT_OVERRIDE
    assert "SELKIES_STUN_HOST: ${M3_TURN_HOST:" in DIRECT_OVERRIDE
    assert "SELKIES_TURN_PROTOCOL: tcp" in TCP_OVERRIDE
    assert 'SELKIES_TURN_TLS: "false"' in TCP_OVERRIDE
    assert 'TURN_PROTOCOL: "tcp"' in TCP_OVERRIDE
    assert "SELKIES_TURN_PORT: ${M3_TURN_TLS_PORT:-5349}" in TLS_OVERRIDE
    assert 'SELKIES_TURN_TLS: "true"' in TLS_OVERRIDE
    assert 'TURN_TLS: "true"' in TLS_OVERRIDE


def test_scripts_validate_public_inputs_without_committing_secrets() -> None:
    assert "local/milestone3-cert/" in GITIGNORE
    for setting in (
        "M3_PUBLIC_HOSTNAME",
        "M3_TLS_CERT_FILE",
        "M3_TLS_KEY_FILE",
        "M3_TURN_SHARED_SECRET",
        "M3_TURN_REST_API_KEY",
        "M3_ROM_PATH",
    ):
        assert setting in START_SCRIPT
    assert "milestone3.template.yml" in START_SCRIPT
    assert "MatchesHostname" in START_SCRIPT
    assert '"infra/traefik/dynamic/generated"' in START_SCRIPT
    assert '"milestone3.yml"' in START_SCRIPT
    for transport in ("direct", "turn-udp", "turn-tcp", "turn-tls"):
        assert transport in START_SCRIPT
    expected_refresh = '@("up", "-d", "--no-deps", "--force-recreate", "--wait", "coturn", "edge")'
    assert expected_refresh in START_SCRIPT
    assert "compose.public-test.yml" in STOP_SCRIPT
    assert "New-HexToken" in START_SCRIPT
    assert "openrelayprojectsecret" not in START_SCRIPT


def test_retro_entrypoint_supports_the_trusted_deployment_subfolder() -> None:
    required_subfolder = (
        'readonly STREAM_SUBFOLDER="${SELKIES_SUBFOLDER:?SELKIES_SUBFOLDER is required}"'
    )
    assert required_subfolder in ENTRYPOINT
    assert "${STREAM_SUBFOLDER}/api/health" in ENTRYPOINT
    assert 'SELKIES_USE_CPU: "false"' in GPU_OVERRIDE
