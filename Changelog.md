# Changelog

### 2.0.0 (2026-03-26) — Mr Expresso
* Complete rewrite in Python (zero dependencies, no build step)
* Compatible with ExpressVPN v12+ (tested on v12.1.0)
* Added Chrome and Edge native messaging manifest search paths
* Fixed country-based connection requiring location ID in newer ExpressVPN
* Fixed status display using `selected_location` fallback for newer protocol
* Added Linux support for native messaging paths
* Added interactive REPL shortcuts for common commands
* Cross-platform: macOS, Windows, Linux

---

*Prior versions (C#/.NET) by [Adrian Stutz (sttz)](https://github.com/sttz/expresso):*

### 1.3.0 (2021-10-10)
* Added `status` command
* Added `--toggle` option to `connect` command
* Fixed country name and code not matched case-insensitively in `connect`

### 1.2.1 (2021-06-15)
* Increase connection timeout for Windows (@lord-ne)

### 1.2.0 (2021-06-12)
* Add Windows support (@lord-ne)
* Switch from CoreRT to .Net 6 preview for single-file builds

### 1.1.0 (2020-12-19)
* Enable changing connected location with `--change` or `-c`
* Add `--random` option to connect to random location in country

### 1.0.2 (2020-04-17)
* Fix timeout when connecting to the already selected location

### 1.0.1 (2020-04-16)
* Fix browser extension showing the last selected instead of the currently connected location

### 1.0.0 (2020-04-12)
* Initial release by Adrian Stutz
