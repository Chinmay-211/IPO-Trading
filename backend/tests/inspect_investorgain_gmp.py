from bs4 import BeautifulSoup


def main():
    with open(
        "data/raw/tempsens_investorgain_gmp.html",
        "r",
        encoding="utf-8",
    ) as file:
        html = file.read()

    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text("\n", strip=True)

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    for i, line in enumerate(lines):
        if "GMP" in line.upper():
            print(f"\n--- Match {i} ---")

            start = max(0, i - 5)
            end = min(len(lines), i + 15)

            for item in lines[start:end]:
                print(item)


if __name__ == "__main__":
    main()