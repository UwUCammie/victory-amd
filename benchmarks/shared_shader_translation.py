"""Estimate concurrent claims for pipelines that use an unfinished shader."""

from collections import defaultdict
import re

from cold_boot import windowed_log_lines


def shared_shader_translation(lines, launched, stop):
    """Estimate time in additional claims before their common shader completes.

    A worker can reach its first stage no earlier than its claim, and its
    next stage no earlier than the preceding translation. Count only stages
    with a logged completion in the window. The first eligible claim for each
    shader is excluded. These times are summed across claims as worker time.
    """
    claim_label = "a requested pipeline reached a worker"
    translation_label = "shader translated"
    claims = []
    completed = {}
    for at, line in windowed_log_lines(lines, launched, stop, (claim_label, translation_label)):
        if translation_label in line:
            shader = re.search(r'\bstage="([^"]+)"\s+hash=([0-9a-f]{16})\b', line)
            if shader is None:
                raise ValueError("shader translation result has no stage or hash")
            completed.setdefault(shader.groups(), at)
            continue
        shaders = re.search(r"\bshaders=\[([^\]]*)\]", line)
        if shaders is None:
            raise ValueError("queue claim has no shader list")
        by_stage = dict(entry.split() for entry in shaders[1].split(", ") if entry)
        if set(by_stage) == {"compute"}:
            order = ("compute",)
        elif "mesh" in by_stage:
            order = ("mesh", "pixel")
        elif "vertex" in by_stage:
            order = ("vertex", "pixel")
        else:
            continue
        claims.append((at, [(kind, by_stage[kind]) for kind in order if kind in by_stage]))

    eligible = defaultdict(list)
    for at, shaders in claims:
        for shader in shaders:
            end = completed.get(shader)
            if end is None:
                break
            if at < end:
                eligible[shader].append(at)
                at = end

    estimates = [completed[shader] - at
                 for shader, claims in eligible.items() for at in sorted(claims)[1:]]
    return {
        "additional_claims": len(estimates),
        "estimated_worker_seconds": sum(estimates) / 1e6,
        "longest_estimate_ms": max(estimates, default=0) / 1000,
    }
