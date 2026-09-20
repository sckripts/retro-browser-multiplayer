# Entrypoint

The Milestone 2 proof entrypoint accepts one image-defined ROM mount path and one pinned
ROM hash. It validates the read-only mount and all artifacts, fixes the X display, logs
versions/hashes, and replaces itself with RetroArch. The finish hook terminates the
container when RetroArch exits. A later milestone will replace proof constants with a
validated typed RuntimeSpec; browser-provided shell text is never allowed.
