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

ADAPTIVE_API_URL = "http://127.0.0.1:8000/detect-adaptive"

WINDOW_API_URL = "http://127.0.0.1:8000/detect-window"

DATASET = "test_temperature_drift.csv"

DATASET_PATH = project_root / "output" / DATASET

MODEL = "lof"

WINDOW_SIZE = 50

# Delay between API calls.
# 0.0  -> fastest functional test
# 0.1  -> current development test
# 0.5  -> more realistic demonstration
DELAY_SECONDS = 0.1


# ---- Development controls ----

# Start near the consecutive-anomaly region in the
# dataset so that IncidentManager can demonstrate incident deduplication.

START_INDEX = 3300


# Number of readings to process.
# Set to None to process until the end of the dataset.
MAX_READINGS = 450


# ---- Helpers ----

def select_mode():
    """
    Ask the user which detection mode should be demonstrated.

    1 -> Adaptive
    2 -> Window
    3 -> Both
    """

    print("=" * 60)
    print("SELECT DETECTION MODE")
    print("=" * 60)

    print()
    print("1. Adaptive")
    print("2. Window")
    print("3. Both")
    print()

    while True:

        choice = input(
            "Enter choice [1-3]: "
        ).strip()

        if choice == "1":

            return "adaptive"

        if choice == "2":

            return "window"

        if choice == "3":

            return "both"

        print(
            "[ERROR] Please enter 1, 2, or 3."
        )


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
        WINDOW_API_URL,
        json=payload,
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


def send_adaptive(readings):
    """
    Send a batch of readings to /detect-adaptive.

    The adaptive endpoint processes the readings sequentially
    through the same stateful AdaptiveEngine.
    """

    payload = {
        "model": MODEL,
        "readings": readings,
    }

    response = requests.post(
        ADAPTIVE_API_URL,
        json=payload,
        timeout=20,
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


def print_incident_summary(
    mode,
    processed,
    total_anomaly_readings,
    total_alerts,
    alert_details,
    detection_window,
):
    """
    Print the final playback and incident summary.
    """

    print()
    print("=" * 60)
    print(
        f"STREAM PLAYBACK COMPLETED - "
        f"{mode.upper()}"
    )
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
        f"{len(detection_window) if mode == 'window' else 0}"
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


# ---- Main ----

def run_playback(
    mode,
    df,
    end_index,
):
    """
    Run one complete playback using the selected detection mode.
    """

    # Reset deduplication + incident state for a fresh playback

    incident_manager.reset()

    total_readings = end_index - START_INDEX

    api_url = (
        ADAPTIVE_API_URL
        if mode == "adaptive"
        else WINDOW_API_URL
    )

    # Configuration output

    print()
    print("=" * 60)
    print("STREAM PLAYBACK")
    print("=" * 60)

    print(f"Mode          : {mode}")
    print(f"Dataset       : {DATASET}")
    print(f"Model         : {MODEL}")

    if mode == "window":

        print(f"Window size   : {WINDOW_SIZE}")

    else:

        print(
            f"Batch size    : {WINDOW_SIZE}"
        )

    print(f"Start index   : {START_INDEX}")
    print(f"End index     : {end_index - 1}")
    print(f"Readings      : {total_readings}")
    print(f"Delay         : {DELAY_SECONDS}s")
    print(f"API           : {api_url}")

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

    index = START_INDEX

    while index < end_index:

        # ----------------------------------------------------
        # ADAPTIVE MODE
        # ----------------------------------------------------

        if mode == "adaptive":

            batch_end = min(
                index + WINDOW_SIZE,
                end_index,
            )

            batch_readings = []

            for batch_index in range(
                index,
                batch_end,
            ):

                row = df.iloc[
                    batch_index
                ]

                try:

                    reading = build_reading(
                        row,
                        reading_id=batch_index,
                    )

                except (ValueError, TypeError) as exc:

                    print(
                        f"[ERROR] Invalid reading "
                        f"at index={batch_index}: {exc}"
                    )

                    continue

                batch_readings.append(
                    reading
                )

            if not batch_readings:

                index = batch_end

                continue

            try:

                result = send_adaptive(
                    batch_readings
                )

            except requests.exceptions.ConnectionError:

                print(
                    "[ERROR] Cannot connect to API."
                )

                print(
                    f"        Expected API at: "
                    f"{ADAPTIVE_API_URL}"
                )

                return

            except requests.exceptions.Timeout:

                print(
                    f"[ERROR] API timeout "
                    f"for readings "
                    f"{index}-{batch_end - 1}"
                )

                index = batch_end

                continue

            except requests.exceptions.HTTPError as exc:

                print(
                    f"[ERROR] HTTP error "
                    f"for readings "
                    f"{index}-{batch_end - 1}: {exc}"
                )

                try:

                    print(
                        f"        Response: "
                        f"{exc.response.text}"
                    )

                except Exception:
                    pass

                index = batch_end

                continue

            except requests.exceptions.RequestException as exc:

                print(
                    f"[ERROR] Request failed "
                    f"for readings "
                    f"{index}-{batch_end - 1}: {exc}"
                )

                index = batch_end

                continue

            processed += len(
                batch_readings
            )

            total_anomalies = result.get(
                "total_anomalies",
                0,
            )

            total_anomaly_readings += (
                total_anomalies
            )

            adaptive_results = result.get(
                "adaptive_results",
                [],
            )

            # Process individual adaptive results.
            #
            # The API processes the batch sequentially, so
            # each result still corresponds to one reading.

            for adaptive_result in adaptive_results:

                reading_id = adaptive_result.get(
                    "reading_id"
                )

                if reading_id is None:

                    continue

                try:

                    reading_id = int(
                        reading_id
                    )

                except (ValueError, TypeError):

                    continue

                is_anomaly = adaptive_result.get(
                    "is_anomaly",
                    False,
                )

                score = adaptive_result.get(
                    "score"
                )

                reasons = adaptive_result.get(
                    "reasons",
                    [],
                )

                regime_changed = adaptive_result.get(
                    "regime_changed",
                    False,
                )

                regime_confirmed = adaptive_result.get(
                    "regime_confirmed",
                    False,
                )

                temporal_drift = adaptive_result.get(
                    "temporal_drift",
                    False,
                )

                adapted = adaptive_result.get(
                    "adapted",
                    False,
                )

                # Determine the visible status for this
                # individual reading.

                if is_anomaly:

                    status = "ANOMALY"

                elif temporal_drift:

                    status = "TEMPORAL_DRIFT"

                elif regime_confirmed:

                    status = "REGIME_CONFIRMED"

                elif regime_changed:

                    status = "REGIME_CHANGE"

                elif adapted:

                    status = "ADAPTED"

                else:

                    status = "NORMAL"

                print(
                    f"[ADAPTIVE] "
                    f"reading_id={reading_id} "
                    f"status={status} "
                    f"score={score}"
                )

                # Show lifecycle information directly on
                # the reading where it happened.

                if regime_changed:

                    print(
                        f"    [REGIME CHANGE] "
                        f"reading_id={reading_id}"
                    )

                if regime_confirmed:

                    print(
                        f"    [REGIME CONFIRMED] "
                        f"reading_id={reading_id}"
                    )

                if temporal_drift:

                    print(
                        f"    [TEMPORAL DRIFT] "
                        f"reading_id={reading_id}"
                    )

                if adapted:

                    print(
                        f"    [THRESHOLD ADAPTED] "
                        f"reading_id={reading_id}"
                    )

                # Normal readings require no IncidentManager
                # processing.

                if not is_anomaly:

                    continue

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

                    print(
                        f"    [INCIDENT UPDATED] "
                        f"start={incident['start']} "
                        f"end={incident['end']} "
                        f"count={incident['count']}"
                    )

                    continue

                # status == "new"

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
                    f"score={score}"
                )

                if reasons:

                    print(
                        f"reasons={reasons}"
                    )

            # Close out any incident that has gone quiet.

            closed = (
                incident_manager.close_stale_incidents(
                    MODEL,
                    batch_end - 1,
                )
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

            if DELAY_SECONDS > 0:

                time.sleep(
                    DELAY_SECONDS
                )

            index = batch_end

            continue

        # ----------------------------------------------------
        # WINDOW MODE
        # ----------------------------------------------------

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

            index += 1

            continue

        processed += 1

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

            index += 1

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
                f"        Expected API at: "
                f"{WINDOW_API_URL}"
            )

            return

        except requests.exceptions.Timeout:

            print(
                f"[ERROR] API timeout "
                f"at reading_id={index}"
            )

            index += 1

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

            index += 1

            continue

        except requests.exceptions.RequestException as exc:

            print(
                f"[ERROR] Request failed "
                f"at reading_id={index}: {exc}"
            )

            index += 1

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

            if (
                new_alerts > 0
                or extended_incidents > 0
            ):

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

        index += 1

    # Close any incident still open at the very end of playback

    final_closed = (
        incident_manager.close_stale_incidents(
            MODEL,
            end_index
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

    print_incident_summary(
        mode=mode,
        processed=processed,
        total_anomaly_readings=total_anomaly_readings,
        total_alerts=total_alerts,
        alert_details=alert_details,
        detection_window=detection_window,
    )


# ---- Main ----

def main():

    # Select detection mode

    mode = select_mode()

    # Load dataset

    try:

        df = pd.read_csv(
            DATASET_PATH
        )

    except FileNotFoundError:

        print(
            f"[ERROR] Dataset not found: "
            f"{DATASET}"
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

    # Run selected playback

    if mode == "adaptive":

        run_playback(
            mode="adaptive",
            df=df,
            end_index=end_index,
        )

        return

    if mode == "window":

        run_playback(
            mode="window",
            df=df,
            end_index=end_index,
        )

        return

    # Run both modes separately.
    #
    # IncidentManager is reset at the start of each playback,
    # so adaptive and window results remain independent.

    if mode == "both":

        print()
        print("=" * 60)
        print("RUNNING ADAPTIVE PLAYBACK")
        print("=" * 60)

        run_playback(
            mode="adaptive",
            df=df,
            end_index=end_index,
        )

        print()
        print("=" * 60)
        print("RUNNING WINDOW PLAYBACK")
        print("=" * 60)

        run_playback(
            mode="window",
            df=df,
            end_index=end_index,
        )

        print()
        print("=" * 60)
        print("BOTH PLAYBACK MODES COMPLETED")
        print("=" * 60)


# ---- Entry point ----

if __name__ == "__main__":
    main()