# wecom-auth-keeper

**Desktop-assisted permission renewal for WeCom CLI automations on macOS.**

[简体中文](README.md) · [Setup](docs/getting-started.md) · [Evidence](docs/validation.md) · [Roadmap](docs/roadmap.md) · [Contributing](CONTRIBUTING.md)

![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
![Status: experimental](https://img.shields.io/badge/status-experimental-orange)

WeCom CLI can refresh its access token, but the business permissions granted to a bot expire separately. In our observations, document read and write permissions each have a seven-day authorization period. Continued API use does not extend it, which can interrupt scheduled reports, spreadsheet synchronization and agent workflows.

This project uses an existing macOS WeCom session to detect expired permissions and interact with the authorization UI. It is a community project, not an official Tencent or WeCom integration.

> **Experimental operations tool.** The repository implements renewal after expiry. Desktop automation has also demonstrated renewal *before* expiry by revoking and re-granting an existing permission, and an experimental `--pre-renew --existing-window` state machine is now implemented. The new standalone implementation has not yet completed live reauthorization acceptance. A logged-in, interactive Mac is required.

## What works today?

| Capability | Status |
|---|---|
| CLI read/write probes | Implemented; production use reported by the author |
| Renew expired permissions through the desktop UI | Implemented; successful recoveries reported by the author |
| Revoke and re-grant before expiry | Demonstrated with a desktop agent; experimental existing-window state machine implemented |
| Independent installation and multi-cycle unattended reliability | Planned |

On September 21, 2026, live desktop automation extended a bot's document read permission from **September 22, 18:01 to September 28, 16:36**, and its write permission to **September 28, 16:39** (Asia/Shanghai). Both persisted after closing and reopening the authorization page. No QR scan or human click was needed. See the [validation record](docs/validation.md) for scope and limitations.

## How it works

`launchd → CLI read/write probes → 850003 → desktop renewal → CLI verification → optional notification`

The pre-expiry route observed in the live session is:

`Bot chat title → Manage → Bot list → Bot details → Available permissions → Authorized dropdown → Revoke → Authorize`

Revocation and reauthorization are separate operations. There is a temporary permission gap; calling applications need coordination and retries.

## Get started

```bash
git clone https://github.com/fyaic/wecom-auth-keeper.git
cd wecom-auth-keeper
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-macos.txt
cp config.example.json config.json
```

Follow the [setup guide](docs/getting-started.md) to configure a bot, a dedicated probe spreadsheet and the local Python environment. Native AX helpers are included; bridge is optional for link delivery, notifications and monitor coordination. Detailed operational documentation is currently in Chinese; English contributions are welcome.

`--doctor` checks local configuration/platform/dependencies without GUI access. `--check` never sends messages or changes authorization/monitor mode, but may open an existing link and writes local state. Add `--existing-window` to prohibit navigation. Experimental `--pre-renew` requires that flag, processes due permissions one at a time, and journals interrupted recovery.

Run repository checks without WeCom or credentials:

```bash
python3 scripts/check_repository.py
python3 -m unittest discover -s tests -v
```

Checks cover repository integrity, recovery state transitions and process boundaries, plus native AX value conversion when macOS dependencies are installed. They are not live reauthorization tests. Unknown states and failed renewal return nonzero exits. Keepalive requires both the GUI result and read/write API probes to pass; see [known limitations](docs/known-limitations.md).

## Help improve it

The next priorities are reliable navigation, independent live validation and repeated expiry-cycle testing. See [Contributing](CONTRIBUTING.md) and the [roadmap](docs/roadmap.md).

Upstream context: [WeCom CLI #87](https://github.com/WecomTeam/wecom-cli/issues/87) and [#134](https://github.com/WecomTeam/wecom-cli/issues/134). The seven-day behavior is an observation, not a guarantee about every account, capability or future platform version.

[MIT License](LICENSE) © 2026 fyaic
