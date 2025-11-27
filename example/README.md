How to use this folder:

In first terminal, run the server.

```sh
uv run server
```

Then, sync the project exectuable.

```sh
uv run client -p ./example/example.py
```

By default, this syncs to your local machine at
`~/.local/share/psync/${PROJECT_HASH}`. You can change the project settings by
following the documentation.
