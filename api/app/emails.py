"""Email format check. Deliberately simple and predictable: it checks the shape of the address, nothing more.
The app sends no email, so there is no confirmation step, and ASCII addresses only for now."""
from __future__ import annotations

import re

_LOCAL = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$")
_LABEL = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def normalize_email(value) -> str:
    return (value or "").strip().lower()


def validate_email(value) -> str:
    """The normalized address, or ValueError with a message that is safe to show."""
    email = normalize_email(value)
    problem = ValueError("Enter a valid email address.")
    if len(email) > 254 or email.count("@") != 1:
        raise problem
    local, domain = email.split("@")
    if not local or len(local) > 64 or not _LOCAL.match(local):
        raise problem
    labels = domain.split(".")
    if len(labels) < 2 or not all(_LABEL.match(l) for l in labels) or len(labels[-1]) < 2 or labels[-1].isdigit():
        raise problem
    return email
