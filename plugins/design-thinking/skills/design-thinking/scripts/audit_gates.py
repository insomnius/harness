#!/usr/bin/env python3
"""Attack the gates. Exits non-zero if any of them can be walked past.

`test_design.py` proves the intended paths work. This proves the unintended
ones do not - the two are different questions, and only this one answers
"is there a critical or important issue in here".

Every case is an attempt to reach a state the method forbids: closing without
evidence, passing a gate by declaring it, writing outside .design/, or having
a command report success while recording nothing. A case that SUCCEEDS is a
finding.

    python3 audit_gates.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI = [sys.executable, str(HERE / "design.py")]


class Repo:
    def __init__(self, root):
        self.root = Path(root)
        (self.root / ".git").mkdir(exist_ok=True)

    def run(self, *args):
        return subprocess.run(CLI + list(args), cwd=self.root,
                              capture_output=True, text=True)

    def ok(self, *args):
        r = self.run(*args)
        if r.returncode != 0:
            raise AssertionError(f"setup failed: {' '.join(args)}\n{r.stdout}{r.stderr}")
        return r

    def fresh(self, ref="A1"):
        for p in (self.root / ".design").glob("*"):
            p.unlink()
        self.ok("init", "--ref", ref)
        return ref


def main():
    findings = []

    def attack(desc, repo, *args, setup=()):
        """The command must be REFUSED. Success is a finding."""
        for s in setup:
            repo.ok(*s)
        r = repo.run(*args)
        if r.returncode == 0:
            findings.append(f"{desc}: ACCEPTED — `{' '.join(args)}`")
            print(f"  ✗ {desc}")
        else:
            print(f"  ✓ {desc}")

    with tempfile.TemporaryDirectory() as tmp:
        repo = Repo(tmp)

        print("behavior gate")
        repo.fresh("B1")
        repo.ok("requirement", "--id", "R1", "--statement", "r")
        repo.ok("acceptance", "--id", "R1", "--cmd", "t", "--red", "boom")
        repo.ok("task", "--id", "T1", "--slug", "a", "--requirement", "R1")
        repo.ok("node", "--slug", "a", "--path", "n.go", "--purpose", "p",
                "--verdict", "change", "--depth", "0")
        repo.ok("behavior", "--slug", "a", "--id", "B1", "--statement", "b",
                "--path", "n.go", "--status", "specified", "--requirement", "R1")
        attack("green without any gate", repo,
               "behavior", "--slug", "a", "--id", "B1", "--statement", "b",
               "--status", "green")
        attack("gated without any gate", repo,
               "behavior", "--slug", "a", "--id", "B1", "--statement", "b",
               "--status", "gated")
        attack("green after a FAILED gate", repo,
               "behavior", "--slug", "a", "--id", "B1", "--statement", "b",
               "--status", "green",
               setup=[("gate", "--slug", "a", "--id", "B1", "--red", "r",
                       "--failed", "G1")])
        attack("green after restating a gated behavior", repo,
               "behavior", "--slug", "a", "--id", "B1", "--statement", "b CHANGED",
               "--status", "green",
               setup=[("gate", "--slug", "a", "--id", "B1", "--red", "r"),
                      ("behavior", "--slug", "a", "--id", "B1", "--statement", "b",
                       "--status", "green")])

        print("requirement gate")
        repo.fresh("R2")
        repo.ok("requirement", "--id", "R1", "--statement", "r")
        attack("task opened before any red", repo,
               "task", "--id", "T1", "--slug", "a", "--requirement", "R1")
        attack("green with no red first", repo, "acceptance", "--id", "R1", "--green")
        attack("green under a changed command", repo,
               "acceptance", "--id", "R1", "--cmd", "t2", "--green",
               setup=[("acceptance", "--id", "R1", "--cmd", "t1", "--red", "x")])

        print("closing without evidence")
        for desc, setup in [
            ("done with no acceptance at all",
             [("requirement", "--id", "R1", "--statement", "r", "--status", "done")]),
            ("red but never green",
             [("acceptance", "--id", "R1", "--cmd", "t", "--red", "x"),
              ("requirement", "--id", "R1", "--statement", "r", "--status", "done")]),
            ("green but zero behaviors",
             [("acceptance", "--id", "R1", "--cmd", "t", "--red", "x"),
              ("acceptance", "--id", "R1", "--green"),
              ("requirement", "--id", "R1", "--statement", "r", "--status", "done")]),
        ]:
            repo.fresh("C1")
            repo.ok("requirement", "--id", "R1", "--statement", "r")
            attack(desc, repo, "close", setup=setup)
        repo.fresh("C2")
        repo.ok("requirement", "--id", "R1", "--statement", "r")
        attack("descoped with no reason", repo,
               "requirement", "--id", "R1", "--statement", "r", "--status", "descoped")

        print("writing outside .design/")
        for bad in ("../evil", "a/b", "x*y", "E.1"):
            repo.fresh("P1")
            attack(f"ref {bad!r}", repo, "init", "--ref", bad)
        repo.fresh("P2")
        repo.ok("requirement", "--id", "R1", "--statement", "r")
        repo.ok("acceptance", "--id", "R1", "--cmd", "t", "--red", "x")
        for bad in ("../evil", "a/b"):
            attack(f"task slug {bad!r}", repo,
                   "task", "--id", "T1", "--slug", bad, "--requirement", "R1")
        stray = [p for p in Path(tmp).rglob("*.json*") if ".design" not in p.parts]
        if stray:
            findings.append(f"files written outside .design/: {stray}")
            print(f"  ✗ nothing written outside .design/ ({stray})")
        else:
            print("  ✓ nothing written outside .design/")

        print("silent no-ops (accepted, records nothing)")
        repo.fresh("S1")
        repo.ok("requirement", "--id", "R1", "--statement", "r")
        repo.ok("acceptance", "--id", "R1", "--cmd", "t", "--red", "x")
        repo.ok("task", "--id", "T1", "--slug", "a", "--requirement", "R1")
        repo.ok("node", "--slug", "a", "--path", "n.go", "--purpose", "p",
                "--verdict", "change", "--depth", "0")
        attack("behavior on an unknown task", repo,
               "behavior", "--slug", "NOPE", "--id", "B1", "--statement", "b")
        attack("edge on an unknown task", repo,
               "edge", "--slug", "NOPE", "--from", "a", "--to", "b")
        attack("behavior claiming an unknown requirement", repo,
               "behavior", "--slug", "a", "--id", "B2", "--statement", "b",
               "--requirement", "R999")
        attack("order on an unknown node", repo,
               "order", "--slug", "a", "--path", "NOPE.go", "--n", "9")
        attack("edge re-recorded with a different kind", repo,
               "edge", "--slug", "a", "--from", "n.go", "--to", "m.go",
               "--kind", "provisions",
               setup=[("edge", "--slug", "a", "--from", "n.go", "--to", "m.go")])

        print("log integrity")
        log = Path(tmp) / ".design" / "S1.log.jsonl"
        good = log.read_text()
        for desc, junk in [("malformed JSON line", "{bad\n"),
                           ("valid JSON that is not an object", '"a string"\n')]:
            log.write_text(good + junk)
            r = repo.run("rebuild")
            if r.returncode == 0:
                findings.append(f"{desc}: folded around it")
                print(f"  ✗ {desc}")
            else:
                print(f"  ✓ {desc}")
            log.write_text(good)

    print()
    if findings:
        print(f"{len(findings)} CRITICAL/IMPORTANT FINDING(S):")
        for f in findings:
            print("  -", f)
        return 1
    print("no critical or important issues: every gate refused every attack")
    return 0


if __name__ == "__main__":
    sys.exit(main())
