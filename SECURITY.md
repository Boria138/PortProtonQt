# Security Policy

## Reporting a vulnerability

Do not publish suspected vulnerability details in public issues, discussions,
or pull requests. Send reports to [support@linux-gaming.ru](mailto:info@linux-gaming.ru).

Please include enough information to reproduce and assess the issue:

- PortProtonQt version or commit and installation source.
- Linux distribution and relevant launcher or runtime details.
- Affected feature and clear reproduction steps.
- Expected behavior, observed behavior, and potential security impact.
- A minimal proof of concept or sanitized logs, if available.
- A suggested mitigation or fix, if known.

Do not include passwords, tokens, private keys, or personal data. Redact
usernames, home directory paths, and other sensitive details from logs where
practical. Test only with systems, accounts, and files you own or are
authorized to use.

## Scope

This policy covers security issues in PortProtonQt, including its handling of
local files and archives, launcher data, network requests, downloaded content,
and application configuration. Issues in third-party launchers, libraries,
compatibility tools, or distribution packages should also be reported to their
maintainers. Please report cases where PortProtonQt's handling creates or
increases the risk.

## Supported versions

Please check whether the issue affects the latest published release and
include the affected version in your report. Older releases may not receive
security fixes; users should update when a fix becomes available.

## Coordinated disclosure

Keep vulnerability details private while maintainers investigate and prepare a
fix or mitigation. Coordinate public disclosure with the maintainers, allowing
reasonable time for a fix to reach users. Response and remediation times depend
on the issue; no fixed response time is promised.
