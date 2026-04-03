#!/usr/bin/env python3
"""
Clean, organized regex patterns for typosquat detection.
Generated from known phishing domains analysis.

KEY PRINCIPLE: Only match domains with OBVIOUS distortions.
Legitimate domains like "example.com" should NOT match.
"""
import re


# ============================================
# SUSPICIOUS TLDs (free/suspicious hosting)
# ============================================

SUSPICIOUS_TLDS = r'(cc|xyz|top|club|icu|tk|ml|click|cloud|online|site|sbs|xin|tharshen)'


# ============================================
# BRAND PATTERNS (Example: example.com)
# ============================================

BRAND_PATTERNS = {
    "example": [
        # Leetspeak core (0=o, 1=i/l, 4=a, 3=e, etc.)
        r"[3e][1x]4mpl[3e]",                   # 3x4mpl3
        r"[3e]x[4a]mpl[3e]",                   # ex4mpl3
        r"[3e]x[4a]mp1[3e]",                   # ex4mp13
        r"[3e]xx[4a]mpl[3e]",                  # exxample (double x)
        r"[3e]x[4a]mm[4a]pl[3e]",              # exmample (double m)
        r"[3e]x[4a]mpl[3e][3e]",               # examplee (double e)
        r"[3e]x[4a]mp1e",                      # ex4mp1e
        r"[3e]x[a@4]mpl[3e]",                  # ex@mple, ex4mple

        # Suspicious TLD combinations
        r"[3e]x[4a]mpl[3e].*\.(" + SUSPICIOUS_TLDS + r")",
        r"[3e]x[4a]mp1[3e].*\.(" + SUSPICIOUS_TLDS + r")",

        # Missing/extra letters
        r"[3e]x[4a]mpl[.]?",                   # exampl (missing e)
        r"[3e]x[4a]mpel",                      # exampel (transposed)
        r"[3e]xamp1[3e]",                      # examp1e
        r"[3e]x[4a]mple[.]?",                  # examp1 (missing e)

        # Combined with suspicious keywords
        r"[3e]x[4a]mpl[3e].*(login|secure|verify|account|update)",
        r"(login|secure|verify|account|update).*[3e]x[4a]mpl[3e]",
    ],

    "testcorp": [
        # Leetspeak substitutions
        r"[7t][3e][5s][7t]c[0o]rp",            # 7357c0rp
        r"[7t][3e]s[7t]c[0o]rp",               # 73stc0rp
        r"[7t][3e][5s][7t]c[o0]r[p9]",         # 7357c0r9
        r"[7t][3e]s[7t]c[o0][r][p9]",          # 73stc0rp

        # Double letters (obvious typos)
        r"[7t][3e]ss[7t]c[o0]rp",              # tesstcorp
        r"[7t][3e]s[7t][7t]c[o0]rp",           # testtcorp
        r"[7t][3e]s[7t]cc[o0]rp",              # testccorp
        r"[7t][3e]s[7t]c[o0]rrp",              # testcorrp
        r"[7t][3e]s[7t]c[o0]rpp",              # testcorpp

        # Suspicious TLD combinations
        r"[7t][3e]s[7t]c[o0]rp.*\.(" + SUSPICIOUS_TLDS + r")",

        # Combined with suspicious keywords
        r"[7t][3e]s[7t]c[o0]rp.*(login|secure|verify|account)",
        r"(login|secure|verify|account).*[7t][3e]s[7t]c[o0]rp",
    ],
}


# ============================================
# WHITELIST - Legitimate domains to exclude
# ============================================

WHITELIST = [
    # Legitimate example domains
    r'^example\.com$',
    r'^example\.org$',
    r'^example\.net$',

    # Legitimate testcorp domains
    r'^testcorp\.com$',
    r'^testcorp\.org$',
]


# ============================================
# DETECTION FUNCTIONS
# ============================================

def is_whitelisted(domain: str) -> bool:
    """Check if domain is in whitelist."""
    domain_lower = domain.lower()
    for pattern in WHITELIST:
        if re.match(pattern, domain_lower):
            return True
    return False


def get_brand_patterns(brand: str = None) -> dict:
    """Get patterns for a specific brand or all brands."""
    if brand:
        return {brand: BRAND_PATTERNS.get(brand, [])}
    return BRAND_PATTERNS


def check_domain(domain: str) -> list:
    """Check if a domain matches any typosquat patterns.

    Args:
        domain: Domain to check

    Returns:
        List of matched brands
    """
    # Skip if whitelisted
    if is_whitelisted(domain):
        return []

    domain_lower = domain.lower()
    matches = []

    for brand, patterns in BRAND_PATTERNS.items():
        for pattern in patterns:
            try:
                if re.search(pattern, domain_lower):
                    matches.append(brand)
                    break
            except re.error:
                continue

    return matches


def extract_brand_from_domain(domain: str) -> str | None:
    """Extract potential brand name from typosquat domain."""
    matches = check_domain(domain)
    return matches[0] if matches else None


# ============================================
# TEST
# ============================================

if __name__ == "__main__":
    test_cases = [
        # Should match "example" (leetspeak or suspicious TLD)
        ("3x4mpl3.com", "example"),             # leetspeak
        ("ex4mpl3.com", "example"),             # a=4, e=3
        ("ex4mp13.com", "example"),             # full leetspeak
        ("exxample.xyz", "example"),            # double x + suspicious TLD
        ("exmample.cc", "example"),             # double m + suspicious TLD
        ("examplee.click", "example"),          # double e + suspicious TLD
        ("example-login.com", "example"),       # with suspicious keyword
        ("secure-example.net", "example"),      # keyword prefix

        # Should match "testcorp" (obvious typos or combined with suspicious)
        ("7357c0rp.com", "testcorp"),           # full leetspeak
        ("73stc0rp.com", "testcorp"),           # partial leetspeak
        ("tesstcorp.xyz", "testcorp"),          # double s + suspicious TLD
        ("testtcorp.cc", "testcorp"),           # double t + suspicious TLD
        ("testcorrp.click", "testcorp"),        # double r + suspicious TLD
        ("testcorp-verify.com", "testcorp"),    # with suspicious keyword

        # Should be CLEAN (legitimate or no obvious typos)
        ("example.com", None),                  # whitelisted
        ("example.org", None),                  # whitelisted
        ("testcorp.com", None),                 # whitelisted
        ("testcorp.org", None),                 # whitelisted
        ("example.net", None),                  # whitelisted
        ("test.com", None),                     # no brand
        ("corp.com", None),                     # no brand
    ]

    print("=" * 70)
    print("Typosquat Detection Test")
    print("=" * 70)

    passed = 0
    failed = 0

    for domain, expected in test_cases:
        result = extract_brand_from_domain(domain)
        status = "PASS" if result == expected else "FAIL"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        exp_str = expected or "(none)"
        res_str = result or "(none)"
        print(f"[{status}] {domain:40} -> {res_str:15} (expected: {exp_str})")

    print("=" * 70)
    print(f"Results: {passed}/{passed + failed} passed")

    # Also test whitelist
    print("\n" + "=" * 70)
    print("Whitelist Test")
    print("=" * 70)
    for domain in ["example.com", "example.org", "testcorp.com", "testcorp.org"]:
        wl = is_whitelisted(domain)
        print(f"[{'OK' if wl else 'FAIL'}] {domain:30} whitelisted: {wl}")
