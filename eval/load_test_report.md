# Load test, 2026-11-09 20:45

4 analyses started at once on 12 key(s), prompt V5, development set. 4 finished, 0 failed, in 0.5 minutes (median analysis 25 s).

Pool settings: 4 keys active at a time (rolling replacement); 15 requests and 250,000 tokens per minute assumed per key; a key with a named limit rests 60 s; a busy Google is waited out for up to 15 min.

Active at the end: key 1, key 2, key 3, key 4. Retired today (daily quota): none.

| Key | Most analyses at once | Peak calls / min | Peak tokens / min | Limits hit | Rests | Runs moved away |
|---|---|---|---|---|---|---|
| key 1 | 1 | 5 | 178,261 | 0 | 0 | 0 |
| key 2 | 1 | 5 | 109,326 | 0 | 0 | 0 |
| key 3 | 1 | 6 | 156,801 | 0 | 0 | 0 |
| key 4 | 1 | 5 | 90,927 | 0 | 0 | 0 |
| key 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| key 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| key 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| key 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| key 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| key 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| key 11 | 0 | 0 | 0 | 0 | 0 | 0 |
| key 12 | 0 | 0 | 0 | 0 | 0 | 0 |

Times every key was resting at once (the run had to wait): 0. Waits for a busy Google (503 or unnamed 429, run kept its key): 0.

## Verdict

All 4 analyses ran at once with no rate limit: the keys can carry 4 at a time.

Every event, in order (seconds from start):

```
(none)
```
