# Contributing to ImageForge

Thank you for your interest in contributing! Here's how you can help make ImageForge even better.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork:
   ```bash
   git clone https://github.com/yourusername/imageforge.git
   cd imageforge
   ```
3. **Set up** development environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -e .
   ```

## Development

### Code Style

- Follow **PEP 8** guidelines
- Use **type hints** for all function parameters and return values
- Keep functions focused and small
- Write **docstrings** for public functions

### Running Tests

```bash
pytest tests/ -v
```

### Linting

```bash
ruff check src/
black --check src/
```

### Formatting

```bash
black src/
ruff check --fix src/
```

## Submitting Changes

1. Create a **feature branch**:
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. Make your changes and add tests if applicable

3. Ensure tests pass:
   ```bash
   pytest tests/ -v
   ```

4. Commit with a clear message:
   ```bash
   git commit -m "Add amazing feature"
   ```

5. Push to your fork:
   ```bash
   git push origin feature/amazing-feature
   ```

6. Open a **Pull Request**

## Reporting Issues

When reporting bugs, please include:

- Python version (`python --version`)
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages and stack traces

## Feature Requests

- Open an issue with the **enhancement** label
- Describe the use case
- Explain why it would benefit other users

## Code of Conduct

Be respectful and constructive. We're here to build something useful together.

---

Thank you for contributing! 🎉
