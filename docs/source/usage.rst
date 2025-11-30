Usage
=====

Setup
-----

You will need to be able to reciprocally SSH into your target machines. The
below describes my setup, though you can set it up however you'd like.

.. image:: ../static/psync-info-light.png
    :align: center
    :class: only-light

.. image:: ../static/psync-info-dark.png
    :align: center
    :class: only-dark

The network should be secure. Psync messages are unencrypted, so I recommend
that you **do not expose your psync ports over the WAN**, and if you do, you
should use a secure ethernet-over-WAN server like `zerotier`_.

.. _zerotier: https://zerotier.com

Server
------

It is recommend to run the server in a docker container. This improves security
by isolating binaries, and improves ease of setup. You can run the server
manually, or the server can be set up to run as a daemon on Linux with a simple
systemd service.

Docker setup
^^^^^^^^^^^^

First, create a directory for your docker-compose file, for example at
``/opt/psync``. This can be done as follows:

.. code-block:: bash

    # make the dir, create the compose file
    sudo mkdir /opt/psync
    sudo touch docker-compose.yml

    # optional: add psync user
    sudo useradd -Ms /usr/sbin/nologin psync
    sudo chown psync /opt/psync
    sudo chmod g+rw /opt/psync
    sudo usermod -aG psync $(whoami)
    newgrp psync


Then, generate your self-signed SSL certificate:

.. code-block :: bash

    cd /opt/psync #or wherever
    # Generate a public/private keypair
    openssl req -x509 -newkey rsa:4096 \
        -keyout key.pem -out cert.pem \
        -sha256 -days 3650 -nodes \
        -subj "/C=XX/ST=StateName/L=CityName/O=CompanyName/OU=CompanySectionName/CN=$MY_IP" \
        -addext "subjectAltName=DNS:localhost,DNS:psync-server,IP:127.0.0.1,IP:$MY_IP"


You can configure it like this:

.. code-block:: yaml

    ---
    services:
        psync-server:
            image: ghcr.io/ada-x64/psync-server
            container_name: psync-server
            ports:
                - "5000:5000" # expose the psync websocket server
                - "5022:22" # expose the SSH server
            environment:
                # Required to accept connections from your client machine
                # I recommend allowing localhost / 127.0.0.1 here for testing
                - PSYNC_ORIGINS="client.ip.1 client.ip.2"
            volumes:
                - ./cert.pem:/app/cert.pem:ro
                - ./key.pem:/app/key.pem:ro
                - ~/.ssh/authorized_keys:/app/authorized_keys.src:ro

Importantly, **the SSH server is set up to only accept authorized keys.** This
should be your default anyways. Follow any guide to set up your SSH keys and SSH
server; this will automatically copy the authorized keys to the docker container.

Note that whenever you restart the docker container

Refer to the :doc:`server documentation <generated/server.main>` for environment
configuration.

Daemon setup
^^^^^^^^^^^^

Next, create a systemd configuration file. I recommend storing this at
``etc/systemd/system`` so it opens at system boot. Additionally, you should
create a new user with minimal permissions to run the service. This will avoid
admin access to your system in case of bad actor intervention. This can be done as follows:

.. code-block :: bash

    sudo useradd psync -M -s /sbin/nologin
    sudo usermod psync -aG docker

``/etc/systemd/system/psync.service``

.. code-block:: systemd

    [Unit]
    Description=Psync Daemon
    After=network.target

    [Service]
    User=psync
    ExecStart=/usr/bin/docker compose -f /opt/psync/docker-compose.yml up
    Restart=on-failure
    RestartSec=1

    ProtectSystem=full
    PrivateTmp=true
    NoNewPrivileges=true

    [Install]
    WantedBy=multi-user.target


Client
------

The client is intended to be invoked as a CLI script. First, you will need to install it.
Use your favorite package manager. I use uv.

.. code-block :: bash

    uv tool install cubething_psync

Then, you should be able to access it from the command line.

.. code-block :: bash

    psync-client --help

Refer to the help command and the :doc:`api docs <./generated/client.main>` for
more details.

**You will need to manually add a certificate to trust the server.** Copy the
certificate you generated for the server to your client machine at
`~/.local/share/psync`. (If you want to use a different directory, set it using
the `PSYNC_CERT_PATH` environment variable.)
