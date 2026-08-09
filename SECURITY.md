# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue in PrintBridge, please follow these steps:

### 1. Do NOT open a public GitHub issue

Security vulnerabilities should not be disclosed publicly until a fix is available.

### 2. Report privately

Email: **sbia.anouar@gmail.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### 3. Response timeline

- **Acknowledgment**: within 48 hours
- **Initial assessment**: within 5 business days
- **Fix or mitigation**: within 30 days (severity-dependent)
- **Public disclosure**: after fix is released, coordinated with reporter

### 4. Scope

PrintBridge runs locally on `127.0.0.1` and does not expose external endpoints. Security concerns include:

- CORS misconfiguration allowing unauthorized origins
- Input validation bypasses in API endpoints
- Path traversal in file handling
- Privilege escalation via auto-start registration

### 5. Out of scope

- Vulnerabilities in dependencies (report to upstream projects)
- Social engineering attacks
- Physical access to the machine running PrintBridge
- DoS attacks requiring local network access

## Security Best Practices for Users

1. **Keep CORS restricted** — only add your web app's domain to `cors_origins`
2. **Don't expose the port** — PrintBridge binds to `127.0.0.1` only, keep it that way
3. **Review config.json** — ensure no sensitive data in config files
4. **Keep dependencies updated** — run `pip install --upgrade -r requirements.txt` periodically
