from backend.models.instrument import Instrument
from backend.storage.database import get_connection


class InstrumentRepository:
    """Database operations for provider instrument mappings."""

    def add(self, instrument: Instrument) -> bool:
        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO instruments (
                    symbol,
                    company_name,
                    isin,
                    exchange,
                    provider,
                    provider_instrument_id,
                    valid_from,
                    valid_to
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    instrument.symbol,
                    instrument.company_name,
                    instrument.isin,
                    instrument.exchange,
                    instrument.provider,
                    instrument.provider_instrument_id,
                    (
                        instrument.valid_from.isoformat()
                        if instrument.valid_from
                        else None
                    ),
                    (
                        instrument.valid_to.isoformat()
                        if instrument.valid_to
                        else None
                    ),
                ),
            )

            connection.commit()
            return cursor.rowcount > 0

        finally:
            connection.close()

    def get_by_symbol(
        self,
        symbol: str,
        provider: str,
    ) -> list[dict]:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM instruments
                WHERE symbol = ?
                  AND provider = ?
                ORDER BY valid_from
                """,
                (symbol, provider),
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()

    def count(self) -> int:
        connection = get_connection()

        try:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM instruments"
            ).fetchone()

            return row["count"]

        finally:
            connection.close()