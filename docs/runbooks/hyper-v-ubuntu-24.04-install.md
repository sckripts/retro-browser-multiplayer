# Hyper-V Ubuntu 24.04 installation runbook

This runbook installs the production Compose model on an Ubuntu Server 24.04 LTS
`amd64` virtual machine hosted by Hyper-V. It starts with LAN-restricted access and
does not add Internet router forwarding until the local deployment passes verification.

The repository-root `compose.yml` is the only production topology. Milestone Compose
files and scripts under `infra/compose/acceptance` and `infra/scripts/acceptance` are
regression tools, not deployment inputs.

## 1. Record site-specific values

Choose these values before logging in to the VM. Examples are documentation values;
replace every angle-bracket placeholder.

| Setting | Example | Required value |
|---|---|---|
| VM IPv4 address | `192.168.10.20` | `<vm-ip>` |
| IPv4 prefix | `/24` | `<prefix>` |
| Router/default gateway | `192.168.10.1` | `<gateway-ip>` |
| DNS resolver | `192.168.10.1` | `<dns-ip>` |
| Linux interface | `eth0` | `<vm-interface>` |
| Administrator source address | `192.168.10.50/32` | `<admin-cidr>` |
| Initial test-client range | `192.168.10.0/24` | `<test-client-cidr>` |
| Linux operator account | `retroadmin` | `<operator-user>` |
| Public application name | `games.example.net` | `<public-hostname>` |
| authentik name | `auth.example.net` | `<auth-hostname>` |
| TURN name | `turn.example.net` | `<turn-hostname>` |
| Certificate contact | `operator@example.net` | `<certificate-email>` |
| Deployment repository | approved Git remote | `<deployment-repository-url>` |
| Deployment commit | release commit SHA | `<deployment-commit>` |
| RomM fork URL | separate AGPL fork | `<romm-fork-url>` |
| RomM fork commit | full 40-character SHA | `<romm-commit>` |

Use three names under a real domain that the operator controls. The production
validator rejects raw IP endpoints and `.test` or `.example` names. Do not use the
example names in the table.

## 2. Confirm the Hyper-V VM

Before installing Ubuntu, confirm:

- Generation 2 VM;
- Secure Boot enabled with the **Microsoft UEFI Certificate Authority** template;
- 8 virtual processors;
- 24 GiB static memory for the initial two-player test;
- OS VHDX of at least 64 GiB;
- empty data/build VHDX of at least 150 GiB;
- Hyper-V synthetic network adapter attached to an external virtual switch;
- automatic checkpoints disabled;
- no GPU assignment for the first deployment.

Install Ubuntu Server 24.04 LTS `amd64` on only the OS VHDX. Select OpenSSH during
installation. Do not format the second VHDX in the installer unless it is unmistakably
identified.

After the VM boots, establish a Hyper-V console session and log in. Keep that console
open while changing networking or firewall settings so an SSH mistake is recoverable.

## 3. Update Ubuntu and establish time

```bash
sudo apt update
sudo DEBIAN_FRONTEND=noninteractive apt full-upgrade -y
sudo apt install -y ca-certificates curl git jq nano openssh-server openssl parted ufw wget
sudo systemctl enable --now ssh
sudo timedatectl set-timezone America/Chicago
timedatectl status
sudo reboot
```

Reconnect through the Hyper-V console after the reboot.

Confirm the expected release and architecture:

```bash
source /etc/os-release
printf 'release=%s architecture=%s\n' "$PRETTY_NAME" "$(dpkg --print-architecture)"
```

Expected: Ubuntu 24.04 LTS and `amd64`.

## 4. Configure a stable LAN address

A DHCP reservation on the router is preferred because it avoids hand-editing Netplan.
Find the guest MAC and current address:

```bash
ip -br link
ip -br address
ip route
```

Create a DHCP reservation for `<vm-ip>`, renew the lease or reboot, and verify:

```bash
ip -4 -br address show dev <vm-interface>
ip route get 1.1.1.1
getent hosts github.com
```

Do not continue until the VM retains `<vm-ip>` after a reboot.

If router-based reservation is impossible, use Ubuntu's current Netplan configuration
for the installed renderer. Apply Netplan changes from the Hyper-V console with
`sudo netplan try`; do not use `netplan apply` over an unprotected SSH-only session.

## 5. Prepare the second VHDX

This section destroys the selected second disk. First identify both disks by size and
serial information:

```bash
lsblk -o NAME,PATH,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL,SERIAL
sudo fdisk -l
```

Stop if the empty data VHDX cannot be distinguished from the OS disk. In the commands
below, replace `/dev/sdX` with the verified empty data disk. Never substitute the disk
that contains `/`.

```bash
sudo parted --script /dev/sdX mklabel gpt
sudo parted --script /dev/sdX mkpart primary ext4 1MiB 100%
sudo partprobe /dev/sdX
sudo mkfs.ext4 -L retrobrowser-data /dev/sdX1
sudo mkdir -p /srv
sudo blkid /dev/sdX1
```

Copy the UUID printed by `blkid`. Edit `/etc/fstab`:

```bash
sudoedit /etc/fstab
```

Add one line, replacing `<data-filesystem-uuid>`:

```text
UUID=<data-filesystem-uuid> /srv ext4 defaults,noatime 0 2
```

Test the entry before rebooting:

```bash
sudo mount -a
findmnt --verify
findmnt /srv
df -h /srv
```

Create the deployment layout:

```bash
sudo install -d -o root -g root -m 0711 /srv/docker
sudo install -d -o <operator-user> -g <operator-user> -m 0750 /srv/src
sudo install -d -o <operator-user> -g <operator-user> -m 0750 /srv/retrobrowser
sudo install -d -o <operator-user> -g <operator-user> -m 0750 /srv/retrobrowser/library
sudo install -d -o <operator-user> -g <operator-user> -m 0750 /srv/retrobrowser/userdata
sudo install -d -o <operator-user> -g <operator-user> -m 0750 /srv/retrobrowser/saves
sudo install -d -o <operator-user> -g <operator-user> -m 0750 /srv/retrobrowser/routes
sudo install -d -o <operator-user> -g <operator-user> -m 0750 /srv/retrobrowser/metrics-targets
sudo install -d -o <operator-user> -g <operator-user> -m 0700 /srv/retrobrowser/tls
```

Reboot once and confirm `/srv` mounts automatically:

```bash
sudo reboot
```

After reconnecting:

```bash
findmnt /srv
df -h /srv
```

## 6. Establish SSH and the host firewall

Install the operator's SSH public key. Test a second SSH session using the key before
disabling password authentication.

Edit the SSH server configuration through a drop-in:

```bash
sudoedit /etc/ssh/sshd_config.d/10-retrobrowser-hardening.conf
```

Use:

```text
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
```

Validate and reload without closing the working console/session:

```bash
sudo sshd -t
sudo systemctl reload ssh
```

Configure UFW for host-local services. UFW does not, by itself, protect Docker-published
ports; Docker forwarding is handled separately in step 9.

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow proto tcp from <admin-cidr> to <vm-ip> port 22 comment 'restricted SSH'
sudo ufw logging low
sudo ufw --dry-run enable
sudo ufw enable
sudo ufw status verbose
```

Open a new SSH session before continuing. If it fails, correct the rule through the
Hyper-V console.

## 7. Install Docker Engine and Compose

Install Docker from Docker's official Ubuntu repository. Do not install Ubuntu's
`docker.io`, `docker-compose`, or standalone containerd packages.

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudoedit /etc/apt/sources.list.d/docker.sources
```

Enter:

```text
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
```

Then install:

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Move Docker's data root to the second VHDX and bound local log growth:

```bash
sudo systemctl stop docker docker.socket
sudoedit /etc/docker/daemon.json
```

Use:

```json
{
  "data-root": "/srv/docker",
  "log-driver": "local",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Do not set Docker's `iptables` or `ip6tables` options to `false`. Do not enable the
experimental nftables backend for this deployment.

Start and verify Docker:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now docker
sudo docker info
sudo docker compose version
sudo docker run --rm hello-world
sudo docker info --format '{{.DockerRootDir}}'
```

Expected Docker root: `/srv/docker`.

The Docker group is root-equivalent. Add only the dedicated operator account:

```bash
sudo usermod -aG docker <operator-user>
```

Log out and back in. Verify without `sudo`:

```bash
docker version
docker compose version
docker info --format '{{.DockerRootDir}}'
```

Confirm the Docker daemon has no network listener:

```bash
sudo ss -lntp | grep -E ':2375|:2376' || true
```

Expected: no matching listener.

## 8. Install PowerShell 7

Microsoft's package repository is the supported installation route on Ubuntu 24.04:

```bash
sudo apt update
sudo apt install -y apt-transport-https software-properties-common wget
source /etc/os-release
wget -q "https://packages.microsoft.com/config/ubuntu/$VERSION_ID/packages-microsoft-prod.deb"
sudo dpkg -i packages-microsoft-prod.deb
rm packages-microsoft-prod.deb
sudo apt update
sudo apt install -y powershell
pwsh --version
```

## 9. Add Docker-aware LAN firewall rules

Docker publishes container ports through forwarding rules that can bypass normal UFW
input policy. The following dedicated chain permits only the initial test-client CIDR
to the six configured public port groups, then drops other externally initiated Docker
traffic arriving on the VM's LAN interface.

Create the firewall script:

```bash
sudoedit /usr/local/sbin/retrobrowser-docker-firewall
```

Paste the following after replacing `<vm-interface>` and `<test-client-cidr>`:

```bash
#!/usr/bin/env bash
set -euo pipefail

RB_EXTERNAL_INTERFACE="<vm-interface>"
RB_TEST_CLIENT_CIDR="<test-client-cidr>"
RB_CHAIN="RETROBROWSER-FILTER"

iptables -w -N "$RB_CHAIN" 2>/dev/null || true
iptables -w -F "$RB_CHAIN"
iptables -w -C DOCKER-USER -j "$RB_CHAIN" 2>/dev/null || \
  iptables -w -I DOCKER-USER 1 -j "$RB_CHAIN"

iptables -w -A "$RB_CHAIN" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
iptables -w -A "$RB_CHAIN" -i "$RB_EXTERNAL_INTERFACE" -s "$RB_TEST_CLIENT_CIDR" \
  -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport 80 -j RETURN
iptables -w -A "$RB_CHAIN" -i "$RB_EXTERNAL_INTERFACE" -s "$RB_TEST_CLIENT_CIDR" \
  -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport 443 -j RETURN
iptables -w -A "$RB_CHAIN" -i "$RB_EXTERNAL_INTERFACE" -s "$RB_TEST_CLIENT_CIDR" \
  -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport 3478 -j RETURN
iptables -w -A "$RB_CHAIN" -i "$RB_EXTERNAL_INTERFACE" -s "$RB_TEST_CLIENT_CIDR" \
  -p udp -m conntrack --ctdir ORIGINAL --ctorigdstport 3478 -j RETURN
iptables -w -A "$RB_CHAIN" -i "$RB_EXTERNAL_INTERFACE" -s "$RB_TEST_CLIENT_CIDR" \
  -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport 5349 -j RETURN
iptables -w -A "$RB_CHAIN" -i "$RB_EXTERNAL_INTERFACE" -s "$RB_TEST_CLIENT_CIDR" \
  -p udp -m conntrack --ctdir ORIGINAL --ctorigdstport 49160:49200 -j RETURN
iptables -w -A "$RB_CHAIN" -i "$RB_EXTERNAL_INTERFACE" \
  -m conntrack --ctdir ORIGINAL -j DROP
iptables -w -A "$RB_CHAIN" -j RETURN
```

Install it and run it once:

```bash
sudo chmod 0750 /usr/local/sbin/retrobrowser-docker-firewall
sudo /usr/local/sbin/retrobrowser-docker-firewall
sudo iptables -S DOCKER-USER
sudo iptables -S RETROBROWSER-FILTER
```

Make Docker reapply the policy after every daemon start:

```bash
sudo systemctl edit docker.service
```

Enter:

```ini
[Service]
ExecStartPost=/usr/local/sbin/retrobrowser-docker-firewall
```

Then verify a Docker restart does not lose the chain:

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
sudo iptables -S RETROBROWSER-FILTER
```

This initial policy is IPv4-only and the Compose bindings use an explicit IPv4
`BIND_ADDRESS`. Do not publish AAAA records or enable public IPv6 until an equivalent
IPv6 policy has been designed and externally tested.

## 10. Configure DNS

Create public DNS A records for the three real names. They may initially point to the
site's public address even while router forwarding remains disabled.

Configure the LAN DNS resolver with split-horizon overrides:

```text
<public-hostname>  -> <vm-ip>
<auth-hostname>    -> <vm-ip>
<turn-hostname>    -> <vm-ip>
```

From both intended test clients and the VM, verify:

```bash
getent ahostsv4 <public-hostname>
getent ahostsv4 <auth-hostname>
getent ahostsv4 <turn-hostname>
```

The LAN clients must resolve all three names to `<vm-ip>`. Do not continue if the
names resolve to an old host.

## 11. Obtain TLS certificates

Obtain a certificate whose Subject Alternative Names cover all three hostnames. A
DNS-01 ACME challenge is preferred because it requires no inbound port forwarding.
Use the DNS provider's maintained Certbot plugin when available so renewal can be
automated.

For a temporary manually renewed test certificate:

```bash
sudo apt install -y certbot
sudo certbot certonly --manual --preferred-challenges dns \
  --agree-tos --no-eff-email --email <certificate-email> \
  -d <public-hostname> -d <auth-hostname> -d <turn-hostname>
```

Follow Certbot's TXT-record instructions and wait for public DNS propagation before
continuing. Then copy the active material into the protected deployment directory:

```bash
sudo install -o <operator-user> -g <operator-user> -m 0644 \
  /etc/letsencrypt/live/<certificate-name>/fullchain.pem \
  /srv/retrobrowser/tls/fullchain.pem
sudo install -o <operator-user> -g <operator-user> -m 0600 \
  /etc/letsencrypt/live/<certificate-name>/privkey.pem \
  /srv/retrobrowser/tls/privkey.pem
```

Verify names and dates without printing the private key:

```bash
openssl x509 -in /srv/retrobrowser/tls/fullchain.pem -noout -dates -subject -ext subjectAltName
```

Manual DNS certificates do not renew unattended. Replace this with a DNS-provider
plugin and a deploy hook that refreshes the protected copies before production use.

## 12. Prepare authenticated SMTP

Obtain an SMTP submission account or provider-specific application password. Record:

- server hostname;
- port, normally 587 for STARTTLS or 465 for implicit TLS;
- username;
- password/application password;
- allowed From address;
- initial administrator email.

Do not use an open relay. The production configuration requires SMTP because authentik
owns passwordless email authentication and account recovery.

## 13. Check out the deployment repository

```bash
cd /srv/src
git clone <deployment-repository-url> retro-browser-multiplayer
cd /srv/src/retro-browser-multiplayer
git checkout --detach <deployment-commit>
git status --short
git rev-parse HEAD
```

`git status --short` must be empty and `git rev-parse HEAD` must equal the recorded
deployment commit.

Run the repository content audit:

```bash
pwsh -NoProfile -File ./tools/repository-audit/verify-public.ps1 -IncludeHistory
```

## 14. Obtain the separate RomM integration fork

The complete multiplayer deployment cannot use the stock `rommapp/romm` image. It
requires the separately licensed AGPL RomM fork containing the external multiplayer
provider.

Hard stop: the public repository currently does not identify a usable fork URL and
full accepted commit SHA. Obtain and record both before continuing. Do not substitute
an unreviewed branch tip or a shortened SHA.

Once available:

```bash
cd /srv/src
git clone <romm-fork-url> romm-integration
git -C /srv/src/romm-integration checkout --detach <romm-commit>
git -C /srv/src/romm-integration status --short
git -C /srv/src/romm-integration rev-parse HEAD
```

The worktree must be clean and the reported SHA must exactly match the recorded
40-character commit. Preserve the corresponding source and license information for
every network-accessible build distributed or deployed.

## 15. Initialize production state

```bash
cd /srv/src/retro-browser-multiplayer
pwsh -NoProfile -File ./infra/scripts/production/initialize.ps1
chmod 0600 .env.production
```

The initializer generates independent secrets without printing them. Never commit,
email, or paste `.env.production` into a ticket.

Edit it locally:

```bash
nano .env.production
```

Set at least:

```dotenv
PUBLIC_HOSTNAME=<public-hostname>
AUTH_HOSTNAME=<auth-hostname>
TURN_HOST=<turn-hostname>
TURN_REALM=<turn-hostname>

TLS_CERT_FILE=/srv/retrobrowser/tls/fullchain.pem
TLS_KEY_FILE=/srv/retrobrowser/tls/privkey.pem

BIND_ADDRESS=<vm-ip>
HTTP_PORT=80
HTTPS_PORT=443
TURN_PORT=3478
TURN_TLS_PORT=5349
TURN_RELAY_MIN_PORT=49160
TURN_RELAY_MAX_PORT=49200

ROM_ROOT=/srv/retrobrowser/library
USER_DATA_ROOT=/srv/retrobrowser/userdata
SAVE_DATA_ROOT=/srv/retrobrowser/saves
ROUTE_CONFIG_ROOT=/srv/retrobrowser/routes
METRICS_TARGET_ROOT=/srv/retrobrowser/metrics-targets

SMTP_HOST=<smtp-hostname>
SMTP_PORT=587
SMTP_USERNAME=<smtp-username>
SMTP_PASSWORD=<smtp-application-password>
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_FROM=<smtp-from-address>
ADMIN_EMAIL=<administrator-email>

GPU_PROFILES=cpu
DEFAULT_GPU_PROFILE=cpu
RUNTIME_CAPACITY=2
SESSION_CAPACITY=1
PER_USER_RUNTIME_CAPACITY=1
RUNTIME_MEMORY_BYTES=4294967296
RUNTIME_NANO_CPUS=2000000000
RUNTIME_PIDS_LIMIT=1024

OBSERVABILITY_BIND_ADDRESS=127.0.0.1
GRAFANA_PORT=3000
```

For implicit SMTP TLS on port 465, use `SMTP_USE_TLS=false` and
`SMTP_USE_SSL=true`. Never enable both modes simultaneously.

Leave the four image variables blank until the next step. Preserve every generated
secret already written by the initializer.

## 16. Build the four immutable images

Confirm at least 60 GiB free before a clean build:

```bash
df -h /srv /srv/docker
docker system df
```

Build Runtime Agent, Session Manager, Retro Session, and the separate RomM integration
image. The helper verifies the RomM commit and clean worktree, then writes local
content-addressed image references to `.env.production`:

```bash
cd /srv/src/retro-browser-multiplayer
pwsh -NoProfile -File ./infra/scripts/production/build-images.ps1 \
  -RomMSource /srv/src/romm-integration \
  -RomMCommit <romm-commit>
```

Do not interrupt the Retro Session build while it compiles RetroArch and the approved
cores. Confirm the four references resolve without printing the rest of the environment:

```bash
grep -E '^(RUNTIME_AGENT_IMAGE|SESSION_MANAGER_IMAGE|RETRO_SESSION_IMAGE|ROMM_IMAGE)=' .env.production
docker compose --env-file .env.production --file compose.yml config --images
```

Each custom reference must contain `@sha256:`.

## 17. Validate and start

Before starting, confirm the router still has no Internet port-forwarding rules for
this VM.

```bash
cd /srv/src/retro-browser-multiplayer
pwsh -NoProfile -File ./infra/scripts/production/start.ps1
```

The script validates required settings, immutable image references, absolute host
paths, SMTP mode, certificate validity and SANs, rendered Compose configuration, and
container health.

Inspect state without exposing environment values:

```bash
docker compose --env-file .env.production --file compose.yml ps
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
sudo ss -lntup
sudo iptables -S RETROBROWSER-FILTER
```

Expected host bindings are:

- `<vm-ip>` TCP 80 and 443;
- `<vm-ip>` TCP and UDP 3478;
- `<vm-ip>` TCP 5349;
- `<vm-ip>` UDP 49160-49200;
- `127.0.0.1` TCP 3000;
- SSH TCP 22 restricted by UFW to `<admin-cidr>`.

No database, Valkey, Runtime Agent, Session Manager, Selkies, RetroArch, Docker API,
or TURN REST port may be publicly bound.

## 18. Complete first-time application setup

1. Open `https://<auth-hostname>` from the administrator workstation.
2. Sign in with the emergency `akadmin` account and the generated
   `AUTHENTIK_BOOTSTRAP_PASSWORD` stored in `.env.production`.
3. Confirm the **Retro Browser RomM OIDC** blueprint applied successfully.
4. Create two active test users with distinct email addresses. Mark each address as
   verified according to the authentik administrative workflow.
5. Open `https://<public-hostname>` and complete RomM's one-time setup wizard. Preserve
   the resulting local RomM administrator as an emergency administrative path.
6. Test the authentik/OIDC sign-in flow separately for both users using different
   browser profiles.

Do not use two private windows from the same browser if they share cookies.

## 19. Add authorized test content

Place only content the operator is entitled to use under the external library root.
Never copy ROMs or BIOS images into the Git checkout, a container image, CI artifact,
or support bundle.

Use RomM's documented library layout and scan/import workflow. Confirm RomM displays
the game before attempting a multiplayer session. Start with one approved platform
profile and a legally redistributable homebrew test title.

## 20. Run automated verification

```bash
cd /srv/src/retro-browser-multiplayer
pwsh -NoProfile -File ./infra/scripts/production/verify.ps1 -RequireClean
```

The verifier checks the rendered model, expected running services, Runtime Agent,
zero leftover participant runtimes, the public RomM heartbeat, and browser security
headers.

## 21. Run the LAN browser acceptance

From two physical LAN clients in `<test-client-cidr>`:

1. Confirm all three hostnames resolve to `<vm-ip>`.
2. Confirm browsers trust the certificate with no exception page.
3. Sign in as two distinct authentik users in independent browser profiles.
4. Open the same game page for both users.
5. Create a named multiplayer session as user one.
6. Join it as user two.
7. Open each participant's player in a separate browser window.
8. Verify video, audio, keyboard/controller input, and synchronized game state.
9. Have user two leave.
10. Have the owner close the session.
11. Run `verify.ps1 -RequireClean` again.

Evaluate streaming from the physical clients, not through Remote Desktop to the
Hyper-V host. A private LAN test may select a direct ICE path. Full TURN relay
acceptance requires the remote test in the next step.

## 22. Validate external exposure before forwarding

From another LAN machine, scan the VM:

```bash
nmap -Pn -sT -p- <vm-ip>
sudo nmap -Pn -sU -p 3478,49160-49200 <vm-ip>
```

Only the intended TCP services should appear. UDP scanning is not definitive and must
be followed by WebRTC/TURN evidence.

Review the guest again:

```bash
sudo ufw status verbose
sudo iptables -S DOCKER-USER
sudo iptables -S RETROBROWSER-FILTER
sudo ss -lntup
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

## 23. Optional remote TURN test

Only after the LAN checks pass, forward these router ports to `<vm-ip>`:

| Public port | Protocol |
|---|---|
| 80 | TCP |
| 443 | TCP |
| 3478 | TCP and UDP |
| 5349 | TCP |
| 49160-49200 | UDP |

Do not forward SSH, Grafana, Docker API, database, Valkey, or internal application
ports.

For arbitrary remote clients, change `RB_TEST_CLIENT_CIDR` in
`/usr/local/sbin/retrobrowser-docker-firewall` only after deciding that public testing
is authorized. Re-run the script and inspect the resulting chain. During a controlled
test, a narrow known remote source range is safer than immediately allowing all IPv4
addresses.

Test from a phone hotspot or other off-site network. Confirm the browser's WebRTC
diagnostics show a selected `relay` candidate and that coturn metrics increase. A LAN
client may require router hairpin/U-turn NAT because coturn advertises the public IP.

## 24. Stop, restart, and recover

Normal stop preserves named volumes, host data, secrets, ROMs, and saves:

```bash
cd /srv/src/retro-browser-multiplayer
pwsh -NoProfile -File ./infra/scripts/production/stop.ps1
```

Normal restart:

```bash
pwsh -NoProfile -File ./infra/scripts/production/start.ps1
pwsh -NoProfile -File ./infra/scripts/production/verify.ps1 -RequireClean
```

If startup fails, collect state before changing anything:

```bash
docker compose --env-file .env.production --file compose.yml ps
docker compose --env-file .env.production --file compose.yml logs --tail 200
df -h
docker system df
sudo journalctl -u docker --since '-30 minutes' --no-pager
```

Treat logs as sensitive. Do not post credentials, launch URLs, tokens, user identifiers,
ROM paths, or save contents.

Do not remove named volumes or `/srv/retrobrowser` as a troubleshooting shortcut.

## 25. Required follow-up before general use

The first successful installation is still a deployment trial. Before inviting users:

- automate certificate renewal and test a renewal restart;
- back up `.env.production`, TLS material, authentik PostgreSQL, RomM MariaDB,
  RomM assets/resources, saves, and per-user data through an encrypted process;
- perform a clean-machine restore drill;
- perform secret-rotation and rollback drills;
- retain the four deployed immutable image references and the two source commit SHAs;
- configure monitoring and disk-capacity alerts;
- patch Ubuntu and Docker on a staged schedule;
- repeat external port scans after Compose, Docker, or firewall changes;
- complete the outstanding production-hardening acceptance recorded in the project
  documentation.

Hyper-V checkpoints are not a substitute for these backups. If a checkpoint is used
before a risky test, stop the stack first and remove the checkpoint after the test so
database differencing disks do not become permanent state.

## Reference documentation

- [Project production deployment](../deployment.md)
- [Project network and TURN model](../networking.md)
- [Project public-release hygiene](../public-release.md)
- [Docker Engine installation on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Docker packet filtering and `DOCKER-USER`](https://docs.docker.com/engine/network/firewall-iptables/)
- [PowerShell installation on Ubuntu](https://learn.microsoft.com/powershell/scripting/install/install-ubuntu)
- [Microsoft Linux on Hyper-V practices](https://learn.microsoft.com/windows-server/virtualization/hyper-v/best-practices-for-running-linux-on-hyper-v)
- [Ubuntu firewall documentation](https://documentation.ubuntu.com/server/how-to/security/firewalls/)
