# Netplay hash mismatch

## Trigger

RetroArch rejects Netplay because content or core identity differs between participants.

## Diagnose

1. Record the session ID, platform, and core profile from session diagnostics.
2. Compare runtime logs for the approved core artifact hash and ROM content hash. Record
   only hashes, never ROM filenames or contents.
3. Verify RomM resolves every participant launch to the same trusted ROM record and the
   image manifest reports the same pinned core.

## Recover

Close the affected lobby, reconcile/import the operator-owned library item through RomM,
and rebuild only from the pinned manifest if the core check fails. Never accept a browser
path, disable hash checks, or copy ROM content into logs, Git, images, or test artifacts.
