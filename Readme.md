# Mr Expresso — CLI for ExpressVPN

Mr Expresso is a command line interface to control the [ExpressVPN](https://www.expressvpn.com) app. It uses the same native messaging interface as the official ExpressVPN browser extensions.

This is a modern rewrite of [sttz/expresso](https://github.com/sttz/expresso) by **[Adrian Stutz](https://sttz.ch)**, updated for compatibility with the latest ExpressVPN versions (v12+).

> **Credit:** The original [expresso](https://github.com/sttz/expresso) was created by [Adrian Stutz (sttz)](https://github.com/sttz) in C#/.NET. That project is no longer maintained (last updated October 2021) and does not work with recent ExpressVPN versions. Mr Expresso is a from-scratch rewrite based on the same native messaging protocol, with fixes for the latest ExpressVPN API changes.

# Setup

[**Download the latest release here.**](https://github.com/mfq2412/mr-expresso/releases/latest) Mr Expresso is a self-contained executable and has no dependencies.

### Requirements

* [ExpressVPN](https://www.expressvpn.com) desktop app installed and running

### Install

1. Download the zip for your platform from the [releases page](https://github.com/mfq2412/mr-expresso/releases/latest)
2. Extract it
3. Move `mr-expresso` to a directory in your PATH:

```bash
unzip mr-expresso-2.0.0-osx-arm64.zip
sudo mv mr-expresso /usr/local/bin/
mr-expresso --help
```

That's it. No Python, no pip, no dependencies — just the binary.

### How It Works

Mr Expresso communicates with the ExpressVPN desktop app through its browser-extension native messaging helper. This is the same interface used by the official ExpressVPN browser extensions for Chrome, Firefox, and Edge.

The communication uses:
1. **Native Messaging Protocol** — Chrome/Firefox standard length-prefixed JSON over stdin/stdout
2. **JSON-RPC 2.0** — Structured method calls to the ExpressVPN helper daemon

No reverse engineering of the ExpressVPN binary is involved. The native messaging manifests are installed by ExpressVPN itself for its browser extensions.

# Usage

```
mr-expresso v2.0.0

usage: mr-expresso [-h] [--version] [-v] [-q] [-t TIMEOUT]
                   {status,locations,connect,disconnect,repl} ...

Mr Expresso - CLI to control the ExpressVPN app

GLOBAL OPTIONS:
  -h, --help       Show this help message and exit
  --version        Show program's version number and exit
  -v, --verbose    Increase verbosity (-v, -vv, -vvv)
  -q, --quiet      Only show errors
  -t, --timeout    Operation timeout in ms (default: 10000)


---- STATUS:
     Show the current VPN connection status

USAGE: mr-expresso [options] status


---- LOCATIONS:
     List all available VPN locations

USAGE: mr-expresso [options] locations


---- CONNECT:
     Connect to a VPN location

USAGE: mr-expresso [options] connect [--change] [--random] [--toggle] [<location>]

OPTIONS:
  <location>       Location ID, country name, country code, or keyword
  -c, --change     Change location when already connected
  --random         Choose a random server in the given country
  --toggle         Disconnect if already connected (to the given
                   location with --change)


---- DISCONNECT:
     Disconnect from the current VPN location

USAGE: mr-expresso [options] disconnect


---- REPL:
     Interactive mode for raw communication with the helper

USAGE: mr-expresso [options] repl
```

# Examples

### Check status
```
$ mr-expresso status
Connected to 'Singapore - CBD' (singapore-cbd)
```

### List all locations
```
$ mr-expresso locations

--- Africa ---

Algeria (DZ)
  Algeria (algeria)

Egypt (EG)
  Egypt (egypt)
...
```

### Connect by country
```
$ mr-expresso connect Germany
Connecting to 'Germany - Frankfurt - 1' (Germany)...
Connected to 'Germany - Frankfurt - 1'
```

### Connect by location ID
```
$ mr-expresso connect singapore-cbd
Connecting to 'Singapore - CBD'...
Connected to 'Singapore - CBD'
```

### Connect to random server in a country
```
$ mr-expresso connect --random US
Connecting to 'USA - San Francisco' (United States)...
Connected to 'USA - San Francisco'
```

### Toggle connection
```
$ mr-expresso connect --toggle Singapore
Already connected to 'Singapore - CBD', disconnecting...
Disconnected
```

### Change connected location
```
$ mr-expresso connect -c Japan
Connecting to 'Japan - Tokyo' (Japan)...
Connected to 'Japan - Tokyo'
```

### Disconnect
```
$ mr-expresso disconnect
Disconnected
```

### Interactive REPL
```
$ mr-expresso repl
Interactive mode. Type JSON-RPC messages, or use shortcuts:
  status    -> XVPN.GetStatus
  locations -> XVPN.GetLocations
  disconnect-> XVPN.Disconnect
  quit      -> exit
```

# Supported Platforms

| Platform | Status |
|----------|--------|
| macOS    | Tested and working (ExpressVPN v12.1.0) |
| Windows  | Supported (untested on latest) |
| Linux    | Supported (untested) |

# Troubleshooting

### "No native messaging manifest found"
ExpressVPN must be installed. The native messaging manifests are created by ExpressVPN for its browser extensions. Verify they exist:

**macOS:**
```
ls /Library/Application\ Support/Mozilla/NativeMessagingHosts/com.expressvpn.helper.json
ls /Library/Google/Chrome/NativeMessagingHosts/com.expressvpn.helper.json
```

**Linux:**
```
ls /usr/lib/mozilla/native-messaging-hosts/com.expressvpn.helper.json
```

### "Timed out waiting for connection"
Make sure the ExpressVPN desktop app is running (not just installed).

### Verbose output
Use `-v` (info), `-vv` (debug), or `-vvv` (trace) to see what's happening:
```
mr-expresso -vv status
```

# Credits

Mr Expresso is built upon the protocol research and original implementation by **[Adrian Stutz (sttz)](https://github.com/sttz)**.

* **Original project:** [sttz/expresso](https://github.com/sttz/expresso) — C#/.NET CLI for ExpressVPN (2020–2021, MIT License)
* **Original author:** [Adrian Stutz](https://sttz.ch) ([GitHub](https://github.com/sttz))

The original project is no longer maintained and is incompatible with ExpressVPN v12+. Mr Expresso is a complete Python rewrite with protocol fixes for modern ExpressVPN versions.

# License

[MIT](./LICENSE)
