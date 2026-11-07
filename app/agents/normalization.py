_ALIASES = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
}


def normalize_skills(skills: list[str]) -> list[str]:
    """Normalise la casse et les synonymes sans fusionner les autres termes."""
    result: list[str] = []
    seen: set[str] = set()
    for skill in skills:
        cleaned = " ".join(skill.strip().split())
        if not cleaned:
            continue
        canonical = _ALIASES.get(cleaned.casefold(), cleaned)
        key = canonical.casefold()
        if key not in seen:
            seen.add(key)
            result.append(canonical)
    return result
