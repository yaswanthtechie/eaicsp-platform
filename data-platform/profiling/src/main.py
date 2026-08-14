from src.make_sample_data import make_sample_data
from src.profile import generate_html
from src.report import generate_report


def main():
    print("=" * 60)
    print("STARTING DATA PROFILING PROJECT")
    print("=" * 60)

    make_sample_data()
    generate_html()
    generate_report()

    print("=" * 60)
    print("PROJECT COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
    