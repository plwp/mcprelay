# Contributing to MCPRelay

Thank you for your interest in contributing to MCPRelay! We welcome contributions from the community.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/mcprelay.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Test your changes
6. Commit and push: `git commit -m "Add your feature" && git push origin feature/your-feature-name`
7. Create a pull request

## Development Setup

```bash
# Clone the repository
git clone https://github.com/plwp/mcprelay.git
cd mcprelay

# Install in development mode
pip install -e ".[dev]"

# Copy example config
cp config.example.yaml config.yaml

# Run tests
pytest

# Start development server
mcprelay serve
```

## Code Standards

- Follow PEP 8 for Python code style
- Use type hints where appropriate
- Write tests for new features
- Update documentation for API changes
- Keep commits focused and atomic

## Testing

Run the test suite before submitting changes:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mcprelay

# Run specific test file
pytest tests/test_auth.py
```

## Pull Request Guidelines

- Ensure all tests pass
- Include tests for new functionality
- Update documentation as needed
- Use clear, descriptive commit messages
- Keep pull requests focused on a single feature or fix

## Reporting Issues

When reporting issues, please include:

- MCPRelay version
- Python version
- Operating system
- Steps to reproduce the issue
- Expected vs actual behavior
- Relevant logs or error messages

## Code of Conduct

This project follows a standard code of conduct. Be respectful and inclusive in all interactions.

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.