#!/usr/bin/env python3
"""
Mr Expresso - CLI to control the ExpressVPN app.

A Python rewrite of https://github.com/sttz/expresso by Adrian Stutz,
updated for compatibility with modern ExpressVPN versions (v12+).

Communicates with the ExpressVPN desktop app through its browser-extension
native messaging helper using the Chrome/Firefox native messaging protocol
(length-prefixed JSON over stdin/stdout) and JSON-RPC 2.0.

Original C# implementation: https://github.com/sttz/expresso (MIT License)
Original author: Adrian Stutz (sttz.ch)
"""

import argparse
import json
import os
import platform
import random
import struct
import subprocess
import sys
import threading
import time
from queue import Queue, Empty

__version__ = "2.0.0"

# ---------------------------------------------------------------------------
# Native Messaging Client
# ---------------------------------------------------------------------------

_MANIFEST_PATHS_MAC = [
    os.path.expanduser("~/Library/Application Support/Mozilla/NativeMessagingHosts"),
    "/Library/Application Support/Mozilla/NativeMessagingHosts",
    os.path.expanduser("~/Library/Application Support/Google/Chrome/NativeMessagingHosts"),
    "/Library/Google/Chrome/NativeMessagingHosts",
    os.path.expanduser("~/Library/Application Support/Microsoft Edge/NativeMessagingHosts"),
    "/Library/Microsoft/Edge/NativeMessagingHosts",
]

_MANIFEST_PATHS_LINUX = [
    "/usr/lib/mozilla/native-messaging-hosts",
    "/usr/lib64/mozilla/native-messaging-hosts",
    os.path.expanduser("~/.mozilla/native-messaging-hosts"),
    os.path.expanduser("~/.config/google-chrome/NativeMessagingHosts"),
    "/etc/opt/chrome/native-messaging-hosts",
    os.path.expanduser("~/.config/microsoft-edge/NativeMessagingHosts"),
]

_MANIFEST_PATHS_WIN = []
if platform.system() == "Windows":
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    _MANIFEST_PATHS_WIN = [
        os.path.join(pf86, "ExpressVPN", "expressvpnd"),
        os.path.join(pf, "ExpressVPN", "expressvpnd"),
    ]

MANIFEST_SEARCH_PATHS = {
    "Darwin": _MANIFEST_PATHS_MAC,
    "Linux": _MANIFEST_PATHS_LINUX,
    "Windows": _MANIFEST_PATHS_WIN,
}


class NativeMessagingClient:
    """Communicate with a native messaging host (Chrome/Firefox protocol)."""

    def __init__(self, manifest_name, verbose=0):
        self.verbose = verbose
        self._recv_queue = Queue()
        self._process = None

        system = platform.system()
        search_paths = MANIFEST_SEARCH_PATHS.get(system, [])
        if not search_paths:
            search_paths = _MANIFEST_PATHS_MAC + _MANIFEST_PATHS_LINUX + _MANIFEST_PATHS_WIN

        self._manifest_path = None
        for base in search_paths:
            candidate = os.path.join(base, manifest_name + ".json")
            if os.path.isfile(candidate):
                self._manifest_path = candidate
                break

        if self._manifest_path is None:
            raise FileNotFoundError(
                f"No native messaging manifest found for '{manifest_name}'.\n"
                f"Searched in: {search_paths}\n"
                f"Is ExpressVPN installed?"
            )

        with open(self._manifest_path, "r") as f:
            text = "\n".join(
                line for line in f.read().splitlines()
                if not line.strip().startswith("//")
            )
        self._manifest = json.loads(text)

        if self._manifest.get("type") != "stdio":
            raise ValueError(
                f"Unsupported native messaging type '{self._manifest.get('type')}', "
                f"only 'stdio' is supported."
            )

        helper_path = self._manifest["path"]
        if not os.path.isfile(helper_path):
            raise FileNotFoundError(
                f"Helper binary specified in manifest does not exist: {helper_path}"
            )

        self._log(1, f"Manifest loaded: {self._manifest_path}")
        self._log(1, f"Helper binary: {helper_path}")

        allowed = (
            self._manifest.get("allowed_extensions")
            or self._manifest.get("allowed_origins")
            or ["unknown"]
        )
        first_ext = allowed[0]

        cmd = [helper_path, self._manifest_path, first_ext]
        self._log(2, f"Launching: {cmd}")
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self._recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._recv_thread.start()

    def _log(self, level, msg):
        if self.verbose >= level:
            prefix = "DEBUG" if level >= 2 else "INFO"
            print(f"[{prefix}] {msg}", file=sys.stderr)

    def send(self, message):
        """Send a JSON message using length-prefixed protocol."""
        data = json.dumps(message, separators=(",", ":")).encode("utf-8")
        length = struct.pack("<I", len(data))
        self._log(2, f"-> {data.decode()}")
        try:
            self._process.stdin.write(length)
            self._process.stdin.write(data)
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise ConnectionError(f"Failed to send to helper: {e}")

    def receive(self, timeout=0.0):
        """Receive the next message, or None if none pending."""
        try:
            if timeout > 0:
                return self._recv_queue.get(timeout=timeout)
            return self._recv_queue.get_nowait()
        except Empty:
            return None

    def _receive_loop(self):
        """Background thread reading length-prefixed JSON from helper stdout."""
        try:
            while self._process.poll() is None:
                length_bytes = self._read_exact(4)
                if length_bytes is None:
                    break
                length = struct.unpack("<I", length_bytes)[0]
                if length > 10 * 1024 * 1024:
                    self._log(0, f"Message too large: {length} bytes")
                    break
                data = self._read_exact(length)
                if data is None:
                    break
                text = data.decode("utf-8")
                self._log(2, f"<- {text}")
                try:
                    msg = json.loads(text)
                    self._recv_queue.put(msg)
                except json.JSONDecodeError as e:
                    self._log(0, f"Invalid JSON from helper: {e}")
        except Exception as e:
            self._log(0, f"Receive loop error: {e}")
        exit_code = self._process.poll()
        self._log(1, f"Helper process exited with code {exit_code}")

    def _read_exact(self, n):
        """Read exactly n bytes from stdout."""
        buf = b""
        while len(buf) < n:
            chunk = self._process.stdout.read(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    @property
    def is_alive(self):
        return self._process is not None and self._process.poll() is None


# ---------------------------------------------------------------------------
# ExpressVPN Client
# ---------------------------------------------------------------------------

class ExpressVPNClient:
    """High-level client for controlling ExpressVPN via its browser helper."""

    DEFAULT_MANIFEST = (
        "com.expressvpn.helper.firefox" if platform.system() == "Windows"
        else "com.expressvpn.helper"
    )

    def __init__(self, verbose=0):
        self.verbose = verbose
        self._native = NativeMessagingClient(self.DEFAULT_MANIFEST, verbose)

        self.is_connected_to_helper = False
        self.app_version = None
        self.latest_status = {}
        self.locations = []
        self.default_location_id = None
        self.recent_location_ids = []
        self.recommended_location_ids = []

        self._callbacks = {
            "connected": [],
            "status_update": [],
            "full_status_update": [],
            "locations_updated": [],
            "connection_progress": [],
        }
        self._process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._process_thread.start()

    def _log(self, level, msg):
        if self.verbose >= level:
            prefix = "DEBUG" if level >= 2 else "INFO"
            print(f"[{prefix}] {msg}", file=sys.stderr)

    def _call(self, method, params=None):
        """Send a JSON-RPC 2.0 call."""
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1,
        }
        self._native.send(msg)

    def _process_loop(self):
        """Continuously process incoming messages."""
        while self._native.is_alive:
            msg = self._native.receive(timeout=0.05)
            if msg is None:
                continue
            try:
                self._handle_message(msg)
            except Exception as e:
                self._log(0, f"Error handling message: {e}")

    def _handle_message(self, msg):
        if "error" in msg:
            self._log(0, f"Error from helper: {msg['error']}")
            return

        if msg.get("connected"):
            self.is_connected_to_helper = True
            self.app_version = msg.get("app_version", "unknown")
            self._log(1, f"Connected to ExpressVPN v{self.app_version}")
            self._fire("connected")
            return

        if "info" in msg:
            self.latest_status = msg["info"]
            self._fire("status_update")
            self._fire("full_status_update")
            return

        if "name" in msg:
            name = msg["name"]
            data_wrapper = msg.get("data", {})
            data = data_wrapper.get(f"{name}Data", {})

            if name == "ServiceStateChanged":
                new_state = data.get("newstate") or data.get("state")
                if new_state:
                    self.latest_status["state"] = new_state
                    self._fire("status_update")

            elif name == "ConnectionProgress":
                progress = data.get("progress", 0)
                self._fire("connection_progress", progress)

            elif name == "SelectedLocationChanged":
                sel = self.latest_status.get("selected_location", {})
                for key in ("id", "name", "is_country", "is_smart_location"):
                    if key in data:
                        sel[key] = data[key]
                self.latest_status["selected_location"] = sel
                self._fire("status_update")

            elif name == "WaitForNetworkReady":
                pass

            else:
                self._log(1, f"Unhandled named event: {name}")
            return

        if "locations" in msg:
            self.locations = msg.get("locations", [])
            dl = msg.get("default_location")
            if isinstance(dl, dict):
                self.default_location_id = dl.get("id")
            self.recent_location_ids = msg.get("recent_locations_ids", [])
            self.recommended_location_ids = msg.get("recommended_location_ids", [])
            self._fire("locations_updated")
            return

        if "Preferences" in msg or "messages" in msg or "success" in msg:
            return

        self._log(1, f"Unhandled message: {json.dumps(msg)[:200]}")

    def _fire(self, event, *args):
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args)
            except Exception as e:
                self._log(0, f"Callback error for {event}: {e}")

    def _wait_for_event(self, event, timeout):
        flag = threading.Event()
        def handler(*_args):
            flag.set()
        self._callbacks[event].append(handler)
        try:
            return flag.wait(timeout=timeout)
        finally:
            self._callbacks[event].remove(handler)

    # --- Public API ---

    def wait_for_connection(self, timeout=10.0):
        if self.is_connected_to_helper:
            return
        if not self._wait_for_event("connected", timeout):
            raise TimeoutError(
                "Timed out waiting for connection to ExpressVPN helper.\n"
                "Is ExpressVPN running?"
            )

    def update_status(self, timeout=5.0):
        self._call("XVPN.GetStatus")
        if not self._wait_for_event("full_status_update", timeout):
            raise TimeoutError("Timed out waiting for status update.")

    def get_locations(self, timeout=5.0):
        self._call("XVPN.GetLocations", {
            "include_default_location": True,
            "include_recent_connections": True,
        })
        if not self._wait_for_event("locations_updated", timeout):
            raise TimeoutError("Timed out waiting for locations.")

    def get_location(self, location_id):
        for loc in self.locations:
            if loc.get("id") == location_id:
                return loc
        return None

    def select_location(self, selected, timeout=5.0):
        self._call("XVPN.SelectLocation", {"selected_location": selected})
        self._wait_for_event("status_update", timeout)

    def connect(self, args, timeout=30.0):
        state = self.latest_status.get("state")

        if state != "connected":
            selected = {
                "id": args.get("id", ""),
                "name": args.get("country") or args.get("name", ""),
                "is_country": bool(args.get("country")),
                "is_smart_location": args.get("is_default", False),
            }
            current_sel = self.latest_status.get("selected_location", {})
            if current_sel.get("name") != selected["name"]:
                self.select_location(selected)

        self._call("XVPN.Connect", args)

        was_connected = (state == "connected")
        deadline = time.time() + timeout
        last_progress = None

        def on_progress(p):
            nonlocal last_progress
            last_progress = p

        self._callbacks["connection_progress"].append(on_progress)
        try:
            while time.time() < deadline:
                s = self.latest_status.get("state", "")
                if last_progress is not None:
                    self._log(0, f"Connecting... {last_progress:.1f}%")
                    last_progress = None
                if s == "connected" and not was_connected:
                    return
                if was_connected and s not in ("connected", "disconnecting"):
                    was_connected = False
                if not was_connected and s == "connected":
                    return
                if s not in ("ready", "connecting", "reconnecting", "disconnecting", "connected"):
                    raise RuntimeError(f"Connection failed, state: {s}")
                time.sleep(0.1)
        finally:
            self._callbacks["connection_progress"].remove(on_progress)

        s = self.latest_status.get("state", "")
        if s == "connected":
            return
        raise TimeoutError(f"Timed out waiting to connect (state: {s}).")

    def disconnect(self, timeout=10.0):
        if self.latest_status.get("state") != "connected":
            raise RuntimeError("VPN is not connected.")

        self._call("XVPN.Disconnect")

        deadline = time.time() + timeout
        while time.time() < deadline:
            s = self.latest_status.get("state", "")
            if s == "ready":
                return
            if s not in ("connected", "disconnecting"):
                raise RuntimeError(f"Unexpected state while disconnecting: {s}")
            time.sleep(0.1)

        raise TimeoutError("Timed out waiting to disconnect.")


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------

def cmd_status(client, _args):
    state = client.latest_status.get("state", "unknown")
    if state == "connected":
        loc = client.latest_status.get("current_location", {})
        sel = client.latest_status.get("selected_location", {})
        name = loc.get("name") or sel.get("name") or "?"
        loc_id = loc.get("id") or sel.get("id") or "?"
        print(f"Connected to '{name}' ({loc_id})")
    elif state == "ready":
        print("VPN not connected")
    else:
        print(f"ExpressVPN state: {state}")


def cmd_locations(client, _args):
    client.get_locations()
    if not client.locations:
        print("No locations available.")
        return

    locs = sorted(
        client.locations,
        key=lambda l: (l.get("region", ""), l.get("country", ""), l.get("name", "")),
    )
    last_region = None
    last_country = None
    for loc in locs:
        region = loc.get("region", "")
        country = loc.get("country", "")
        if region != last_region:
            print(f"\n--- {region} ---")
            last_region = region
            last_country = None
        if country != last_country:
            print(f"\n{country} ({loc.get('country_code', '')})")
            last_country = country
        print(f"  {loc.get('name', '?')} ({loc.get('id', '?')})")


def cmd_connect(client, args):
    client.get_locations()
    if not client.locations:
        raise RuntimeError("Could not load location list.")

    connect_args = {}
    connect_country = None

    if not args.location:
        if not client.default_location_id:
            raise RuntimeError("No default location returned.")
        default_loc = client.get_location(client.default_location_id)
        if not default_loc:
            raise RuntimeError(f"Default location '{client.default_location_id}' not found.")
        print(f"Connecting to default location '{default_loc['name']}'...", file=sys.stderr)
        connect_args = {"id": default_loc["id"], "name": default_loc["name"], "is_default": True}
    else:
        query = args.location
        country_locs = [
            l for l in client.locations
            if l.get("country", "").lower() == query.lower()
            or l.get("country_code", "").lower() == query.lower()
        ]

        if country_locs:
            if args.random:
                chosen = random.choice(country_locs)
            else:
                chosen = country_locs[0]
            connect_country = chosen
            print(f"Connecting to '{chosen['name']}' ({chosen['country']})...", file=sys.stderr)
            connect_args = {"id": chosen["id"], "name": chosen["name"], "country": chosen["country"]}
        else:
            best = None
            best_priority = 0
            for loc in client.locations:
                if best_priority < 2 and loc.get("id") == query:
                    best = loc
                    best_priority = 2
                elif best_priority < 1 and query.lower() in loc.get("name", "").lower():
                    best = loc
                    best_priority = 1
            if not best:
                raise RuntimeError(f"No location found for '{query}'.")
            print(f"Connecting to '{best['name']}'...", file=sys.stderr)
            connect_args = {"id": best["id"], "name": best["name"]}

    state = client.latest_status.get("state")
    if state == "connected":
        current = client.latest_status.get("current_location", {})
        # In newer ExpressVPN, selected_location may have the name when current_location doesn't
        current_name = (
            current.get("name")
            or client.latest_status.get("selected_location", {}).get("name")
            or "unknown"
        )
        current_id = current.get("id") or client.latest_status.get("selected_location", {}).get("id")
        if args.toggle and (
            not args.change
            or current_id == connect_args.get("id")
            or (connect_country and current.get("country") == connect_country.get("country"))
        ):
            print(f"Already connected to '{current_name}', disconnecting...", file=sys.stderr)
            client.disconnect(timeout=args.timeout / 1000)
            print("Disconnected")
            return
        if not args.change:
            raise RuntimeError(
                f"Already connected to '{current_name}'.\n"
                f"Use --change or -c to change the currently connected location."
            )
        connect_args["change_connected_location"] = True

    client.connect(connect_args, timeout=args.timeout / 1000)
    # Refresh status to get the connected location details
    try:
        client.update_status(timeout=5.0)
    except TimeoutError:
        pass
    loc = client.latest_status.get("current_location", {})
    name = loc.get("name") or connect_args.get("name", "?")
    print(f"Connected to '{name}'")


def cmd_disconnect(client, args):
    client.disconnect(timeout=args.timeout / 1000)
    print("Disconnected")


def cmd_repl(client, _args):
    print("Interactive mode. Type JSON-RPC messages, or use shortcuts:")
    print("  status    -> XVPN.GetStatus")
    print("  locations -> XVPN.GetLocations")
    print("  disconnect-> XVPN.Disconnect")
    print("  quit      -> exit")
    print()

    shortcuts = {
        "status": {"jsonrpc": "2.0", "method": "XVPN.GetStatus", "params": {}, "id": 1},
        "locations": {"jsonrpc": "2.0", "method": "XVPN.GetLocations",
                      "params": {"include_default_location": True, "include_recent_connections": True}, "id": 1},
        "disconnect": {"jsonrpc": "2.0", "method": "XVPN.Disconnect", "params": {}, "id": 1},
    }

    def print_incoming():
        while True:
            msg = client._native.receive(timeout=0.1)
            if msg:
                print(f"\n<< {json.dumps(msg, indent=2)}")
                print("> ", end="", flush=True)

    t = threading.Thread(target=print_incoming, daemon=True)
    t.start()

    try:
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                break
            if not line:
                continue
            if line.lower() == "quit":
                break
            if line.lower() in shortcuts:
                client._native.send(shortcuts[line.lower()])
                continue
            try:
                msg = json.loads(line)
                client._native.send(msg)
            except json.JSONDecodeError:
                print("Invalid JSON. Enter a valid JSON-RPC message or use a shortcut.")
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="mr-expresso",
        description="Mr Expresso - CLI to control the ExpressVPN app",
    )
    parser.add_argument("--version", action="version", version=f"expresso v{__version__}")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase verbosity (-v, -vv, -vvv)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Only show errors")
    parser.add_argument("-t", "--timeout", type=int, default=10000,
                        help="Operation timeout in ms (default: 10000)")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    sub.add_parser("status", help="Show current VPN connection status")
    sub.add_parser("locations", help="List all available VPN locations")

    cp = sub.add_parser("connect", help="Connect to a VPN location")
    cp.add_argument("location", nargs="?", default=None,
                     help="Location ID, country name, country code, or keyword")
    cp.add_argument("-c", "--change", action="store_true",
                     help="Change location when already connected")
    cp.add_argument("--random", action="store_true",
                     help="Choose a random server in the given country")
    cp.add_argument("--toggle", action="store_true",
                     help="Disconnect if already connected to given location")

    sub.add_parser("disconnect", help="Disconnect from current VPN location")
    sub.add_parser("repl", help="Interactive mode for raw communication")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    verbose = 0 if args.quiet else args.verbose

    try:
        client = ExpressVPNClient(verbose=verbose)
        client.wait_for_connection()

        if verbose >= 1:
            print(f"[INFO] Connected to ExpressVPN v{client.app_version}", file=sys.stderr)

        if args.command != "repl":
            client.update_status()

        commands = {
            "status": cmd_status,
            "locations": cmd_locations,
            "connect": cmd_connect,
            "disconnect": cmd_disconnect,
            "repl": cmd_repl,
        }
        cmd_fn = commands.get(args.command)
        if cmd_fn:
            cmd_fn(client, args)
        else:
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        sys.exit(130)
    except (FileNotFoundError, TimeoutError, RuntimeError, ConnectionError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if verbose >= 1:
            import traceback
            traceback.print_exc()
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
