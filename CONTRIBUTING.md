# Contributing to Xultron

## Commit convention

Keep each commit atomic and use a Conventional Commit-style prefix:

```text
feat(scope): add a user-visible capability
fix(scope): correct a defect
test(scope): add or repair verification
docs(scope): improve documentation
build(scope): change packaging or build configuration
chore(scope): maintain tooling without product behavior changes
```

Examples:

```text
feat(chat): add attachment analysis
fix(android): scope WebView media picker
test(api): cover expired session behavior
```

Before pushing, run the smallest relevant checks, then run the full validation path when practical. Do not force-push shared branches. Keep secrets, keystores, APKs, and generated local data out of source control.
