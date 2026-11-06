# pines-team-feed

Feed for the Pines Team TV Roku channel. `team.enc` is the Pi's team screen
data, encrypted; it is updated by `relay.py` running on the Pi. The channel
plays `background.mp4` behind it.

Install the relay on the Pi (asks for the relay passphrase):

    curl -fsSL https://raw.githubusercontent.com/granviladmin-lab/pines-team-feed/main/install.sh | sudo bash

Check it there with `journalctl -u pines-relay -f`.
