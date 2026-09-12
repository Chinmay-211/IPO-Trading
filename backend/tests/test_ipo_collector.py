from backend.collectors.ipo.collector import IPOCollector
from backend.collectors.ipo.nse_source import NSEIPODataSource


def main():
    source = NSEIPODataSource()
    collector = IPOCollector(source)

    result = collector.run()

    print(result)


if __name__ == "__main__":
    main()