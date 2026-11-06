#!/usr/bin/env bash
# Install the Pines team-screen relay on the Pi. Run at the Pi's keyboard:
#   curl -fsSL https://raw.githubusercontent.com/granviladmin-lab/pines-team-feed/main/install.sh | sudo bash
# It asks for the relay passphrase, which unlocks secrets.enc (GitHub token +
# feed key), then installs and starts pines-relay.service.
set -euo pipefail
BASE=https://raw.githubusercontent.com/granviladmin-lab/pines-team-feed/main
[ "$(id -u)" = 0 ] || { echo "Run with sudo"; exit 1; }
command -v openssl >/dev/null || apt-get install -y openssl

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
curl -fsSL "$BASE/relay.py" -o "$tmp/relay.py"
curl -fsSL "$BASE/secrets.enc" -o "$tmp/secrets.enc"

for try in 1 2 3; do
    printf 'Relay passphrase: ' > /dev/tty
    IFS= read -rs pass < /dev/tty; echo > /dev/tty
    if printf '%s' "$pass" | openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -a \
         -in "$tmp/secrets.enc" -out "$tmp/conf" -pass stdin 2>/dev/null \
         && grep -q '^TOKEN=' "$tmp/conf"; then
        break
    fi
    echo "Wrong passphrase." > /dev/tty
    [ $try = 3 ] && exit 1
done

install -m 600 -o root -g root "$tmp/conf" /etc/pines-relay.conf
install -d /opt/pines-relay
install -m 755 "$tmp/relay.py" /opt/pines-relay/relay.py
cat > /etc/systemd/system/pines-relay.service <<'UNIT'
[Unit]
Description=Pines team screen relay (uploads /api/team for the Roku)
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/pines-relay/relay.py
Restart=always
RestartSec=30
DynamicUser=yes
LoadCredential=conf:/etc/pines-relay.conf
Environment=PINES_RELAY_CONF=%d/conf

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pines-relay.service
sleep 8
journalctl -u pines-relay -n 5 --no-pager
echo "Installed. 'uploaded team.enc' above means the Roku can now see the team screen."
