from security_audit import review_npm, review_python


def test_python_audit_rejects_known_and_unrecognized_advisories():
    report = {"dependencies": [{"name": "starlette", "version": "0.52.1", "vulns": [
        {"id": "previously-excepted", "aliases": ["GHSA-86qp-5c8j-p5mr"]},
        {"id": "new-advisory", "aliases": []},
    ]}]}
    accepted, violations = review_python(report)
    assert not accepted
    assert violations == {"starlette@0.52.1:previously-excepted", "starlette@0.52.1:new-advisory"}


def test_npm_audit_rejects_new_advisories():
    report = {"vulnerabilities": {"braces": {"nodes": ["node_modules/braces"], "via": [
        {"url": "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm"},
        {"url": "https://github.com/advisories/new-advisory"},
    ]}}}
    lock = {"packages": {"node_modules/braces": {"version": "3.0.3"}}}
    accepted, violations = review_npm(report, lock)
    assert len(accepted) == 1 and len(violations) == 1
