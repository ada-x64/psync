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

The network should be secure. I recommend that you **do not run this over the WAN**, and if you do,
you should use a secure tunnel like `zerotier`_.

.. _zerotier: https://zerotier.com

Server
------

It is recommend to run the server in a docker container. This improve security
by isolating binaries, and improves ease of setup. You can run the server
manually, or the server can be set up to run as a daemon on Linux with a simple
systemd service.

First, create a directory for your docker-compose file, for example at
``/opt/psync``.

You can configure it like this:

.. code-block:: yaml

    ---
    services:
        psync-server:
            image: ghcr.io/ada-x64/psync-server
            container_name: psync-server
            ports:
                - "5000:5000"
            environment:
                - PSYNC_ORIGINS=my-client-ip
            volumes:
                - /path/to/my/cert:/app/cert.pem:r
                - /path/to/my/key:/app/key.pem:r

Refer to the :doc:`server documentation <generated/server.main>` for environment
configuration.

Next, create a systemd configuration file. I recommend storing this at
``etc/systemd/system`` so it opens at system boot. Additionally, you should
create a new user with minimal permissions to run the service. This will avoid
admin access to your system in case of bad actor intervention. This can be done as follows:

.. code-block :: bash

    sudo useradd psync -M -s /sbin/nologin

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
