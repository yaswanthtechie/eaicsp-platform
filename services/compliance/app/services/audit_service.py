import json

from pathlib import Path

from datetime import (
    datetime,
    timezone
)

def write_audit(
    file_path,
    record
):

    try:

        path = Path(file_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        record["timestamp"] = datetime.now(
            timezone.utc
        ).isoformat()
 


        with path.open(
            "a",
            encoding="utf-8"
        ) as file:


            json.dump(
                record,
                file,
                ensure_ascii=False
            )


            file.write("\n")

    except Exception as error:

        print(
            f"Audit failed: {error}"
        )