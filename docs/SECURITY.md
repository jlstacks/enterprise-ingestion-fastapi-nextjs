# Dependency audit decisions

Reviewed October 21, 2026. These are applicability decisions for this local reference
application, not claims that affected packages are universally safe.

CI runs `npm audit --omit=dev` with no exceptions for browser/server production
dependencies, then audits the full npm graph using `backend/security_audit.py`.
The backend test image audits its entire installed Python graph, including test
tools. Exact package/version/GHSA exceptions below are the only allowed findings.
An unknown advisory, changed affected version, malformed audit response, or audit
service failure fails the check. Regression tests verify that new advisories fail.

## Compatible fixes applied

- pytest 8.4.2 -> 9.0.3 addresses GHSA-6w46-j5rx-g56g (local temporary-directory
  handling); all existing and remediation tests run under the updated version.
- The Python image explicitly installs pip 26.2 before installing dependencies.
  This addresses the package-extraction and installer advisories identified in
  the original image's pip 25.0.1.
- Node 22 is used consistently in frontend Docker builds and CI, including the
  native Node test runner for TypeScript health/error logic.

## Reviewed npm build-tool exceptions

| Package/version | Advisory | Decision and boundary |
|---|---|---|
| braces 3.0.3 | [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) | No patched braces release was available when reviewed. Used by Tailwind 3 and ESLint globbing. The application passes no submitted payloads or user-provided patterns to globbing. Build patterns are trusted repository configuration. |
| postcss-selector-parser 6.1.5 | [GHSA-rj75-hqrm-r3gf](https://github.com/advisories/GHSA-rj75-hqrm-r3gf) | Patched upstream version is 7.1.6+, outside postcss-nested 6/Tailwind 3's compatible dependency range. CSS selectors are trusted repository source; the application does not compile submitted CSS. |

The raw audit reports nine affected dependency entries (seven high, two moderate)
propagated from these two root advisories. They are not nine independent exploits.
There are zero reported production npm advisories at this review. Do not use
`npm audit fix --force` or force incompatible transitive major versions. Review
these exceptions when compatible patched upstream releases become available,
before accepting untrusted CSS/glob input, or before broader public deployment.
Build-tool exceptions do not make arbitrary third-party PR code safe to execute.

## Starlette upgrade

FastAPI 0.165.0 and Starlette 1.10.0 supersede the earlier FastAPI 0.128.8
and Starlette 0.52.1 pair. The audit now rejects the five formerly excepted
Starlette advisories. The newest minimum fixed version among the five is
[Starlette 1.3.1](https://github.com/advisories/GHSA-82w8-qh3p-5jfq).

## Running the audits

```bash
# Run from the repository root after frontend dependencies are installed.
python3 backend/security_audit.py npm --directory frontend
docker build --target test -t enterprise-ingestion-backend-test backend
docker run --rm enterprise-ingestion-backend-test python security_audit.py python
```

The script prints every reviewed exception and rejects any unreviewed advisory.
