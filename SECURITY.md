# Security Policy

## Reporting a Vulnerability

We take the security of RANTAS seriously. If you believe you've found a security vulnerability, please report it to us privately.

### How to Report

**Email:** [halo@deprito.net](mailto:halo@deprito.net)

**Subject Line:** `Security Vulnerability Report - RANTAS`

### What to Include

To help us triage and respond quickly, please include:

1. **Description** - Clear description of the vulnerability
2. **Affected Version** - Version or commit hash where you found the issue
3. **Reproduction Steps** - Detailed steps to reproduce the vulnerability
4. **Impact** - Potential impact if exploited
5. **Proof of Concept** - Code, screenshots, or logs demonstrating the issue (if possible)
6. **Suggested Fix** - Optional: your recommendations for remediation

### Response Timeline

- **Acknowledgment:** Within 48 hours of receipt
- **Initial Assessment:** Within 5 business days
- **Status Update:** Within 10 business days
- **Resolution:** Depends on severity and complexity

### What to Expect

1. **Confirmation** - We'll acknowledge your report and assign a severity rating
2. **Communication** - We'll keep you informed of our progress
3. **Credit** - We'll credit you in our security acknowledgments (unless you prefer to remain anonymous)
4. **Disclosure** - We'll coordinate public disclosure with you after the fix is released

### Severity Ratings

| Severity | Response Time | Description |
|----------|---------------|-------------|
| **Critical** | 24-48 hours | Remote code execution, authentication bypass, data breach |
| **High** | 5 business days | Privilege escalation, XSS, CSRF with significant impact |
| **Medium** | 10 business days | Information disclosure, limited impact vulnerabilities |
| **Low** | 30 business days | Minor issues, best practice violations |

### Safe Harbor

When reporting vulnerabilities in good faith, we will not pursue legal action against you. We appreciate responsible disclosure that helps keep RANTAS and its users secure.

### Out of Scope

The following are generally not considered security vulnerabilities:

- Missing security headers (CSP, HSTS, etc.) - unless combined with other issues
- Clickjacking on pages without sensitive actions
- Logout CSRF
- Missing rate limiting on non-authentication endpoints
- Vulnerabilities requiring physical access to a user's device
- Issues affecting only outdated browsers or platforms

---

*This security policy is subject to change. Last updated: 2026-04-02*
