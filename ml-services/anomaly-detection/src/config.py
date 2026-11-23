# Elliptic Envelope contamination rate.
# Matches the planted anomaly rate: 20 anomalies out of 5000 samples.
ELLIPTIC_CONTAMINATION = 0.004


# Sales anomaly detection (R15-K4)
# Design values; Z_SPIKE is calibrated on the clean seed (see
# src/calibrate_sales_anomaly.py and the README).

LOOKBACK_WEEKS = 8
MIN_WEEKS = 4
MIN_SERIES_DAYS = 56

# 1.4826 turns a MAD into a standard deviation for normally distributed data.
MAD_TO_SIGMA = 1.4826

# Daily sales are over-dispersed (variance = mu + mu^2 / k). k = 8 matches
# data-platform/seed/demand.py:45 (gamma shape 8).
DISPERSION_K = 8.0

# Spike threshold calibrated on the clean seed (no planted anomalies) to a
# false-alarm budget of 2 per 1000 scored days. See README.
Z_SPIKE = 5.0
SPIKE_MEDIUM = 7.0
SPIKE_HIGH = 10.0

# A drop is a share of the expected value; z cannot see drops under
# over-dispersion (a fall to 0 is only about sqrt(k) = 2.8 scale units).
DROP_MIN_EXPECTED = 15.0
DROP_LOW = 0.20
DROP_MEDIUM = 0.10
DROP_HIGH = 0.05

# False-alarm budget used by src/calibrate_sales_anomaly.py: false alarms per
# scored day on a clean file (2 per 1000).
FALSE_ALARM_BUDGET = 2 / 1000

# A flagged day continues the previous incident when it has the same direction
# and comes at most this many days after the last flagged day. Covers feed-gap
# days and weekdays that fall under DROP_MIN_EXPECTED inside one incident.
RUN_GAP_DAYS = 7

# Calibration needs at least this many days of clean data (three months).
MIN_CALIBRATION_DAYS = 90


# Data drift check (R15-K6)
# The latest load (last DRIFT_LATEST_DAYS days of the input) is compared with the
# setup window (the clean data the thresholds were calibrated on). Both sides
# are two columns: the daily quantity and the zero-sales flag.

# Four full weeks, so every weekday counts the same on both sides.
DRIFT_LATEST_DAYS = 28

# Rows per side given to Evidently (seeded random sample), to keep the report fast.
DRIFT_SAMPLE_ROWS = 50_000

# Per-column drift thresholds (Evidently defaults): normalised Wasserstein
# distance for the quantity, Jensen-Shannon distance for the zero-sales flag.
DRIFT_NUM_THRESHOLD = 0.1
DRIFT_CAT_THRESHOLD = 0.1

# A warning is logged when at least this share of the two columns drifted
# (0.5 = either one).
DRIFT_ALERT_SHARE = 0.5

# Stock shrinkage check (R15-K7)
# Between two inventory snapshots: expected on-hand = start on-hand + received
# - sold; unexplained drop (gap) = expected - actual. A pair is flagged when the
# gap is at least SHRINK_MIN_UNITS units AND at least SHRINK_MIN_PCT of the
# expected on-hand. Design values: there is no labelled loss data yet, so they
# are not calibrated (see README).
SHRINK_MIN_UNITS = 10
SHRINK_MIN_PCT = 0.05

# Severity needs BOTH the units and the share of its level.
SHRINK_MEDIUM_UNITS = 25
SHRINK_MEDIUM_PCT = 0.10
SHRINK_HIGH_UNITS = 50
SHRINK_HIGH_PCT = 0.20
