# Deterministic frontend security checker

Standalone scripts. No skill, agent, model, API key, dependency install or AI judgment required.

## Run

From this trusted directory:

```sh
bun run check --config /absolute/path/to/project/frontend-security.config.json
bun run test
```

`check` requires an explicit project configuration and scans only its existing public builds. It **does not build projects**. Artifact paths resolve relative to the configuration file, not the caller's cwd. Missing builds fail as incomplete; they are never silently skipped. Copy `frontend-security.config.example.json` into the target project's root and edit its targets. Harness bundles no personal/production targets.

Only with permission for the configured owned origins:

```sh
bun run check:live --config /absolute/path/to/project/frontend-security.config.json
```

For another project/configuration:

```sh
bun scripts/check.ts --config /absolute/path/to/frontend-security.config.json
# Add --live only when HTTP checks are authorized.
```

## Fixed contract

- Strict versioned configuration: unknown fields, duplicate target names, unsafe URLs and invalid limits fail closed.
- Checked-in filename/content rules in `scripts/policy.ts`; no dynamically generated checks or dependencies.
- Stable traversal and report ordering; no timestamps, random IDs or model-generated verdicts. Identical artifacts, configuration, process environment and HTTP responses produce identical results. Live sites and environment values are inputs, not constants.
- JSON report with `schemaVersion`, `verdict`, `exitCode`, `coverageComplete`, target findings and coverage warnings.
- `0`: assessed checks passed. `1`: findings require review. `2`: incomplete coverage, invalid configuration, missing output, errors or potential HTTP exposure. Both nonzero statuses must fail CI. A format match is not proof of a real/active credential.
- Read-only: no auto-fixes, builds, deployments, pushes, rotations, cache purges or container creation. HTTP and selected-container audits are explicit separate actions.

Example CI step after each project's approved build:

```sh
node /path/to/harness/bin/frontend-security.mjs --config ./frontend-security.config.json
```

Do not suppress a nonzero exit with `|| true`. Never add an exception just to make the check green. Existing project build guards remain authoritative for their source/configuration policy (including disabled automatic Vite env exposure); this tool inspects the actual public output independently.

## Configuration

Your project-owned `frontend-security.config.json` requires:

- `version`: exactly `1`.
- `maxFileMiB`: 1–256; default checked-in value 64.
- `timeoutMs`: 100–30000; checked-in value 8000.
- `compareEnv`: additional required variable **names**. Missing/short values produce incomplete coverage. Never put values in configuration or arguments.
- `publicEnv`: explicitly reviewed, intentionally public variable names excluded from comparison; recorded in reports. No default exemptions.
- `targets`: 1–20 unique `{name, root, origin?}` objects. HTTPS for public origins; loopback HTTP for disposable tests. No credentials, query parameters or fragments in origins. `--live` with a missing origin is incomplete.

Sensitive values in the current process environment are also selected by the fixed name policy and compared in memory. Reports identify this comparison source; they do not imply that production secrets were available locally. No raw env contents, body dumps, matched snippets, secret prefixes or secret fingerprints are emitted. Recognized secret values in metadata/filenames are redacted too.

## Lower-level tools

```sh
bun scripts/audit.ts scan --root /absolute/path/to/public-output
bun scripts/audit.ts probe --url https://owned.example
```

Per-file reads and gzip/Brotli decoding are capped. The artifact scanner has approximately a 512MiB work budget and 100,000-entry limit. Symlinks are not followed; unreadable/oversized files and uninspected archives produce coverage warnings. Prefer immutable release artifacts. HTTP probes use normal TLS validation, make nine bounded requests per configured base URL, do not follow redirects or send authentication, and cap response reads at 64KiB. HTTP 200 SPA fallbacks require review, not an automatic leak verdict.

Optional, explicitly approved Docker/runtime comparison:

```sh
python3 -B scripts/runtime_audit.py --container frontend \
  --compare-env-from approved-backend --web-root /usr/share/nginx/html
```

The standalone runtime helper reads selected environments in memory and inspects the actual web-root tar stream without extracting it or changing containers. It supports local sockets or an existing SSH Docker context; it never disables SSH/TLS verification. Run over an approved SSH alias if needed:

```sh
ssh approved-host 'python3 -B - --container frontend --compare-env-from approved-backend' \
  < scripts/runtime_audit.py
```

## Limits and tests

Deterministic means reproducible decisions for supplied inputs, not exhaustive security proof. Unknown encodings, secrets under innocuous names, visual/screenshot leaks, backend authorization, CI logs/history, third-party runtime configuration and already-downloaded caches are not comprehensively assessed. Read `references/checklist.md` for the separate human review/incident workflow. AI can explain findings and propose changes, but cannot override a failed check.

Tests use generated synthetic values, temporary directories, loopback HTTP and mocked Docker—not production services or credentials. Python runtime tests skip if `python3` is unavailable. An optional agent wrapper may invoke this CLI, but is not required to run or test anything.
