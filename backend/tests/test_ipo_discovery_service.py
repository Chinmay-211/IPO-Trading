from backend.services.ipo_discovery_service import (
    IPODiscoveryService,
)


def main():
    service = IPODiscoveryService()

    result = service.run()

    print("=" * 60)
    print("IPO DISCOVERY SERVICE")
    print("=" * 60)

    print("Fetched:", result["fetched"])
    print("Inserted:", result["inserted"])
    print("Skipped:", result["skipped"])
    print("Errors:", len(result["errors"]))

    if result["errors"]:
        print()
        print("First errors:")

        for error in result["errors"][:5]:
            print(error)


if __name__ == "__main__":
    main()