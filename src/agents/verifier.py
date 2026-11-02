"""M7 verifier: check every cited evidence item against the ToolLog.

Pure Python, no model call (ARCHITECTURE §1; EVALUATION_PROTOCOL §5). For each
`Evidence`:
  1. `ref_id` must exist in the investigation's ToolLog, else `missing_ref`.
  2. If both `stat` and `value` are given, `stat` must be a key somewhere in the
     logged output and the logged number must match within max(5% rel, 0.5 abs),
     else `unknown_stat` / `value_mismatch`.
  3. If `stat` or `value` is missing, the item is `verified_partial` (grounded by
     the ref only) and is counted apart from fully-supported items.
The claim text is not machine-checked; the manual spot-check measures that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from numbers import Real

from common.schemas import Evidence, HypothesisReport
from tools.toollog import ToolLog

_REL_TOL = 0.05
_ABS_TOL = 0.5

# Full + partial are ref-grounded and reach the adjudicator; the rest are excluded.
GROUNDED = ("verified", "verified_partial")


@dataclass
class ItemCheck:
    ref_id: str
    status: str                      # verified | verified_partial | missing_ref | ...
    reason: str | None = None
    logged_value: float | None = None


@dataclass
class VerifyStats:
    n_total: int = 0
    n_verified: int = 0              # fully supported (rule 2 passed)
    n_partial: int = 0              # ref-grounded only (rule 3)
    n_failed: int = 0
    items: list[ItemCheck] = field(default_factory=list)

    @property
    def n_grounded(self) -> int:
        return self.n_verified + self.n_partial

    def as_dict(self) -> dict:
        return {
            "n_total": self.n_total, "n_verified": self.n_verified,
            "n_partial": self.n_partial, "n_failed": self.n_failed,
            "items": [vars(it) for it in self.items],
        }


def _find_numeric(output: object, stat: str) -> tuple[bool, float | None]:
    """Search nested dicts/lists for key == stat; return (present, numeric value).

    `present` is True as soon as the key is seen anywhere, even if its value is
    not numeric (then the returned value is None, which fails the match).
    """
    present = False
    found_value: float | None = None
    stack: list[object] = [output]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                if k == stat:
                    present = True
                    if isinstance(v, Real) and not isinstance(v, bool):
                        return True, float(v)
                if isinstance(v, dict | list):
                    stack.append(v)
        elif isinstance(node, list):
            stack.extend(node)
    return present, found_value


def _matches(logged: float, claimed: float) -> bool:
    return abs(logged - claimed) <= max(_REL_TOL * abs(claimed), _ABS_TOL)


def _check_item(ev: Evidence, log: ToolLog) -> ItemCheck:
    full = log.get_full(ev.ref_id)
    if full is None:
        return ItemCheck(ev.ref_id, "missing_ref", "ref_id not in ToolLog")
    if ev.stat is None or ev.value is None:
        return ItemCheck(ev.ref_id, "verified_partial", "no stat/value to check")
    present, logged = _find_numeric(full.output, ev.stat)
    if not present:
        return ItemCheck(ev.ref_id, "unknown_stat", f"stat '{ev.stat}' not in output")
    if logged is None:
        return ItemCheck(ev.ref_id, "value_mismatch", "logged value is not numeric", None)
    if not _matches(logged, float(ev.value)):
        return ItemCheck(ev.ref_id, "value_mismatch",
                         f"logged {logged} vs claimed {ev.value}", logged)
    return ItemCheck(ev.ref_id, "verified", None, logged)


def verify_report(report: HypothesisReport, log: ToolLog) -> tuple[HypothesisReport, VerifyStats]:
    """Return a copy of the report with `verified` set, plus per-report counts."""
    stats = VerifyStats()
    new_evidence: list[Evidence] = []
    for ev in report.evidence:
        check = _check_item(ev, log)
        stats.n_total += 1
        stats.items.append(check)
        grounded = check.status in GROUNDED
        if check.status == "verified":
            stats.n_verified += 1
        elif check.status == "verified_partial":
            stats.n_partial += 1
        else:
            stats.n_failed += 1
        new_evidence.append(ev.model_copy(update={"verified": grounded}))
    verified_report = report.model_copy(update={"evidence": new_evidence})
    return verified_report, stats


def verified_only(report: HypothesisReport) -> HypothesisReport:
    """Drop evidence that failed verification (adjudicator input, ARCHITECTURE §2.5)."""
    kept = [ev for ev in report.evidence if ev.verified]
    return report.model_copy(update={"evidence": kept})
