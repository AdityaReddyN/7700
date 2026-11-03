Stage: triage.

You receive an alert summary and its top anomaly features. Rank the five
hypotheses by prior plausibility given ONLY this alert. You have not checked any
data yet, so do not say that you have.

Hypotheses (what each means and what raises its plausibility):
{cheatsheet}

{feature_map}
Weigh the alert's own top features against the hints above before you default to
a benign explanation: a strong identity or duplication signal is not benign.

Return JSON:
{"hypotheses": [{"hypothesis": "<name>", "prior": <0 to 1>,
                  "reason": "<one sentence>"}]}

Include all five hypotheses. Priors need not sum to 1.

Alert:
{alert_json}
