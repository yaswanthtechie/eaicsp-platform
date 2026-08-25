import threading


class IncidentManager:
    """
    Anomaly deduplication + incident grouping manager.

    Responsibilities:
        - Track readings that already triggered an alert
          (prevents the same reading re-alerting due to
          overlapping detection windows).
        - Group consecutive anomalous readings from one
          underlying issue into a single incident with a
          start/end range, instead of one alert per reading.
        - Provide the list/set of readings that should be
          excluded from future detection windows.
        - Keep state separate for each model.

    IMPORTANT - behavior change from the original version:
        register_anomaly() now returns a tuple:
            (status, incident)
        instead of a plain bool. See register_anomaly() docstring.
    """

    # Max gap, in reading_id units, between two anomalous
    # readings for them to still count as the SAME ongoing
    # incident. If the gap is larger, the old incident is
    # closed and a new one is opened.
    GAP_TOLERANCE = 3

    def __init__(self):
        self.lock = threading.Lock()

        # Reading IDs that have already generated an alert.
        # Example:
        # {"lof": {890, 915, 920},
        #     "iforest": {890, 918},
        #     "ocsvm": {915}}

        self.excluded_readings = {
            "iforest": set(),
            "lof": set(),
            "ocsvm": set(),
        }

        # Currently open (not yet closed) incident per model,
        # or None if there isn't one.
        #
        # An incident looks like:
        # {
        #     "start": 900,
        #     "end": 904,
        #     "count": 5,
        #     "max_score": 0.87,
        #     "reasons": [...],
        # }

        self.open_incidents = {
            "iforest": None,
            "lof": None,
            "ocsvm": None,
        }

        # Finalized incidents per model.

        self.closed_incidents = {
            "iforest": [],
            "lof": [],
            "ocsvm": [],
        }

    # Validation

    def _validate_model(self, model):
        """
        Validate the requested model.
        """

        if model not in self.excluded_readings:
            raise ValueError(
                f"Invalid model: {model}"
            )

    # Check whether reading is already excluded

    def is_excluded(
        self,
        model,
        reading_id,
    ):
        """
        Return True if this reading has already triggered
        an anomaly alert for the specified model.
        """

        reading_id = int(reading_id)

        with self.lock:

            self._validate_model(model)

            return (
                reading_id
                in self.excluded_readings[model]
            )

    # Register anomaly / create or extend an incident

    def register_anomaly(
        self,
        model,
        reading_id,
        score=None,
        reasons=None,
    ):
        """
        Register a reading as anomalous.

        Returns a tuple: (status, incident)

            status == "new"
                First reading of a brand-new incident.
                An alert SHOULD be generated.
                incident is the newly opened incident dict.

            status == "extended"
                This reading joined an already-alerted,
                still-open incident (it is within
                GAP_TOLERANCE of the incident's last
                reading). No new alert should be generated;
                the existing alert's incident just grew.
                incident is the updated incident dict.

            status == "duplicate"
                This exact reading_id was already processed
                before (e.g. it reappeared in an overlapping
                detection window). Ignore it entirely.
                incident is None.
        """

        reading_id = int(reading_id)

        with self.lock:

            self._validate_model(model)

            # Already processed this exact reading before.

            if (
                reading_id
                in self.excluded_readings[model]
            ):

                return "duplicate", None

            self.excluded_readings[model].add(
                reading_id
            )

            incident = self.open_incidents[model]

            # Extend the currently open incident if this
            # reading is close enough to its last reading.

            if (
                incident is not None
                and (
                    reading_id - incident["end"]
                    <= self.GAP_TOLERANCE
                )
            ):

                incident["end"] = reading_id
                incident["count"] += 1

                if (
                    score is not None
                    and (
                        incident["max_score"] is None
                        or score > incident["max_score"]
                    )
                ):

                    incident["max_score"] = score
                    incident["reasons"] = (
                        reasons
                        if reasons
                        else incident["reasons"]
                    )

                return "extended", incident

            # Gap too large, or no open incident yet.
            # Close the old one (if any) and open a new one.

            if incident is not None:

                self.closed_incidents[model].append(
                    incident
                )

            new_incident = {
                "start": reading_id,
                "end": reading_id,
                "count": 1,
                "max_score": score,
                "reasons": reasons if reasons else [],
            }

            self.open_incidents[model] = new_incident

            return "new", new_incident

    # Close an incident that has gone quiet

    def close_stale_incidents(
        self,
        model,
        current_reading_id,
    ):
        """
        Finalize the open incident for this model if no new
        anomalous reading has joined it for more than
        GAP_TOLERANCE readings.

        Call this once per processed reading (anomalous or
        not) so an incident gets closed even when the stream
        simply goes quiet, rather than only closing when the
        NEXT incident happens to start.

        Returns the closed incident dict, or None if nothing
        was closed.
        """

        current_reading_id = int(
            current_reading_id
        )

        with self.lock:

            self._validate_model(model)

            incident = self.open_incidents[model]

            if incident is None:
                return None

            if (
                current_reading_id - incident["end"]
                > self.GAP_TOLERANCE
            ):

                self.closed_incidents[model].append(
                    incident
                )

                self.open_incidents[model] = None

                return incident

            return None

    # Get excluded readings

    def get_excluded_readings(
        self,
        model,
    ):
        """
        Return a copy of the readings that should be removed
        from future detection windows.
        """

        with self.lock:

            self._validate_model(model)

            return set(
                self.excluded_readings[model]
            )

    # Remove one reading from exclusion

    def remove_excluded_reading(
        self,
        model,
        reading_id,
    ):
        """
        Remove a reading from the exclusion set.

        This is mainly useful for testing or future operational
        recovery behavior.
        """

        reading_id = int(reading_id)

        with self.lock:

            self._validate_model(model)

            self.excluded_readings[model].discard(
                reading_id
            )

    # Get exclusion count

    def get_exclusion_count(
        self,
        model,
    ):
        """
        Return the number of readings that have already
        generated alerts.
        """

        with self.lock:

            self._validate_model(model)

            return len(
                self.excluded_readings[model]
            )

    # Get all incidents (closed + currently open)

    def get_all_incidents(
        self,
        model,
    ):
        """
        Return all incidents for this model: every closed
        incident plus the currently open one (if any), in
        chronological order.
        """

        with self.lock:

            self._validate_model(model)

            incidents = list(
                self.closed_incidents[model]
            )

            if self.open_incidents[model] is not None:

                incidents.append(
                    self.open_incidents[model]
                )

            return incidents

    # Reset

    def reset(self):
        """
        Clear all deduplication and incident state.
        """

        with self.lock:

            for model in self.excluded_readings:

                self.excluded_readings[model].clear()
                self.open_incidents[model] = None
                self.closed_incidents[model].clear()


# Shared incident manager

incident_manager = IncidentManager()