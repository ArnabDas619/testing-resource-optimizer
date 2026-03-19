# src/config.py

# Mapping of tester types to keywords for basic heuristic classification
ROLE_KEYWORDS = {
    "Performance": [
        "latency", "concurrent", "load", "scaling", "stress",
        "throughput", "bottleneck", "optimization", "cache", "redis"
    ],
    "Security": [
        "oauth", "injection", "encryption", "auth", "login",
        "vulnerability", "xss", "csrf", "audit", "pii", "token"
    ],
    "Accessibility": [
        "screen reader", "contrast", "aria", "wcag", "keyboard navigation",
        "color bind", "tts", "voice"
    ],
    "Automation": [
        "selenium", "cypress", "e2e", "api test", "regression",
        "pipeline", "ci/cd", "playwright", "test suite"
    ],
    "Manual": [
        "ui", "ux", "exploratory", "visual", "layout",
        "copy", "design", "redesign", "flow"
    ]
}

# Sprint maturity rules
# Keys are Tester Types, values are the minimum sprint number required
# before this role is actively recommended (unless explicitly requested).
SPRINT_MATURITY_THRESHOLDS = {
    "Performance": 3,
    "Security": 3,
    "Accessibility": 4,
    "Automation": 2,
    "Manual": 1
}

# Tester Proficiency Levels
PROFICIENCY_LEVELS = [
    "1 - Beginner",
    "2 - Intermediate",
    "3 - Competent",
    "4 - Advanced",
    "5 - Expert"
]
