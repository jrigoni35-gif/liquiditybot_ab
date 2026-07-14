"""
scripts/tailnet_forward.py — make a tailnet TCP service look local.

Userspace tailscaled (no TUN device, as in cloud containers) cannot
expose 100.x addresses to ordinary sockets, so anything that dials a
fixed host:port — e.g. the moomoo feed's OpenD probe of 127.0.0.1:11111
— can't reach a peer directly. This forwarder listens locally and pipes
each connection through `tailscale nc`, which dials via the daemon.

Sidecar plumbing, never imported by the engine. Example (moomoo OpenD
shared from the PC with `tailscale serve --tcp 11111 ...`):

  python scripts/tailnet_forward.py \
      --tailscale /path/to/tailscale --socket /path/to/ts.sock \
      --dest 100.77.167.23 --port 11111

On a machine with the standard Tailscale install (TUN present) this is
unnecessary — point the client at the 100.x address directly.
"""
import argparse
import asyncio
import sys


async def _pump(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        try:
            writer.close()
        except Exception:  # nosec B110
            pass          # teardown of an already-dead pipe


def _handler(opts):
    async def handle(client_reader, client_writer):
        proc = await asyncio.create_subprocess_exec(
            opts.tailscale, f"--socket={opts.socket}", "nc",
            opts.dest, str(opts.port),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL)
        try:
            await asyncio.gather(
                _pump(client_reader, proc.stdin),
                _pump(proc.stdout, client_writer))
        finally:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            client_writer.close()
    return handle


async def _serve(opts):
    server = await asyncio.start_server(
        _handler(opts), opts.listen, opts.listen_port or opts.port)
    print(f"forwarding {opts.listen}:{opts.listen_port or opts.port} -> "
          f"tailnet {opts.dest}:{opts.port}", flush=True)
    async with server:
        await server.serve_forever()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tailscale", required=True,
                    help="path to the tailscale CLI binary")
    ap.add_argument("--socket", required=True,
                    help="tailscaled control socket path")
    ap.add_argument("--dest", required=True, help="tailnet peer 100.x IP")
    ap.add_argument("--port", type=int, required=True,
                    help="destination TCP port on the peer")
    ap.add_argument("--listen", default="127.0.0.1",
                    help="local bind address (default 127.0.0.1)")
    ap.add_argument("--listen-port", type=int, default=0,
                    help="local port (default: same as --port)")
    opts = ap.parse_args()
    try:
        asyncio.run(_serve(opts))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
