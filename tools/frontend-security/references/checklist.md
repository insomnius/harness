# Audit and hardening checklist

## Scope before commands

- Confirm owned project(s), final browser output and live origins. Identify the web server's real document root, proxy/static routing, retained releases and any server-only bundles.
- Keep audit read-only unless changes/builds are approved. Run helpers from the trusted skill directory with **absolute target paths**, not from an untrusted project cwd that may contain runtime preloads/configuration.
- No env file contents, credential arguments, inspection output, response bodies, matching lines or secret fingerprints in the conversation. Do not use shell tracing. Use approved existing process environments; comparisons never need secret values in command arguments.
- Do not scan unrelated services just because Docker access exists. Runtime comparisons specify their source containers explicitly.

## What is actually public?

Vite's VITE_ variables, Next's NEXT_PUBLIC_ variables, SvelteKit PUBLIC_ variables and similar prefixes signal client visibility, not secrecy. Required public configuration can remain: public API origin, build ID, file hashes, repository/category IDs, appropriately restricted public SDK keys. Review the service's actual security model before classifying a key as public. A private signing/API key never belongs in a browser bundle.

Inspect:

- Explicit defines and object spreads (`process.env`, dotenv/loadEnv output, runtime window config).
- Final HTML/hydration data, JS/CSS, public copies and retained compatibility assets.
- Source-map files and mapping directives, key files, dotfiles, database dumps, package-auth files and env variants.
- CI build/deploy logs and source history only if separately authorized; they are not assessed by the artifact helper.
- Actual generated output, not just source references. Server-only code can legitimately reference private variables without publishing their values.

## Framework-aware hardening

- Vite with explicitly supplied public fields: `envPrefix: []`, explicit reviewed defines and `build.sourcemap: false`. Do not use `envPrefix: ''` (unsafe/invalid), nor serialize all env values into a define.
- Next/Svelte/other SSR stacks: keep secrets in server-only modules/endpoints and enforce client boundaries. Do not treat an entire server output directory as public static content. Audit runtime config/hydration responses too when authorized.
- Avoid debug output that serializes parsed env files. Use trusted parsers without value logging; check guards before compilation so a changed public-prefix policy fails early.
- A canary test uses a generated, obviously synthetic value in a disposable directory. Build output must not contain it; intentional public test metadata should still work. Check failure output is redacted.
- Exclude dotenv variants, package credentials, private keys, `.git`, `.ssh`, build/test outputs as appropriate from Docker contexts. Use build secrets, not COPY/ARG/ENV layers, for private package-registry authentication. Do not break an approved private dependency install without replacing its auth mechanism.
- Serve only the intended static output in lean runtime images. Build-stage files/layers and CI artifacts require a separate access review before publication.

## HTTP defense in depth

An Nginx example to adapt and validate, not blindly append:

```nginx
location ~ (^|/)\.(?!well-known(?:/|$)) { return 404; }
location ~* (?:\.env(?:\.[^/]*)?|\.(?:pem|key|p12|pfx|log|sql|sqlite3?|bak|map))$ { return 404; }
```

Check regex precedence, existing `^~`/exact locations, case/encoding, legitimate `.well-known` paths and private error-page behavior. A SPA fallback can produce public HTML at sensitive paths; do not call a 200 response a leaked env file without evidence. Test an approved disposable staging container with physically present **nonsecret** canary files. Never insert credentials/canaries into the live web root just to prove a deny rule.

Preserve MIME types, video range responses, cache semantics, native controls, authentication, data storage and existing ingress restrictions. Reject maps at the build boundary as well as the web server. Source maps may instead be uploaded privately to an approved error service.

## Incident branch

If confirmed exposure is found:

1. Report secret category/location and scope, no value/snippet/fingerprint.
2. Ask the authorized owner to revoke/rotate through their private secret-management workflow. Do not rotate or retrieve more secrets without approval.
3. Remove the leak and fix the build/serve boundary. Coordinate CDN purges, immutable-cache URL changes, affected deployment artifacts, logs and history as appropriate.
4. Verify the replacement artifact and known owned endpoints. Retained old chunks may still expose a revoked credential; no asset-retention policy should silently retain a secret leak.
5. State that removal/purging cannot erase previously downloaded copies. Never paste credentials into a public issue, commit, report or chat.

## Reporting and limits

Use **confirmed finding**, **potential finding**, **coverage limitation**, **public by design** and **not assessed** explicitly. A clean scan means only the supplied roots/values/patterns were checked. Short secrets, unknown encodings, external runtime config, compressed archives, authenticated variants, client caches, dependency compromise and secrets under innocuous names may need other evidence.

The helpers support raw, JSON-escaped, URL-encoded and base64 known-value comparisons but cannot enumerate arbitrary transformations. Values shorter than eight bytes are not reliably distinguished from ordinary content and are reported as limited coverage. Links/large unreadable files/archives must never be silently counted as clean. Regex scans do not replace source review, a proper credential scanner, dependency review or backend authorization testing.

A final report should say exactly what passed and what did not. Keep report/log values redacted. Builds, commits, deployments, rotation and purges are separate actions, not implicit consequences of invoking this skill.
