![psync logo - a sketch of a pigeon behind the word 'psync'](./.doc/logo.png)

**psync** is a simple tool to sync your project over SSH. It consists of a
client and server.

## Features

-

## Example usecase

I am working on a [game
project](https://cubething.dev/qproj/general-introduction). Compiling a game
written in Rust requires a lot of CPU power, but I want to be able to build from
my low-end laptop. I already have my machines hooked up to SSH into each other.
So, I set up the client on my laptop, use my editor to SSH into my desktop
server, and sync the build assets from the desktop to the laptop using psync.
**Note that while the desktop is the server _for the editor_, it is the client
for psync.** Similar for the laptop.

## Usage

When you want to run the project, you must build it and then execute the psync
client. The client will sync the files and send a start message to the server.
This starts up the synced executable on the server machine. The server will send
logs and listen for events, e.g. shutdown messages (sent with SIGINT).

### Server

The server should be set up on the machine which is to _recieve_
the files. This corresponds to the laptop in the example usecase.

Ideally you should run the server as a daemon, for example using the systemd
config included in this repository.

### Client

The client should be invoked on the machine which is to _send_ the files. This
corresponds to the desktop in the example usecase. After every build, the client
should be run. The client will then sync the files. Once this is done, recieve
logs from the server.

## Security

This is implemented around
[python-socket.io](https://python-socketio.readthedocs.io/en/stable/index.html),
so please consult [their webpage](https://socket.io) for any concerns.

### SSL

Please generate an SSL certificate. You can use the following one-line if you'd
like.

```sh
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 3650 -nodes \
    -subj "/C=XX/ST=StateName/L=CityName/O=CompanyName/OU=CompanySectionName/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:psync-server,IP:127.0.0.1"
```

Note that this sets an alternate name as psync-server. This will be useful when
deploying to docker.
