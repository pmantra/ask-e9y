"""Common SQL patterns for our application."""

SQL_PATTERNS = {
    # Patterns related to checking if a member is active
    "active_member": "m.effective_range @> CURRENT_DATE",

    # Patterns related to finding members by organization
    "member_by_org_id": "m.organization_id = :org_id",
    "member_by_org_name": "m.organization_id = (SELECT id FROM eligibility.organization WHERE name ILIKE :org_name)",

    # Patterns related to verification status
    "verified_member": """EXISTS (
        SELECT 1 FROM eligibility.member_verification mv 
        JOIN eligibility.verification v ON mv.verification_id = v.id 
        WHERE mv.member_id = m.id AND v.verified_at IS NOT NULL
    )""",

    # Patterns for date operations
    "born_after": "m.date_of_birth > :date",
    "born_before": "m.date_of_birth < :date",
    "born_between": "m.date_of_birth BETWEEN :start_date AND :end_date",
}


def get_pattern(key, **kwargs):
    """
    Get a SQL pattern with variables replaced.

    Args:
        key: The pattern key
        kwargs: Variables to replace in the pattern

    Returns:
        The pattern with variables replaced
    """
    pattern = SQL_PATTERNS.get(key)
    if not pattern:
        return None

    # Replace variables
    for k, v in kwargs.items():
        pattern = pattern.replace(f":{k}", f"'{v}'")

    return pattern