from security_audit import review_npm, review_python


def test_python_audit_rejects_new_advisories_and_changed_versions():
    report = {"dependencies": [{"name": "starlette", "version": "0.52.1", "vulns": [
        {"id": "known", "aliases": ["GHSA-86qp-5c8j-p5mr"]},
        {"id": "new-advisory", "aliases": []},
    ]}]}
    accepted, violations = review_python(report)
    assert len(accepted) == 1 and len(violations) == 1
    report["dependencies"][0]["version"] = "0.52.2"
    assert len(review_python(report)[1]) == 2


def test_npm_audit_rejects_new_advisories():
    report = {"vulnerabilities": {"braces": {"nodes": ["node_modules/braces"], "via": [
        {"url": "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm"},
        {"url": "https://github.com/advisories/new-advisory"},
    ]}}}
    lock = {"packages": {"node_modules/braces": {"version": "3.0.3"}}}
    accepted, violations = review_npm(report, lock)
    assert len(accepted) == 1 and len(violations) == 1
