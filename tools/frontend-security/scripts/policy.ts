export type Finding = { kind: string; path?: string; envName?: string };
export const sensitiveName = /secret|password|token|credential|private[_-]?key|api[_-]?key|access[_-]?key|database_url|connection_string|dsn/i;
export const patterns: [string, string][] = [
  ['private-key', '-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'],
  ['github-token', '\\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'],
  ['api-token', '\\bsk-[A-Za-z0-9_-]{20,}'],
  ['gitlab-token', '\\bglpat-[A-Za-z0-9_-]{20,}'],
  ['aws-access-key', '\\b(?:AKIA|ASIA)[A-Z0-9]{16}\\b'],
];
export function privatePath(path: string): boolean {
  const parts = path.replaceAll('\\', '/').replace(/^\.\//, '').split('/');
  return parts.some(part => part.startsWith('.') && part !== '.well-known') ||
    ['node_modules', 'src', 'scripts', 'deployment'].includes(parts[0]) ||
    /(?:\.env(?:\.[^/]*)?|\.(?:pem|key|p12|pfx|map|log|sql|sqlite3?|db|bak)(?:-wal|-shm)?)$/i.test(path) ||
    /(?:^|\/)(?:id_rsa|id_ed25519|credentials|Dockerfile|docker-compose\.ya?ml)$/i.test(path);
}
export function variants(value: string): string[] {
  const values = new Set([value, JSON.stringify(value).slice(1, -1), Buffer.from(value).toString('base64'), Buffer.from(value).toString('base64url')]);
  try { values.add(encodeURIComponent(value)); } catch { /* Not every malformed input can be URL-encoded. */ }
  return Array.from(values).filter(Boolean).sort((a, b) => b.length - a.length);
}
export function comparisons(env: Record<string, string | undefined>, extra: string[] = [], allowed: string[] = []) {
  const values: [string, string][] = [], warnings: Finding[] = [];
  const selected = new Set([...Object.keys(env).filter(key => sensitiveName.test(key)), ...extra]);
  for (const key of selected) {
    if (allowed.includes(key)) continue;
    const value = env[key];
    if (!value) { if (extra.includes(key)) warnings.push({kind: 'comparison-value-unavailable', envName: key}); continue; }
    values.push([key, value]);
    if (Buffer.byteLength(value) < 8) warnings.push({kind: 'short-value-not-reliably-scannable', envName: key});
  }
  return {values, warnings};
}
export function inspect(bytes: Uint8Array, path: string, values: [string, string][]): Finding[] {
  const buffer = Buffer.from(bytes), findings: Finding[] = [];
  if (privatePath(path)) findings.push({kind: 'private-artifact', path});
  for (const [envName, value] of values) {
    if (Buffer.byteLength(value) >= 8 && variants(value).some(candidate => buffer.includes(Buffer.from(candidate)))) findings.push({kind: 'known-environment-value', path, envName});
  }
  const text = buffer.toString('latin1');
  for (const [kind, pattern] of patterns) if (new RegExp(pattern).test(text)) findings.push({kind, path});
  if (/\.(?:js|css)$/.test(path) && /(?:^|\n)\s*\/\/[#@]\s*sourceMappingURL=|\/\*[#@]\s*sourceMappingURL=/.test(text)) findings.push({kind: 'source-map-reference', path});
  return findings;
}
export function redact(value: unknown, values: [string, string][]): unknown {
  if (typeof value === 'string') {
    let text = value;
    for (const [, secret] of values) for (const form of variants(secret)) text = text.split(form).join('[REDACTED]');
    for (const [, pattern] of patterns) text = text.replace(new RegExp(pattern, 'g'), '[REDACTED]');
    return text.replace(/[\u0000-\u001f\u007f]/g, '[CONTROL]');
  }
  if (Array.isArray(value)) return value.map(item => redact(item, values));
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, redact(item, values)]));
  return value;
}
export function exitCode(findings: Finding[], warnings: Finding[]): number { return findings.length ? 1 : warnings.length ? 2 : 0; }
