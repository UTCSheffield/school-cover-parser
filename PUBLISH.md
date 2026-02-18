# Publish to PyPI

This project uses setuptools and publishes with `build` + `twine`.

## One-time setup

- Create accounts on https://test.pypi.org and https://pypi.org.
- Create API tokens for each site.
- Configure `~/.pypirc` (recommended):

```
[pypi]
  username = __token__
  password = pypi-REPLACE_WITH_REAL_TOKEN

[testpypi]
  repository = https://test.pypi.org/legacy/
  username = __token__
  password = pypi-REPLACE_WITH_REAL_TOKEN
```

Install tooling:

```
python -m pip install --upgrade build twine
```

## Release process (test first)

1) Update the version in [pyproject.toml](pyproject.toml).

2) Build sdist + wheel:

```
python -m build
```

3) Upload to TestPyPI:

```
python -m twine upload --repository testpypi dist/*
```

4) Smoke-test install from TestPyPI:

```
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ school-cover-parser
```

5) Run a quick check:

```
python -m school_cover_parser --test
```

## Publish to PyPI

After the TestPyPI install works:

```
python -m twine upload dist/*
```

## Notes

- If you need to re-release the same version, bump the version first. PyPI does not allow overwriting existing files.
- Clean old builds between attempts:

```
rm -rf dist/ build/ *.egg-info
```
