"""Fail closed on advisories except exact, reviewed package/version/GHSA entries.

The rationale and applicability conditions are maintained in docs/SECURITY.md.
"""
import argparse
import json
import subprocess
from pathlib import Path

EXCEPTIONS = {
    ("braces", "3.0.3"): {"GHSA-vfj7-8cjw-p6xm"},
    ("postcss-selector-parser", "6.1.5"): {"GHSA-rj75-hqrm-r3gf"},
    ("starlette", "0.52.1"): {
        "GHSA-86qp-5c8j-p5mr", "GHSA-wqp7-x3pw-xc5r", "GHSA-x746-7m8f-x49c",
        "GHSA-82w8-qh3p-5jfq", "GHSA-jp82-jpqv-5vv3",
    },
}


def review_python(report):
    accepted, violations = set(), set()
    for package in report["dependencies"]:
        for advisory in package["vulns"]:
            aliases = set(advisory.get("aliases", [])) | {advisory["id"]}
            entry = (package["name"], package["version"])
            label = f"{entry[0]}@{entry[1]}:{advisory['id']}"
            (accepted if aliases & EXCEPTIONS.get(entry, set()) else violations).add(label)
    return accepted, violations


def review_npm(report, lock):
    accepted, violations = set(), set()
    for name, vulnerability in report["vulnerabilities"].items():
        for advisory in vulnerability["via"]:
            if isinstance(advisory, str):
                continue  # Transitive propagation: the root advisory is checked below.
            identifier = advisory["url"].rsplit("/", 1)[-1]
            nodes = vulnerability["nodes"]
            if not nodes:
                violations.add(f"{name}:{identifier}:missing package version")
            for node in nodes:
                version = lock["packages"][node]["version"]
                label = f"{name}@{version}:{identifier}"
                (accepted if identifier in EXCEPTIONS.get((name, version), set()) else violations).add(label)
    return accepted, violations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ecosystem", choices=["python", "npm"])
    parser.add_argument("--directory", default=".")
    args = parser.parse_args()
    command = ["pip-audit", "--format=json", "--progress-spinner=off"] if args.ecosystem == "python" else ["npm", "audit", "--json"]
    result = subprocess.run(command, cwd=args.directory, capture_output=True, text=True, check=False)
    if result.returncode not in (0, 1):
        raise SystemExit(f"Audit failed to execute: {result.stderr}")
    report = json.loads(result.stdout)
    if args.ecosystem == "python":
        accepted, violations = review_python(report)
    else:
        if "error" in report:
            raise SystemExit(f"Audit service failed: {report['error']}")
        lock = json.loads((Path(args.directory) / "package-lock.json").read_text())
        accepted, violations = review_npm(report, lock)
    print(json.dumps({"reviewed_exceptions": sorted(accepted), "unreviewed_advisories": sorted(violations)}, indent=2))
    raise SystemExit(bool(violations))


if __name__ == "__main__":
    main()
