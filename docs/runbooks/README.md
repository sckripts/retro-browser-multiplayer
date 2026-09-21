# Runbooks

Deployment:

- [Hyper-V Ubuntu 24.04 installation](hyper-v-ubuntu-24.04-install.md)

Milestone 18 operational runbooks:

- [Stream will not connect](stream-will-not-connect.md)
- [TURN relay failure](turn-relay-failure.md)
- [Controller not detected](controller-not-detected.md)
- [Netplay hash mismatch](netplay-hash-mismatch.md)
- [Orphan runtime](orphan-runtime.md)
- [Authentication login failure](auth-login-failure.md)
- [GPU encoder exhaustion](gpu-encoder-exhaustion.md)

Runbooks preserve evidence first, use the narrow Runtime Agent API for lifecycle work,
and never print or copy tokens, credentials, ROM paths, save contents, or Docker socket
data into tickets.
