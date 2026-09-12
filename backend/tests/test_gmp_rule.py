from backend.strategy.gmp_rule import GMPRule
from backend.storage.gmp_repository import GMPRepository


def main():
    repository = GMPRepository()

    snapshots = repository.get_by_ipo(2252)

    rule = GMPRule(minimum_percent=10.0)

    result = rule.evaluate(snapshots)

    print("GMP Rule Result:")
    print(result)


if __name__ == "__main__":
    main()