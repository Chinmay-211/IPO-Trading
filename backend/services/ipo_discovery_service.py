from backend.collectors.ipo.chittorgarh_source import (
    ChittorgarhIPODataSource,
)
from backend.models.ipo_discovery import IPODiscovery
from backend.storage.ipo_discovery_repository import (
    IPODiscoveryRepository,
)


class IPODiscoveryService:
    """Discover and persist IPOs from Chittorgarh."""

    def __init__(
        self,
        source=None,
        repository=None,
    ):
        self.source = (
            source or ChittorgarhIPODataSource()
        )

        self.repository = (
            repository or IPODiscoveryRepository()
        )

    def run(self) -> dict:
        records = self.source.fetch()

        inserted = 0
        skipped = 0
        errors = []

        for record in records:
            try:
                discovery = IPODiscovery(
                    chittorgarh_ipo_id=record["ipo_id"],
                    company_name=record["company_name"],
                    ipo_type=record.get("ipo_type"),
                    ipo_open_date=record.get(
                        "ipo_open_date"
                    ),
                    ipo_close_date=record.get(
                        "ipo_close_date"
                    ),
                    listing_date=record.get(
                        "listing_date"
                    ),
                    detail_url=record["detail_url"],
                )

                if self.repository.add(discovery):
                    inserted += 1
                else:
                    skipped += 1

                # Sync discovered IPO into ipos table
                self._sync_to_ipos(record)

            except Exception as exc:
                errors.append({
                    "record": record,
                    "error": str(exc),
                })

        # Purge any already-listed historical IPOs from SQLite
        try:
            from backend.storage.database import get_connection
            conn = get_connection()
            try:
                conn.execute("DELETE FROM ipos WHERE listing_date IS NOT NULL AND listing_date != '' AND listing_date < date('now')")
                conn.execute("DELETE FROM ipo_discoveries WHERE listing_date IS NOT NULL AND listing_date != '' AND listing_date < date('now')")
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass

        return {
            "fetched": len(records),
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
        }

    def _sync_to_ipos(self, record: dict) -> None:
        """Synchronize discovered Indian Mainboard IPO to ipos table."""
        try:
            from datetime import date, datetime
            from backend.storage.database import get_connection

            c_name = record.get("company_name", "").strip()
            if not c_name:
                return

            raw_listing = (record.get("listing_date") or "").strip()
            # Do NOT sync already-listed IPOs
            if raw_listing:
                try:
                    for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
                        try:
                            if datetime.strptime(raw_listing, fmt).date() < date.today():
                                return
                            break
                        except ValueError:
                            pass
                except Exception:
                    pass

            sym = record.get("symbol")
            if sym:
                sym = sym.strip().upper()

            price_raw = record.get("issue_price")
            price = float(price_raw) if price_raw is not None and float(price_raw) > 0 else None
            now_iso = datetime.now().isoformat()

            conn = get_connection()
            try:
                # Check for existing IPO by name or symbol
                existing = conn.execute(
                    """
                    SELECT id, symbol, listing_date, issue_price FROM ipos
                    WHERE lower(company_name) = lower(?)
                       OR (symbol IS NOT NULL AND symbol != '' AND symbol = ?)
                    """,
                    (c_name, sym or ""),
                ).fetchone()

                if existing:
                    # Update symbol, listing date, and issue price from live Chittorgarh
                    conn.execute(
                        """
                        UPDATE ipos
                        SET symbol = COALESCE(NULLIF(symbol, ''), ?),
                            listing_date = COALESCE(NULLIF(listing_date, ''), ?),
                            issue_price = COALESCE(?, issue_price),
                            source = 'Chittorgarh'
                        WHERE id = ?
                        """,
                        (sym, raw_listing, price, existing[0]),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO ipos (company_name, symbol, listing_date, issue_price, source, collected_at)
                        VALUES (?, ?, ?, ?, 'Chittorgarh', ?)
                        """,
                        (c_name, sym, raw_listing, price, now_iso),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass