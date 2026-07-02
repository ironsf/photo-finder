from config import INPUT_XLSX
from review_ui import main as run_review


def main():
    if INPUT_XLSX is None:
        raise FileNotFoundError("No .xlsx file found next to the script")
    run_review()


if __name__ == "__main__":
    main()
