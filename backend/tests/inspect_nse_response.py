from pathlib import Path

from backend.collectors.ipo.nse_source import NSEIPODataSource


def main():
    source = NSEIPODataSource()

    response = source.session.get(
        source.URL,
        timeout=30,
    )

    response.raise_for_status()

    output_file = (
        Path("data/raw") / "nse_ipo_tracker_response.html"
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)

    output_file.write_text(
        response.text,
        encoding="utf-8",
    )

    print("Saved NSE response to:")
    print(output_file.resolve())
    print("Response size:", len(response.text))


if __name__ == "__main__":
    main()