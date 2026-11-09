# Contributing

Start with a reproducible problem: OS installation, a document extraction error,
a missing exception in retrieved evidence, or an agent integration issue.
Never attach private documents, credentials or personal transcripts. Create a
small synthetic reproduction or use material you have permission to redistribute.

```sh
python -m pip install '.[mcp,tokens]'
python -m unittest discover -s tests -v
python -m pip check
git diff --check
```

Keep changes focused. Add a regression test for a substantive behavior change.
Use temporary cache and configuration directories in tests. Preserve user edits,
original files and existing host configuration. Do not add paid-service calls,
automatic model fallback or remote telemetry as incidental changes.

Report what was actually tested. A configured CI job is not a passing CI result;
a successful tool call is not necessarily an accurate final model answer.
