# Depth Test - Find the Upstream Multiplier

Use this example to check whether an auditor stops at a local inefficiency.

```csharp
_timer = new Timer(
    async _ => await RefreshAsync(_cts.Token),
    null,
    TimeSpan.Zero,
    TimeSpan.FromMilliseconds(500));

private async Task RefreshAsync(CancellationToken cancellationToken)
{
    foreach (var id in _activeIds)
    {
        var json = await File.ReadAllTextAsync(_rulesPath, cancellationToken);
        var rules = JsonSerializer.Deserialize<Rule[]>(json)!;
        var rule = rules.FirstOrDefault(candidate => candidate.Id == id);
        await _client.SendAsync(BuildRequest(id, rule), cancellationToken);
    }
}
```

A surface review says to move the read outside the loop, deserialize once, use
a dictionary, or parallelize requests. A deep audit first asks whether the
500 ms callback can overlap and amplify every operation in the method.

An acceptable discovery records the timer registration and path, but keeps
these facts unresolved until inspected or measured:

- concrete timer callback overlap semantics
- normal and maximum active-ID count
- request latency distribution and rate limits
- another overlap guard, deduplication layer, or downstream batching
- exception observation, cancellation, disposal, and awaited shutdown
- whether each tick represents required distinct state

Only if evidence establishes, for example, that callbacks overlap, no guard
exists, the ID count is about 100, and requests take about 20 ms serially may an
auditor form this supported model:

```text
starts per second = 2
minimum pass duration ~= active IDs x per-request latency
active passes ~= pass duration / timer period
per-second operations ~= starts per second x active IDs
```

The recommendation must then choose an explicit freshness policy: skip missed
ticks, coalesce into one pending refresh, or preserve each tick. It must account
for idempotency, rate limits, cancellation, and awaited shutdown. Measurement
should capture starts/completions, duration percentiles, active passes, file
reads, requests, queueing, and shutdown time.

The lesson is the gate: the file read is a local inefficiency; timer overlap may
be the upstream multiplier. Inspect the multiplier before optimizing the
symptom, and actively search for evidence that invalidates the model.
