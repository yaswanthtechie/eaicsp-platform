"""
Pure processing core: one reading in, writer + detector + events out.

Kafka and InfluxDB are behind two tiny interfaces:

    writer.write(reading, score, flagged)
    publisher.publish(event)

so the same code runs against real systems or in-memory fakes.

Duplicate or late readings (same or earlier timestamp for a sensor) are
skipped before scoring or writing.

Tuner feed: score goes to tuner.observe() only when the reading is not
flagged and the sensor has no candidate/open episode.
"""

from .stream_events import build_anomaly_event


class InMemoryWriter:

    def __init__(self):
        self.rows = []

    def write(self, reading, score, flagged):
        self.rows.append((reading, float(score), bool(flagged)))

    def close(self):
        pass


class InMemoryPublisher:

    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)

    def close(self):
        pass


class StreamProcessor:

    def __init__(
        self,
        model,
        tuner,
        detector,
        writer,
        publisher,
        use_tuner=True,
    ):
        self.model = model
        self.tuner = tuner
        self.detector = detector
        self.writer = writer
        self.publisher = publisher
        self.use_tuner = use_tuner

        self.readings_seen = 0
        self.flagged_count = 0
        self.skipped_stale = 0
        self.tuner_log = []

    def _publish(self, episode):

        episode = dict(episode)
        peak_reading = episode.pop("peak_reading")

        event = build_anomaly_event(
            **episode,
            top_features=self.model.explain(peak_reading),
            model_version=self.model.version,
        )

        self.publisher.publish(event)

        return event

    def handle(self, reading, score=None):
        """Process one reading. Return the list of events published."""

        sensor_id = reading["sensor_id"]

        if not self.detector.accepts(sensor_id, reading["timestamp"]):
            self.skipped_stale += 1
            return []

        if score is None:
            score = self.model.score_one(reading)

        score = float(score)
        threshold = float(self.tuner.threshold)
        flagged = score >= threshold

        self.writer.write(reading, score, flagged)

        episode = self.detector.process(
            sensor_id,
            reading["timestamp"],
            score,
            threshold,
            reading=reading,
        )

        events = []

        if episode is not None:
            events.append(self._publish(episode))

        if (
            self.use_tuner
            and not flagged
            and not self.detector.is_active(sensor_id)
        ):
            result = self.tuner.observe(score)

            if result is not None:
                self.tuner_log.append(result)

        self.readings_seen += 1
        self.flagged_count += int(flagged)

        return events

    def finish(self):
        """Flush open episodes at shutdown (closed_by='shutdown')."""

        return [self._publish(ep) for ep in self.detector.flush()]