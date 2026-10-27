"""Shared public/synthetic voice fixtures and offline sustained-VAD scoring."""

import numpy as np

from voxlock_trial import SR, load, make_case

BLOCK = 512


def window_score(probabilities, bounds, *, threshold=0.5):
    """32 ms probability decisions, restricted to blocks wholly inside the window.

    shortcut: only the no-transcript 640/160 ms sustained-evidence rule is replayed;
    use native SIP tests for echo rejection, ASR evidence and cancellation timing.
    Coverage is utterance-window coverage, not human-labelled speech recall.
    """
    if not np.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("threshold must be finite and between zero and one")
    starts = np.arange(len(probabilities)) * BLOCK
    select = (starts >= bounds[0]) & (starts + BLOCK <= bounds[1])
    values = np.asarray(probabilities)[select]
    assert len(values)
    # Match the gateway's float32 percentage conversion at threshold boundaries.
    positive = values >= float(np.float32(threshold))
    sustained, maximum, last = 0, 0, None
    trigger_at = None
    for i, voice in enumerate(positive):
        if voice:
            if last is None or (i - last - 1) * 32 >= 160:
                sustained = 0
            sustained += 32
            maximum = max(maximum, sustained)
            last = i
            if sustained >= 640 and trigger_at is None:
                trigger_at = int(starts[select][i] + BLOCK - bounds[0]) / SR * 1000
    first = np.flatnonzero(positive)
    return {
        "blocks": len(values),
        "positive_window_fraction": float(np.mean(positive)),
        "mean_probability": float(np.mean(values)),
        "max_sustained_evidence_ms": maximum,
        "sustained_trigger_ms_from_window_start": trigger_at,
        "first_positive_ms_from_window_start": (
            float(starts[select][first[0]] + BLOCK - bounds[0]) / SR * 1000 if len(first) else None
        ),
    }


def cases(fixtures, directory):
    items = [fixtures["fleurs-1853-1"], fixtures["greeting"]]
    signals = [load(item, directory) for item in items]
    for role in range(2):
        for condition in (
            "clean",
            "background-quiet",
            "background-equal",
            "background-first",
            "quiet-target",
            "quiet-clean",
        ):
            target = signals[role] * (
                0.25
                if condition == "quiet-target"
                else 0.0630957
                if condition == "quiet-clean"
                else 1
            )
            base = {"quiet-target": "background-equal", "quiet-clean": "clean"}.get(
                condition, condition
            )
            mix, windows = make_case(target, signals[1 - role], base)
            first = (5 if base == "background-first" else 1) * SR
            windows["target_first"] = [first, first + len(target)]
            if base == "background-first":
                windows["background_start"] = [0, first]
            yield f"{role}-{condition}", condition, mix, windows
    # An already heard synthetic caller returns briefly while a human voice continues.
    interrupt = load(fixtures["interrupt"], directory)
    for gain, name in ((1, "short-interrupt"), (0.25, "quiet-short-interrupt")):
        start = SR + len(signals[1]) + 7 * SR
        n = start + len(interrupt) + SR
        mix = np.zeros(n, np.float32)
        mix[SR : SR + len(signals[1])] = signals[1] * gain
        bg_start = SR + len(signals[1])
        mix[bg_start:] += np.resize(signals[0], n - bg_start)
        mix[start : start + len(interrupt)] += interrupt * gain
        yield (
            name,
            name,
            mix,
            {
                "background_only": [bg_start + SR, start - SR],
                "target_repeat": [start, start + len(interrupt)],
            },
        )
        clean = mix.copy()
        clean[bg_start:] = 0
        clean[start : start + len(interrupt)] = interrupt * gain
        yield (
            f"{name}-clean",
            f"{name}-clean",
            clean,
            {
                "background_only": [bg_start + SR, start - SR],
                "target_repeat": [start, start + len(interrupt)],
                "target_with_tail": [start, start + len(interrupt) + SR // 2],
            },
        )
    yield "silence", "silence", np.zeros(10 * SR, np.float32), {"silence": [SR, 9 * SR]}
