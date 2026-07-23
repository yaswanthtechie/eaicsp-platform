import csv
from datetime import datetime
from rapidfuzz import fuzz


sanction_names = set()


def load_csv():

    sanction_names.clear()

    files = [
        "data/ofac.csv",
        "data/un.csv"     
    ]

    for csv_file in files:

        try:

            with open(csv_file, encoding="utf-8") as file:

                reader = csv.reader(file)

                for row in reader:

                    if len(row) > 1:

                        sanction_names.add(row[1].strip())

        except FileNotFoundError:
            print(f"{csv_file} not found. Skipping...")

    print(f"Loaded {len(sanction_names)} sanction names")


def write_audit(input_name, matched_name, score, flagged):

    with open("app/audit.log", "a", encoding="utf-8") as log:

        log.write(
            f"{datetime.now()} | "
            f"Input: {input_name} | "
            f"Matched: {matched_name} | "
            f"Score: {score} | "
            f"Flagged: {flagged}\n"
        )


def check_name(name):

    best_score = 0
    matched_name = ""

    for sanction_name in sanction_names:

        
        if name.lower().strip() == sanction_name.lower().strip():

            matched_name = sanction_name
            best_score = 100
            break

        
        score = fuzz.ratio(
            name.lower(),
            sanction_name.lower()
        )

        if score > best_score:

            best_score = score
            matched_name = sanction_name

    flagged = best_score >= 85

    write_audit(
        name,
        matched_name,
        int(best_score),
        flagged
    )

    return {
        "is_flagged": flagged,
        "matched_lists": ["OFAC SDN"] if flagged else [],
        "match_score": int(best_score)
    }