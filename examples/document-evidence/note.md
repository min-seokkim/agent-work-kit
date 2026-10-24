# Extend the cache pilot with a bounded trial

The maintainer should authorize a mixed-workload trial before deciding on a wider rollout. The current fictional pilot measured faster repeated reads, but it leaves the costs of other workloads unmeasured. Expansion has neither been approved nor implemented.

## What the pilot measured

These four synthetic pairs measure milliseconds per request before and after caching:

| Sample | Before (ms) | After (ms) |
|---|---|---|
| 1 | 120 | 84 |
| 2 | 100 | 80 |
| 3 | 140 | 98 |
| 4 | 160 | 112 |

The arithmetic mean decreased from 130 ms to 93.5 ms, a reduction of 36.5 ms, or about 28.1%. These four samples describe repeated read-only requests for a small set of keys, with a warm cache and one client. They do not establish production performance or a general statistical result.

## What the next decision needs

Cold starts, writes, invalidation, concurrent clients and memory use remain unmeasured. The proposed next step is a bounded mixed-workload trial covering cold starts and writes while observing memory use. That trial remains planned and requires the maintainer's decision; it has not run. Its results would inform a later expansion decision.
