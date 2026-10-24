# Fictional cache pilot source facts

All names, measurements and decisions in this bundle are fictional.

The selected workload repeats read-only requests for the same small set of keys, using a warm cache and one client. The four paired durations in measurements.csv are milliseconds per request. The synthetic arithmetic mean is 130 ms before and 93.5 ms after, a decrease of 36.5 ms (about 28.1%). The four samples do not establish production performance or a general statistical result.

The current pilot covers this limited workload only. There are no measurements for cold starts, writes, invalidation, concurrent clients or memory use. No expansion has been approved or implemented.

The proposed next step is a bounded mixed-workload trial covering cold starts and writes while observing memory use. It remains planned and requires the maintainer's decision. The note may recommend that trial, retain the current scope, or request additional evidence; it must distinguish its recommendation from an approved or completed expansion.
