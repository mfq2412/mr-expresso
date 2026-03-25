# Mr Expresso CLI for ExpressVPN

mr-expresso is a command line interface to control the ExpressVPN app. It uses the same native messaging interface as the ExpressVPN browser extension.

Based on the original [expresso](https://github.com/sttz/expresso) by [Adrian Stutz (sttz)](https://github.com/sttz), rewritten for compatibility with modern ExpressVPN versions (v12+).

# Setup

[Download the latest release here](https://github.com/mfq2412/mr-expresso/releases). mr-expresso is a self-contained executable and has no dependencies.

### Install

```bash
# 1. Download and extract
curl -L -o mr-expresso.zip https://github.com/mfq2412/mr-expresso/releases/latest/download/mr-expresso-2.0.0-osx-arm64.zip
unzip mr-expresso.zip

# 2. Install to your PATH
sudo mv mr-expresso /usr/local/bin/

# 3. Verify
mr-expresso --version
```

# Usage

```
mr-expresso v2.0.0

USAGE: mr-expresso [--help] [--version] [--verbose...] [--quiet] [--timeout <arg>]
                   <action>

GLOBAL OPTIONS:
 -h, --help       Show this help
     --version    Print the version of this program
 -v, --verbose    Increase verbosity of output, can be repeated
 -q, --quiet      Only output necessary information and errors
 -t, --timeout <arg>  Override the default connect/disconnect timeout (in
                  milliseconds)


---- LOCATIONS:
     List all available VPN locations

USAGE: mr-expresso [options] locations


---- STATUS:
     Show the current VPN connection status

USAGE: mr-expresso [options] status


---- CONNECT:
     Connect to a VPN location

USAGE: mr-expresso [options] connect [--change] [--random] [--toggle] [<location>]

OPTIONS:
 -c, --change     Change current location when already connected
     --random     Choose a random location in the given country
     --toggle     Disconnect instead when already connected (to the given
                  location with --change)
 <location>       Location to connect to, either location id, country or
                  keyword


---- DISCONNECT:
     Disconnect from the current VPN location

USAGE: mr-expresso [options] disconnect


---- REPL:
     Interactively communicate with the helper

USAGE: mr-expresso [options] repl
```

# Credits

mr-expresso is based on the original [expresso](https://github.com/sttz/expresso) by [Adrian Stutz (sttz)](https://github.com/sttz). The original project was written in C#/.NET and is no longer maintained (last updated October 2021). mr-expresso is a complete rewrite with protocol fixes for ExpressVPN v12+.

# License

[MIT](./LICENSE)
