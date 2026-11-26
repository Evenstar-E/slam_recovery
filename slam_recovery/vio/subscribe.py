"""Independent Unix-socket pose subscriber that records each delivery before ACK."""
import argparse
import json
from pathlib import Path
import socket
import time


def receive(address, output):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(address))
        listener.listen(1)
        try:
            connection, _ = listener.accept()
            with connection, connection.makefile("rb") as stream, output.open("x") as log:
                previous = None
                for number, line in enumerate(stream, 1):
                    instant = time.monotonic_ns()
                    row = json.loads(line)
                    stamp = row["timestamp"]
                    if row["delivery_id"] != number or previous is not None and stamp <= previous:
                        raise ValueError("delivery IDs or physical timestamps are not increasing")
                    print(json.dumps(dict(row, received_ns=instant), allow_nan=False),
                          file=log, flush=True)
                    connection.sendall(f"{number}\n".encode())
                    previous = stamp
        finally:
            address.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("socket", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    receive(args.socket, args.output)


if __name__ == "__main__":
    main()
