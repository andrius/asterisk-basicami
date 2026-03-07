# PyPI Publishing Setup

This repository is configured to automatically publish to PyPI when a GitHub release is created.

## Trusted Publishing (Recommended)

Trusted publishing uses OpenID Connect (OIDC) tokens — more secure since tokens are automatically generated and expire.

### Setup Steps:

1. **Configure PyPI Trusted Publisher:**
   - Go to [PyPI Account Settings](https://pypi.org/manage/account/)
   - Navigate to "Publishing" section
   - Click "Add a new pending publisher"
   - Fill in:
     - **PyPI Project Name:** `basicami`
     - **Owner:** `andrius`
     - **Repository name:** `asterisk-basicami`
     - **Workflow filename:** `ci-cd.yml`
     - **Environment name:** `pypi`

2. **GitHub Repository Setup:**
   - Go to repository Settings → Environments
   - Create environment named `pypi`
   - Enable "Required reviewers" for additional security (optional)

## Publishing Process

1. **Create a Release:**
   - Go to GitHub repository → Releases
   - Click "Create a new release"
   - Create a new tag (e.g., `v0.1.0`)
   - Fill in release title and description
   - Click "Publish release"

2. **Automatic Publishing:**
   - The workflow will automatically run
   - Tests must pass before publishing
   - Package will be built and uploaded to PyPI

## Fallback: API Token

If trusted publishing doesn't work, add a `PYPI_API_TOKEN` secret to the repo and update the workflow:

```yaml
- name: Publish package distributions to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    password: ${{ secrets.PYPI_API_TOKEN }}
```

## Troubleshooting

- **403 Forbidden:** Check PyPI trusted publisher configuration
- **Project not found:** Ensure the pending publisher is configured on pypi.org
- **Version conflict:** Ensure the version in `basicami/__init__.py` is unique
- **Test failures:** Publishing only occurs if all tests pass
