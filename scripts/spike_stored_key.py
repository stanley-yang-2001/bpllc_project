"""
Where does Langflow keep a key it was sent as a tweak? (helper of scripts/spike_model_tweaks.py)

Langflow writes down what it did: chat messages, one "transaction" per component, one "vertex build" per component. If the
learner's API key ends up in those tables, then sending it through Langflow means the key is stored at rest in a database the
site does not encrypt, and phase 2 of docs/CUSTOM-MODEL-DESIGN.md must not do that.

What Langflow 1.12.2 does (read from its source, not yet confirmed on your machine): the transaction log masks values of keys
named like a secret to "first four characters ... last four characters". Whether the other tables hold the whole key is exactly
what the scan below finds out.

This module only LOOKS: it counts rows whose text contains a throwaway key the spike invented (never your real key), it
changes nothing, and the database and the messages API are injected so that it can be tested with fakes.
"""

from typing import Callable, NamedTuple

from spike_tweaks import FAIL, INCONCLUSIVE, PASS  # the same words as the other checks

FULL, MASKED = "full", "masked"

# Mirrors langflow/services/database/models/transactions/model.py (1.12.2): values of secret-looking keys longer than this are
# kept as "abcd...wxyz", shorter ones as "***REDACTED***".
MIN_LENGTH_FOR_PARTIAL_MASK = 12

# Every text-like column of every user table (JSON columns are searched as text).
TEXT_COLUMNS_SQL = (
    "SELECT table_schema, table_name, column_name FROM information_schema.columns "
    "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
    "AND data_type IN ('text', 'character varying', 'json', 'jsonb') "
    "ORDER BY table_schema, table_name, ordinal_position"
)


class Finding(NamedTuple):
    where: str      # "database vertex_build.params", "messages API session u-solo-..."
    kind: str       # FULL = the whole key; MASKED = only Langflow's "abcd...wxyz" form


def langflow_mask(key: str) -> str:
    """The form in which Langflow's transaction log keeps a secret value (a key too short to be partly shown is replaced whole)."""
    if len(key) <= MIN_LENGTH_FOR_PARTIAL_MASK:
        return "***REDACTED***"
    return f"{key[:4]}...{key[-4:]}"


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def like_pattern(needle: str) -> str:
    escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def scan_database(cursor, keys) -> list:
    """Count, column by column, the rows that contain a whole key or only its masked form. `cursor` is a DB-API cursor
    (psycopg2). Two queries per column, however many keys there are."""
    full = [like_pattern(k) for k in keys]
    masked = [like_pattern(langflow_mask(k)) for k in keys if len(k) > MIN_LENGTH_FOR_PARTIAL_MASK]
    cursor.execute(TEXT_COLUMNS_SQL)
    columns = list(cursor.fetchall())
    findings = []
    for schema, table, column in columns:
        target = f"{quote_identifier(schema)}.{quote_identifier(table)}"
        for kind, patterns in ((FULL, full), (MASKED, masked)):
            if not patterns:
                continue
            cursor.execute(f"SELECT count(*) FROM {target} WHERE {quote_identifier(column)}::text LIKE ANY(%s)", (patterns,))
            if cursor.fetchone()[0]:
                findings.append(Finding(f"database {table}.{column}", kind))
    return findings


def database_inspector(connect: Callable) -> Callable:
    """`connect()` -> a DB-API connection. Returns an inspector `(keys, session_ids) -> [Finding]`."""
    def inspect(keys, session_ids):
        connection = connect()
        try:
            cursor = connection.cursor()
            try:
                return scan_database(cursor, keys)
            finally:
                cursor.close()
        finally:
            connection.close()
    return inspect


def messages_inspector(fetch: Callable) -> Callable:
    """`fetch(session_id)` -> the stored messages of that session as parsed JSON. Returns an inspector."""
    def inspect(keys, session_ids):
        findings = []
        for session_id in session_ids:
            text = repr(fetch(session_id))
            for key in keys:
                if key in text:
                    findings.append(Finding(f"messages API, session {session_id[:12]}", FULL))
                elif len(key) > MIN_LENGTH_FOR_PARTIAL_MASK and langflow_mask(key) in text:
                    findings.append(Finding(f"messages API, session {session_id[:12]}", MASKED))
        return findings
    return inspect


def run_inspectors(inspectors: dict, keys, session_ids) -> tuple:
    """Run every inspector; one that fails is reported, not fatal. Returns (findings by name, errors by name)."""
    findings, errors = {}, {}
    for name, inspect in inspectors.items():
        try:
            findings[name] = inspect(keys, session_ids)
        except Exception as e:  # noqa: BLE001
            errors[name] = f"{type(e).__name__}: {e}"
    return findings, errors


def _places(findings, kind) -> str:
    places = sorted({f.where for fs in findings.values() for f in fs if f.kind == kind})
    return ", ".join(places)


def check_stored_key(findings: dict, errors: dict, searched: tuple = ("database", "messages")) -> tuple:
    """(status, detail). `searched` names the inspectors that SHOULD have run; one that did not makes the answer INCONCLUSIVE,
    unless something was already found."""
    whole = _places(findings, FULL)
    if whole:
        return FAIL, f"the WHOLE key is stored by Langflow: {whole}"
    missing = [n for n in searched if n not in findings]
    if missing:
        reasons = "; ".join(f"{n}: {errors.get(n, 'not configured')}" for n in missing)
        return INCONCLUSIVE, f"could not look everywhere ({reasons}); nothing was found where it did look"
    partial = _places(findings, MASKED)
    if partial:
        return PASS, (f"only the masked form (first four and last four characters) is stored: {partial}. "
                      "For a real key that is eight of its characters at rest in Langflow's database")
    return PASS, "the key was found nowhere in Langflow's database or message store"
