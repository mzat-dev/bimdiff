# Contributing to BIM Diff

Thank you for your interest in contributing to BIM Diff!

## Contributor License Agreement (CLA)

**Before any pull request can be merged, you must sign our CLA.**

The CLA grants us the right to distribute your contribution under licenses
other than the AGPL-3.0 (specifically, our commercial license). This is
essential for our dual-licensing model.

When you open a PR, a bot will prompt you to sign the CLA. It's a one-time
process.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/mzat-dev/bimdiff.git
cd bimdiff

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/ tests/
```

## Code Style

- **Formatter**: `ruff format`
- **Linter**: `ruff check`
- **Type hints**: required on all public functions
- **Line length**: 100 characters max

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — new feature
- `fix:` — bug fix
- `refactor:` — code change that doesn't fix a bug or add a feature
- `test:` — adding or updating tests
- `docs:` — documentation changes
- `chore:` — maintenance tasks

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`pytest`)
5. Ensure linting passes (`ruff check src/ tests/`)
6. Open a PR with a clear description
7. Sign the CLA when prompted

## Reporting Issues

Use [GitHub Issues](https://github.com/mzat-dev/bimdiff/issues) to report bugs
or request features. Include:

- Steps to reproduce (for bugs)
- Expected vs actual behavior
- IFC file version (IFC2x3 or IFC4)
- Python version and OS
