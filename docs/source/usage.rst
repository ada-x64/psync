Usage
=====

Server
------

It is recommend to run the server in a docker container. You can run the server
manually, or the server can be set up to run as a daemon on Linux with a simple
systemd service.

First, create a directory for your docker-compose file, for example at
``/opt/psync``.

.. code-block:: yaml

    ---
    services:
        psync-server:
            image: ghcr.io:ada-x64/psync-server
            container_name: psync-server
            ports:
                - "5000:5000"
            environment:
                - PSYNC_ORIGINS=my-client-ip

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
