"""Automated, explainable, rule-based intervention recommender (ticket #14).

Input is the Latin-hypercube sample table produced by the sensitivity analysis
(:mod:`schoolsim.sensitivity`): one row per sampled parameter set, with the
scenario key and the resulting ``attack_rate`` (share of students infected over
the simulation, fraction 0-1).

The rule is deliberately simple and fully deterministic: a scenario's
robustness is the share of its samples whose estimated attack rate is at or
below the policy threshold, and the recommender returns the first scenario in
``INTERVENTION_ORDER`` that clears the robustness threshold. Nothing is fitted,
nothing is learned, and no language model is involved - the reason string is
assembled from the numbers in the table.

See ``docs/assumptions.md`` (recommender section) for why the two thresholds
are policy choices rather than estimates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from .params import load_params
from .scenarios import INTERVENTION_ORDER, get_label

_REQUIRED_COLUMNS = ("scenario", "attack_rate")
ONLINE_SCENARIO = "online"


@dataclass(frozen=True)
class Recommendation:
    """Outcome of one rule-based recommendation.

    Attributes:
        scenario: scenario key of the recommended option (a key in ``INTERVENTION_ORDER``).
        robustness: share of sampled parameter sets in which this scenario kept the
            estimated attack rate at or below the policy threshold (fraction, 0-1).
        reason: plain-language explanation; always states ``robustness`` as a percentage
            and never claims certainty.
        runner_up: scenario key of the most robust alternative, or ``None`` when the
            table holds only one scenario. Ties are broken towards the later (more
            protective) position in ``INTERVENTION_ORDER``.
    """

    scenario: str
    robustness: float
    reason: str
    runner_up: str | None


def recommend(
    lhs_df: pd.DataFrame,
    attack_threshold: float | None = None,
    robustness_threshold: float | None = None,
) -> Recommendation:
    """Pick the least disruptive intervention that is robust enough.

    Walks ``INTERVENTION_ORDER`` (baseline first, online last) and returns the first
    scenario whose robustness - the share of sampled parameter sets in which the
    estimated attack rate stayed at or below ``attack_threshold`` - meets
    ``robustness_threshold``. If no in-person scenario qualifies, returns the online
    scenario as a fallback.

    Args:
        lhs_df: Latin-hypercube sample table with at least ``scenario`` (keys of
            ``INTERVENTION_ORDER``; unknown keys are ignored) and ``attack_rate``
            (fraction of students infected, 0-1). Rows whose ``attack_rate`` is NaN or
            infinite count as failures - an unevaluated sample is not evidence of
            safety. A ``learner_days_lost`` column (days per student) is used in the
            reason text when present.
        attack_threshold: highest acceptable attack rate (fraction, 0-1). Defaults to
            ``params.yaml`` ``attack_rate_threshold``.
        robustness_threshold: required share of samples under ``attack_threshold``
            (fraction, 0-1). Defaults to ``params.yaml`` ``robustness_threshold``.

    Returns:
        The recommendation together with the numbers that produced it.

    Raises:
        ValueError: if ``lhs_df`` is empty or missing required columns, if either
            threshold is outside (0, 1], or if nothing qualifies and the online
            scenario is absent from ``lhs_df``.
    """
    missing = [column for column in _REQUIRED_COLUMNS if column not in lhs_df.columns]
    if missing:
        raise ValueError(f"lhs_df is missing required column(s): {', '.join(missing)}")
    if lhs_df.empty:
        raise ValueError("lhs_df is empty; nothing to recommend from")

    attack_threshold, robustness_threshold = _resolve_thresholds(
        attack_threshold, robustness_threshold
    )
    robustness = _robustness_by_scenario(lhs_df, attack_threshold)
    ordered = [scenario for scenario in INTERVENTION_ORDER if scenario in robustness.index]
    robustness = robustness.reindex(ordered)

    pick = next(
        (scenario for scenario in robustness.index if robustness[scenario] >= robustness_threshold),
        None,
    )
    if pick is None:
        if ONLINE_SCENARIO not in robustness.index:
            raise ValueError(
                "no scenario met robustness_threshold and the online fallback is absent "
                "from lhs_df"
            )
        pick = ONLINE_SCENARIO

    others = [
        (scenario, float(robustness[scenario]))
        for scenario in robustness.index
        if scenario != pick
    ]
    if others:
        runner_up, _ = max(
            others, key=lambda item: (item[1], INTERVENTION_ORDER.index(item[0]))
        )
    else:
        runner_up = None

    reason = _format_reason(
        pick=pick,
        robustness=robustness,
        runner_up=runner_up,
        learner_days=_mean_learner_days(lhs_df, pick, runner_up),
        thresholds=(attack_threshold, robustness_threshold),
    )
    return Recommendation(
        scenario=pick,
        robustness=float(robustness[pick]),
        reason=reason,
        runner_up=runner_up,
    )


def _resolve_thresholds(
    attack_threshold: float | None, robustness_threshold: float | None
) -> tuple[float, float]:
    """Fill missing thresholds from ``params.yaml`` and validate both."""
    params = load_params() if attack_threshold is None or robustness_threshold is None else None
    if attack_threshold is None:
        attack_threshold = float(params["attack_rate_threshold"].value)
    if robustness_threshold is None:
        robustness_threshold = float(params["robustness_threshold"].value)
    if not 0.0 < attack_threshold <= 1.0:
        raise ValueError(f"attack_threshold must be in (0, 1], got {attack_threshold}")
    if not 0.0 < robustness_threshold <= 1.0:
        raise ValueError(f"robustness_threshold must be in (0, 1], got {robustness_threshold}")
    return attack_threshold, robustness_threshold


def _robustness_by_scenario(lhs_df: pd.DataFrame, attack_threshold: float) -> pd.Series:
    """Share of samples per scenario at or below ``attack_threshold`` (fraction).

    ``nan <= x`` and ``inf <= x`` are both False, so samples the simulation could not
    evaluate (diverged integrator, empty aggregation group) count against the scenario
    instead of silently inflating its robustness. No masking code is needed.
    """
    frame = lhs_df[["scenario", "attack_rate"]]
    under_threshold = frame["attack_rate"] <= attack_threshold
    return under_threshold.groupby(frame["scenario"], sort=False).mean()


def _mean_learner_days(
    lhs_df: pd.DataFrame, pick: str, runner_up: str | None
) -> tuple[float, float] | None:
    """Mean learner-days lost per student for ``pick`` and ``runner_up``, or None."""
    if runner_up is None or "learner_days_lost" not in lhs_df.columns:
        return None
    means = lhs_df.groupby("scenario")["learner_days_lost"].mean()
    if pick not in means.index or runner_up not in means.index:
        return None
    pick_days, runner_days = float(means[pick]), float(means[runner_up])
    if not all(math.isfinite(day) for day in (pick_days, runner_days)):
        return None
    return pick_days, runner_days


def _format_reason(
    *,
    pick: str,
    robustness: pd.Series,
    runner_up: str | None,
    learner_days: tuple[float, float] | None,
    thresholds: tuple[float, float],
) -> str:
    """Assemble the plain-language reason; always reports robustness as a percentage."""
    attack_threshold, robustness_threshold = thresholds
    pick_robustness = float(robustness[pick])

    if pick == ONLINE_SCENARIO:
        sentences = [
            f"No face-to-face option kept the estimated attack rate at or below "
            f"{attack_threshold:.0%} in at least {robustness_threshold:.0%} of plausible "
            f"scenario samples; online learning is the fallback and stays under the "
            f"threshold in {pick_robustness:.0%} of samples."
        ]
    else:
        sentences = [
            f"{get_label(pick)} keeps the estimated attack rate at or below "
            f"{attack_threshold:.0%} in {pick_robustness:.0%} of plausible scenario samples."
        ]

    if runner_up is None:
        return " ".join(sentences)

    runner_label = get_label(runner_up)
    runner_robustness = float(robustness[runner_up])
    if INTERVENTION_ORDER.index(runner_up) > INTERVENTION_ORDER.index(pick):
        sentences.append(
            f"{runner_label} is at least as protective ({runner_robustness:.0%}) but is "
            f"a more disruptive intervention."
        )
    else:
        sentences.append(
            f"{runner_label} stays under the threshold in only {runner_robustness:.0%} of samples."
        )
    if learner_days is not None:
        pick_days, runner_days = learner_days
        sentences.append(
            f"Mean estimated learner-days lost: {pick_days:.1f} per student for "
            f"{get_label(pick)} versus {runner_days:.1f} for {runner_label}."
        )
    return " ".join(sentences)