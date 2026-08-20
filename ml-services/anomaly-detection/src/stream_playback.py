from pathlib import Path
import sys
import time

import pandas as pd
import requests


# ---- Project paths ----

project_root = Path(__file__).resolve().parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.incident_manager import incident_manager

# ---- Configuration ----

API_URL = "http://127.0.0.1:8000/detect-window"

DATASET = project_root / "output" / "test_temperature_spike.csv"

MODEL = "lof"

WINDOW_SIZE = 50

# Delay between API calls.
# 0.0  -> fastest functional test
# 0.1  -> current development test
# 0.5  -> more realistic demonstration
DELAY_SECONDS = 0.1


# ---- Development controls ----

# Start from a particular dataset row or 0 from start.
# Current test covers the known anomalies:
# 705
# 794
# 915
# 1055
# 1073
# 1084

START_INDEX = 650


# Number of readings to process.
# Set to None to process until the end of the dataset.
MAX_READINGS = 450


# ---- Helpers ----

def build_reading(row, reading_id):
    """
    Convert one dataframe row into the API sensor-reading format.

    reading_id is the stable identifier used to recognize the
    same reading across multiple overlapping windows.
    """

    return {
        "reading_id": int(reading_id),
        "temperature": float(row["temperature"]),
        "humidity": float(row["humidity"]),
        "stock_count": int(row["stock_count"]),
    }


def send_window(window):
    """
    Send the current rolling window to /detect-window.
    """

    payload = {
        "model": MODEL,
        "readings": window,
    }

    response = requests.post(
        API_URL,
        json=payload,
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def build_detection_window(raw_window):
    """
    Build the detection window from the raw rolling buffer.

    Readings that have already generated an alert are excluded
    from future predictions.

    The original raw rolling buffer is never modified.
    """

    excluded_readings = (
        incident_manager.get_excluded_readings(
            MODEL
        )
    )

    valid_readings = [
        reading
        for reading in raw_window
        if reading["reading_id"]
        not in excluded_readings
    ]

    return valid_readings[
        -WINDOW_SIZE:
    ]


# ---- Main ----

def main():

    # Reset deduplication + incident state for a fresh playback

    incident_manager.reset()

    # Load dataset

    try:

        df = pd.read_csv(DATASET)

    except FileNotFoundError:

        print(
            f"[ERROR] Dataset not found: {DATASET}"
        )

        return

    except Exception as exc:

        print(
            f"[ERROR] Failed to read dataset: {exc}"
        )

        return

    # Validate required columns

    required_columns = [
        "temperature",
        "humidity",
        "stock_count",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        print(
            "[ERROR] Missing required columns: "
            f"{missing_columns}"
        )

        return

    # Validate START_INDEX

    if START_INDEX < 0:

        print(
            "[ERROR] START_INDEX cannot be negative."
        )

        return

    if START_INDEX >= len(df):

        print(
            f"[ERROR] START_INDEX {START_INDEX} "
            f"is outside the dataset."
        )

        return

    # Calculate playback range

    if MAX_READINGS is None:

        end_index = len(df)

    else:

        if MAX_READINGS <= 0:

            print(
                "[ERROR] MAX_READINGS must be "
                "positive or None."
            )

            return

        end_index = min(
            START_INDEX + MAX_READINGS,
            len(df),
        )

    total_readings = end_index - START_INDEX

    # Configuration output

    print("=" * 60)
    print("STREAM PLAYBACK")
    print("=" * 60)

    print(f"Dataset       : {DATASET}")
    print(f"Model         : {MODEL}")
    print(f"Window size   : {WINDOW_SIZE}")
    print(f"Start index   : {START_INDEX}")
    print(f"End index     : {end_index - 1}")
    print(f"Readings      : {total_readings}")
    print(f"Delay         : {DELAY_SECONDS}s")
    print(f"API           : {API_URL}")

    print("=" * 60)
    print()

    # Raw rolling buffer

    raw_window = []

    processed = 0

    total_anomaly_readings = 0

    total_alerts = 0

    alert_details = []

    detection_window = []

    # Stream readings one by one

    for index in range(
        START_INDEX,
        end_index,
    ):

        row = df.iloc[index]

        # Build reading

        try:

            reading = build_reading(
                row,
                reading_id=index,
            )

        except (ValueError, TypeError) as exc:

            print(
                f"[ERROR] Invalid reading "
                f"at index={index}: {exc}"
            )

            continue

        # Add newest reading to raw rolling buffer

        raw_window.append(reading)

        # Keep enough raw history to construct the next
        # WINDOW_SIZE valid readings even after anomalies
        # are excluded.

        max_raw_size = (
            WINDOW_SIZE
            + incident_manager.get_exclusion_count(
                MODEL
            )
        )

        if len(raw_window) > max_raw_size:

            raw_window = raw_window[
                -max_raw_size:
            ]

        processed += 1

        # Build detection window

        detection_window = (
            build_detection_window(
                raw_window
            )
        )

        # Buffer only during initial startup.
        #
        # After the first complete detection window exists,
        # every new reading should produce a prediction.

        if len(detection_window) < WINDOW_SIZE:

            print(
                f"[BUFFERING] "
                f"reading_id={index} "
                f"window="
                f"{len(detection_window)}/{WINDOW_SIZE}"
            )

            continue

        # Send rolling window to API

        try:

            result = send_window(
                detection_window
            )

        except requests.exceptions.ConnectionError:

            print(
                "[ERROR] Cannot connect to API."
            )

            print(
                f"        Expected API at: {API_URL}"
            )

            return

        except requests.exceptions.Timeout:

            print(
                f"[ERROR] API timeout "
                f"at reading_id={index}"
            )

            continue

        except requests.exceptions.HTTPError as exc:

            print(
                f"[ERROR] HTTP error "
                f"at reading_id={index}: {exc}"
            )

            try:

                print(
                    f"        Response: "
                    f"{exc.response.text}"
                )

            except Exception:
                pass

            continue

        except requests.exceptions.RequestException as exc:

            print(
                f"[ERROR] Request failed "
                f"at reading_id={index}: {exc}"
            )

            continue

        # Read API response

        total_anomalies = result.get(
            "total_anomalies",
            0,
        )

        anomalous_readings = result.get(
            "anomalous_readings",
            [],
        )

        total_anomaly_readings += (
            total_anomalies
        )

        # Anomalies found

        if total_anomalies > 0:

            new_alerts = 0
            extended_incidents = 0

            for anomaly in anomalous_readings:

                window_index = anomaly.get(
                    "reading_index"
                )

                if window_index is None:
                    continue

                try:

                    window_index = int(
                        window_index
                    )

                except (ValueError, TypeError):

                    continue

                # Make sure the API returned a valid
                # position within the submitted window.

                if (
                    window_index < 0
                    or window_index >= len(
                        detection_window
                    )
                ):
                    continue

                # Recover the stable dataset reading ID.

                detected_reading = (
                    detection_window[
                        window_index
                    ]
                )

                reading_id = int(
                    detected_reading[
                        "reading_id"
                    ]
                )

                score = anomaly.get(
                    "score"
                )

                reasons = anomaly.get(
                    "reasons",
                    [],
                )

                # Register the anomaly.
                #
                # "new"       -> first reading of a brand-new
                #                incident -> generate an alert.
                #
                # "extended"  -> joined an already-alerted,
                #                still-open incident -> no new
                #                alert, incident just grew.
                #
                # "duplicate" -> same reading already processed
                #                in an earlier overlapping
                #                window -> ignore.

                status, incident = (
                    incident_manager.register_anomaly(
                        MODEL,
                        reading_id,
                        score=score,
                        reasons=reasons,
                    )
                )

                if status == "duplicate":
                    continue

                if status == "extended":

                    extended_incidents += 1

                    print(
                        f"[INCIDENT UPDATED] "
                        f"start={incident['start']} "
                        f"end={incident['end']} "
                        f"count={incident['count']}"
                    )

                    continue

                # status == "new"

                new_alerts += 1
                total_alerts += 1

                alert_details.append(
                    {
                        "reading_id": reading_id,
                        "score": score,
                        "reasons": reasons,
                    }
                )

                print()
                print(
                    "[ANOMALY ALERT]"
                )

                print(
                    f"incident_start={incident['start']}"
                )

                print(
                    f"reading_id={reading_id}"
                )

                print(
                    f"window_end={index}"
                )

                print(
                    f"score={score}"
                )

                if reasons:

                    print(
                        f"reasons={reasons}"
                    )

            if new_alerts > 0 or extended_incidents > 0:

                print()
                print(
                    f"[DEDUPLICATED] "
                    f"New alerts={new_alerts} "
                    f"Incident updates={extended_incidents} "
                    f"Excluded readings="
                    f"{incident_manager.get_exclusion_count(MODEL)}"
                )

        # No anomalies

        else:

            print(
                f"[NORMAL] "
                f"window_end={index} "
                f"window_size="
                f"{len(detection_window)}"
            )

        # Close out any incident that has gone quiet, even
        # when the current reading itself was not anomalous.

        closed = incident_manager.close_stale_incidents(
            MODEL,
            index,
        )

        if closed:

            print()
            print(
                f"[INCIDENT CLOSED] "
                f"start={closed['start']} "
                f"end={closed['end']} "
                f"count={closed['count']} "
                f"peak_score={closed['max_score']}"
            )

        # Simulate streaming delay

        if DELAY_SECONDS > 0:

            time.sleep(
                DELAY_SECONDS
            )

    # Close any incident still open at the very end of playback

    if detection_window:

        final_closed = (
            incident_manager.close_stale_incidents(
                MODEL,
                end_index - 1
                + incident_manager.GAP_TOLERANCE
                + 1,
            )
        )

        if final_closed:

            print()
            print(
                f"[INCIDENT CLOSED] "
                f"start={final_closed['start']} "
                f"end={final_closed['end']} "
                f"count={final_closed['count']} "
                f"peak_score={final_closed['max_score']}"
            )

    # Playback completed

    print()
    print("=" * 60)
    print("STREAM PLAYBACK COMPLETED")
    print("=" * 60)

    print(
        f"Processed readings       : "
        f"{processed}"
    )

    print(
        f"Raw anomaly detections   : "
        f"{total_anomaly_readings}"
    )

    print(
        f"Unique incident alerts   : "
        f"{total_alerts}"
    )

    print(
        f"Excluded readings        : "
        f"{incident_manager.get_exclusion_count(MODEL)}"
    )

    print(
        f"Final window size        : "
        f"{len(detection_window) if processed > 0 else 0}"
    )

    print()

    # Incident summary

    print(
        "INCIDENT SUMMARY"
    )

    print("-" * 60)

    all_incidents = (
        incident_manager.get_all_incidents(
            MODEL
        )
    )

    if not all_incidents:

        print(
            "No incidents detected."
        )

    else:

        for incident in all_incidents:

            print(
                f"start={incident['start']} "
                f"end={incident['end']} "
                f"count={incident['count']} "
                f"peak_score={incident['max_score']}"
            )

    print()

    # Final anomaly summary

    print(
        "ANOMALY INDICES (incident starts)"
    )

    print("-" * 60)

    anomaly_indices = [
        detail["reading_id"]
        for detail in alert_details
    ]

    print(
        anomaly_indices
    )

    print()

    print(
        "ANOMALY DETAILS"
    )

    print("-" * 60)

    if not alert_details:

        print(
            "No unique anomaly alerts detected."
        )

    else:

        for detail in alert_details:

            print(
                f"reading_id={detail['reading_id']}"
            )

            print(
                f"score={detail['score']}"
            )

            if detail["reasons"]:

                print(
                    f"reasons={detail['reasons']}"
                )

            else:

                print(
                    "reasons=[]"
                )

            print("-" * 60)

    print("=" * 60)


# ---- Entry point ----

if __name__ == "__main__":
    main()
