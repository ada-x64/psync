psync
===================================

.. caution::

    This project is not guaranteed to be secure. Use at your own risk.

`psync` is a simple synchronization-and-execution server based on rsync and websockets.

Features
--------

- Project syncing with rsync (requires ssh)
- Execute project binary on daemon host
- Real-time logging based on websockets
- Natural Ctrl-C / SIGINT handling on client and server
- SSL authentication
- Containerized for easy deployment

Example usecase
---------------

I am working on a `game project`_ . Compiling a game
written in Rust requires a lot of CPU power, but I want to be able to build from
my low-end laptop. I already have my machines hooked up to SSH into each other.
So, I set up the client on my laptop, use my editor to SSH into my desktop
server, and sync the build assets from the desktop to the laptop using psync.
Note that while the desktop is the server the editor, it is the client
for psync. Similar for the laptop.

.. _game project: https://cubething.dev/qproj/general-introduction

Security
--------

Psync communicates over a secure websocket connection. The connection is typically achieved with a
self-signed certificate which is accepted client-side. In addition, the server checks for an acceptable
Origin header on the initial websocket handshake, though this can easily be spoofed. Initial project
synchonization occurs over rsync with SSH as the transport layer. All in all, psync is only as secure
as you make it. As such, I do not recommend running this on a public-facing server unless you really
know what you're doing.

About the bird
--------------

The logo is based on the `carrier pigeon`_, an early form of telecommunication. The illustration comes from
`The Big Book of Bird Illustrations`_, by Maggie Kate.

.. _carrier pigeon: https://en.wikipedia.org/wiki/Homing_pigeon
.. _The Big Book of Bird Illustrations: https://store.doverpublications.com/products/9780486135977

Contents
--------

.. toctree::

    usage
    api
