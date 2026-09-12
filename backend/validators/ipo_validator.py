from datetime import date, datetime

from backend.models.ipo import IPO


def validate_ipo(ipo: IPO) -> list[str]:
    """Return a list of validation errors for an IPO record."""
    errors = []

    if not ipo.company_name or not ipo.company_name.strip():
        errors.append("company_name is required")

    if not ipo.listing_date:
        errors.append("listing_date is required")
    elif ipo.listing_date > date.today():
        errors.append("listing_date cannot be in the future")

    if ipo.issue_price <= 0:
        errors.append("issue_price must be greater than zero")

    if ipo.issue_size is not None and ipo.issue_size < 0:
        errors.append("issue_size cannot be negative")

    if not ipo.source or not ipo.source.strip():
        errors.append("source is required")

    if not isinstance(ipo.collected_at, datetime):
        errors.append("collected_at must be a datetime")

    return errors


def is_valid_ipo(ipo: IPO) -> bool:
    """Return True when the IPO passes all validation rules."""
    return len(validate_ipo(ipo)) == 0