# Agent entry point

When asked to install this project for a business user, read
[delivery/AGENT-INSTALL.md](delivery/AGENT-INSTALL.md) and
[delivery/FIRST-RUN.md](delivery/FIRST-RUN.md) before running renewal commands.
For a short user-facing introduction, use [delivery/START-HERE.md](delivery/START-HERE.md).

This branch is an internal macOS acceptance candidate. Windows has no automation
backend. Do not describe package integrity, unit tests or a healthy permission
page as proof of successful unattended renewal.

Installation order:

1. Discover the business service's actual CLI profile and intended Bot. Use the
   official CLI to inspect identity; do not read credentials or replace another
   Bot's binding. If missing, complete the official first-time setup separately.
2. Verify the Bot's organization using the native enterprise menu and the Bot's
   official identity. “Manage robots” is not the complete list of usable Bots.
   On WeCom 5.0.13, “查看更多机器人” opens the contacts Bot directory.
   Use config-free `gui.py --action inspect-expanded --python <absolute-python>`
   with a new private evidence directory before Bot IDs are available; never
   fabricate IDs just to run diagnostics.
3. Open this account's private conversation from the verified Bot's details.
   If the permission page is accessible only through a conversation, you may
   first open an empty candidate conversation from a native Bot directory row
   for read-only identity inspection. Do not send or authorize until it matches.
   A new device may have no conversation or renewal link. Prepare and, within the
   user's authorization, send one entry link there; read it back locally. Do not
   send it to a group or another Bot, or search for history that does not exist.
4. Leave the conversation, then use the GUI launchd entry verifier to reopen the
   correct page, read the selected permissions and close it. Preserve its result
   separately from the installer's observation of the private-chat type.
5. Verify real expiry extension by scripts, then a real scheduled trigger, before
   enabling the production schedule. Report entry preparation, renewal and
   scheduling separately. Never delete an entry-receipt requirement to bypass it.

Business users should not need to supply IDs, Secrets or shell commands. Discover
what the device can tell you, and ask only about unresolved business choices or
necessary one-time system/first-access authorization. Respect existing service
constraints; in particular, do not stop or change a Bridge without authorization.
Do not contact others or upload private diagnostics as part of installation.

For repository development, keep real configs and acceptance evidence outside
the release. Build the ZIP with `delivery/build_bundle.py` from committed files;
verify the manifest after extraction and retain the exact tested commit. Runtime
changes require relevant regression tests; live device acceptance remains a
separate requirement. See [delivery/VALIDATION.md](delivery/VALIDATION.md).
