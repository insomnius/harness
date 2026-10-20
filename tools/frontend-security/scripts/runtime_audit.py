#!/usr/bin/env python3
"""Read-only, standalone Docker web-root audit. Safe to pipe over verified SSH.
No extraction, env/body output, credential arguments or container changes.
"""
import argparse
import base64
import io
import json
import os
import re
import subprocess
import tarfile
import urllib.parse

SENSITIVE = re.compile(r"secret|password|token|credential|private[_-]?key|api[_-]?key|access[_-]?key|database_url|connection_string|dsn", re.I)
PATTERNS = [
    ("private-key", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ("github-token", r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    ("api-token", r"\bsk-[A-Za-z0-9_-]{20,}"),
    ("gitlab-token", r"\bglpat-[A-Za-z0-9_-]{20,}"),
    ("aws-access-key", r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
]


def variants(value):
    encoded = value.encode()
    return sorted({value, json.dumps(value, ensure_ascii=False)[1:-1],
                   urllib.parse.quote(value, safe="~!*'()-._"),
                   base64.b64encode(encoded).decode(),
                   base64.urlsafe_b64encode(encoded).decode().rstrip("=")}, key=len, reverse=True)


def redact(value, secrets):
    if isinstance(value, str):
        for secret in secrets.values():
            for form in variants(secret):
                value = value.replace(form, "[REDACTED]")
        for _, pattern in PATTERNS:
            value = re.sub(pattern, "[REDACTED]", value)
        return re.sub(r"[\x00-\x1f\x7f]", "[CONTROL]", value)
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, dict):
        return {key: redact(item, secrets) for key, item in value.items()}
    return value


def private_path(name):
    parts = name.replace("\\", "/").split("/")
    return (any(part.startswith(".") and part != ".well-known" for part in parts)
            or parts[0] in ("src", "scripts", "deployment", "node_modules")
            or bool(re.search(r"(?:\.env(?:\.[^/]*)?|\.(?:pem|key|p12|pfx|map|log|sql|sqlite3?|db|bak)(?:-wal|-shm)?)$", name, re.I))
            or bool(re.search(r"(?:^|/)(?:id_rsa|id_ed25519|credentials|Dockerfile|docker-compose\.ya?ml)$", name, re.I)))


def capture(args, maximum, timeout=60):
    """Bound output before buffering; never forward CLI stderr/exception details."""
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as child:
        # communicate() is unbounded; spool neither secrets nor archives to disk.
        import threading
        timer = threading.Timer(timeout, child.kill)
        timer.start()
        try:
            output = child.stdout.read(maximum + 1)
            if len(output) > maximum:
                child.kill()
                raise RuntimeError("command-output-budget-exceeded")
            if child.wait() != 0:
                raise RuntimeError("runtime-command-failed")
            return output
        finally:
            timer.cancel()


def audit(args):
    report = {"mode": "selected-runtime-web-roots", "services": [], "findings": [], "warnings": []}
    secrets = {}
    # Resolve, then force an explicit context so DOCKER_HOST cannot override the
    # transport we checked. Restrict this helper to local sockets or SSH.
    try:
        context = args.context or capture(["docker", "context", "show"], 4096).decode().strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", context):
            raise RuntimeError()
        metadata = json.loads(capture(["docker", "context", "inspect", context], 1024 * 1024))
        endpoint = metadata[0]["Endpoints"]["docker"]
        if endpoint.get("SkipTLSVerify") or not endpoint["Host"].startswith(("unix://", "npipe://", "ssh://")):
            report["warnings"].append({"kind": "transport-not-approved-local-or-ssh"})
            return report, secrets
        docker = ["docker", "--context", context]
        report["context"] = context
        for source in dict.fromkeys(args.container + args.compare_env_from):
            config = json.loads(capture(docker + ["inspect", source], 8 * 1024 * 1024))[0]
            for entry in config.get("Config", {}).get("Env", []) or []:
                name, separator, value = entry.partition("=")
                if separator and value and SENSITIVE.search(name):
                    secrets[f"{source}:{name}"] = value
                    if len(value.encode()) < 8:
                        report["warnings"].append({"kind": "short-value-not-reliably-scannable", "envName": name, "service": source})
    except Exception:
        report["warnings"].append({"kind": "runtime-context-or-env-inspection-failed"})
        return report, secrets

    for service in dict.fromkeys(args.container):
        record = {"service": service, "webRoot": args.web_root, "files": 0, "bytes": 0}
        report["services"].append(record)
        try:
            archive = capture(docker + ["cp", f"{service}:{args.web_root}/.", "-"], args.max_archive_mib * 1024 * 1024)
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
                for index, member in enumerate(tar):
                    if index > 100000:
                        report["warnings"].append({"kind": "archive-member-budget-exceeded", "service": service})
                        break
                    name = member.name
                    while name.startswith("./"):
                        name = name[2:]
                    if name in ("", "."):
                        continue
                    location = {"service": service, "path": name}
                    if name.startswith("/") or ".." in name.replace("\\", "/").split("/"):
                        report["warnings"].append({"kind": "unsafe-archive-path", **location})
                        continue
                    if private_path(name):
                        report["findings"].append({"kind": "private-artifact", **location})
                    if member.isdir():
                        continue
                    if not member.isfile():
                        report["warnings"].append({"kind": "link-or-nonregular-member-not-followed", **location})
                        continue
                    if member.size > 64 * 1024 * 1024:
                        report["warnings"].append({"kind": "oversized-file-not-scanned", **location})
                        continue
                    stream = tar.extractfile(member)  # Reads bytes only; no extraction to disk.
                    if stream is None:
                        raise RuntimeError()
                    data = stream.read(64 * 1024 * 1024 + 1)
                    if len(data) > 64 * 1024 * 1024:
                        raise RuntimeError()
                    record["files"] += 1
                    record["bytes"] += len(data)
                    for label, value in secrets.items():
                        if len(value.encode()) >= 8 and any(form.encode() in data for form in variants(value)):
                            report["findings"].append({"kind": "known-environment-value", "envName": label, **location})
                    text = data.decode("latin1")
                    for kind, pattern in PATTERNS:
                        if re.search(pattern, text):
                            report["findings"].append({"kind": kind, **location})
                    if re.search(r"\.(?:js|css)$", name) and re.search(r"(?:^|\n)\s*//[#@]\s*sourceMappingURL=|/\*[#@]\s*sourceMappingURL=", text):
                        report["findings"].append({"kind": "source-map-reference", **location})
                    if re.search(r"\.(?:zip|tar|tgz|gz|br|7z|rar|xz|zst)$", name, re.I):
                        report["warnings"].append({"kind": "compressed-content-not-inspected", **location})
        except Exception:
            report["warnings"].append({"kind": "runtime-web-root-not-fully-scanned", "service": service})
    report["comparedValues"] = sum(len(value.encode()) >= 8 for value in secrets.values())
    return report, secrets


def main():
    class SafeParser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError("invalid arguments")
    parser = SafeParser(description=__doc__)
    parser.add_argument("--container", action="append", required=True)
    parser.add_argument("--compare-env-from", action="append", default=[])
    parser.add_argument("--context")
    parser.add_argument("--web-root", default="/usr/share/nginx/html")
    parser.add_argument("--max-archive-mib", type=int, default=256)
    # Do not let argparse echo unknown credential-bearing input on errors.
    try:
        args, unknown = parser.parse_known_args()
        names = args.container + args.compare_env_from
        if unknown or len(names) > 20 or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name) for name in names):
            raise ValueError()
        if not args.web_root.startswith("/") or args.web_root == "/" or ".." in args.web_root.split("/") or not args.web_root.isprintable() or not 1 <= args.max_archive_mib <= 1024:
            raise ValueError()
    except ValueError:
        print(json.dumps({"error": "Invalid scope or arguments; use container names, not credential values."}))
        return 2
    report, secrets = audit(args)
    print(json.dumps(redact(report, secrets), indent=2))
    return 1 if report["findings"] else 2 if report["warnings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
