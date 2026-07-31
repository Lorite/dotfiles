---
name: lorite-experiment-campaign
description: Author or extend a campaign (experiments/<exp>/campaigns/*.yaml) for an EXISTING experiment in the robotics repo (~/git/lorite_ros2_humble_phd) — decide sweep vs fixed factors, repetitions, the T-0 gate, operator steps and verify steps, then validate with campaign_spec, campaign_plan, the config lint and a trial_runner dry run before anyone proposes --execute. A thin, repo-first procedure: the source of truth is experiments/AGENTS.md, the framework guide and the lint, not this file. Use when asked to create a new campaign, add a sweep or new conditions to an existing experiment, or turn an approved design's conditions matrix into runnable trials. NOT for designing a new experiment (lorite-experiment-designer) and NOT for operating trials or hardware (lorite-experiment-coder).
---

# lorite-experiment-campaign — author a campaign for an existing experiment

A campaign says *what set of trials under what conditions*. This skill turns that decision into a validated `campaigns/*.yaml`, and nothing more: it does not design experiments and it does not run trials.

**Repo-first, by design.** The durable knowledge lives in the robotics repo, enforced there rather than written here: `experiments/AGENTS.md` holds the conventions, `docs/development/experiments_framework_guide.md` holds the procedure (section "Authoring a new campaign"), and `experiments/common/scripts/test_experiment_config_lint.py` holds the incident-derived rules. This file carries only the trigger, the reading order, and the judgment questions a human-plus-LLM conversation genuinely adds. When this file and the repo disagree, the repo wins. When a campaign incident teaches something checkable, add a lint rule in the repo instead of a paragraph here.

## When to use
- A new campaign for an experiment that already exists under `experiments/`.
- Extending or adjusting an existing campaign: a new sweep, changed conditions, a campaign-scoped gate.
- Turning the conditions matrix of an approved `lorite-experiment-designer` design into campaign YAML.
- Not for a new experiment (factors, contract, runner, preflight): that scaffold is `lorite-experiment-designer` territory. Not for executing trials: dry runs are fine here, `--execute` belongs to the user or `lorite-experiment-coder`, and hardware always needs explicit per-session approval.

## Read first, in this order
1. The driving vault task note (per `/lorite`), for what this campaign is meant to evidence.
2. `experiments/AGENTS.md`: the campaign bullets and the config-lint block.
3. `docs/development/experiments_framework_guide.md`, section "Authoring a new campaign".
4. The experiment's own declarations under `experiments/<exp>/config/`: `factors.yaml` (merged over `experiments/common/config/factors.yaml`), `trial_metadata_schema.yaml`, `runner.yaml` (its steps and its `verify_steps`), `preflight_checklist.json`.
5. The nearest existing campaign as the exemplar, because the living schema is the existing campaigns plus `campaign_spec.py`, not anyone's memory. The smallest complete one is `experiments/demo_talker_listener/campaigns/rates.yaml`. The richest operator prose is `experiments/ros2_crazyflie_crazyswarm2_realsense_apriltag_mocap/campaigns/icra_exp1_vision_hover.yaml`.

## The judgment questions (settle these with the user before writing YAML)
1. **What claim will these trials evidence?** One campaign, one claim. It becomes `describe`, written so the operator six months from now understands what the data was for and what was safety-critical about collecting it.
2. **Which factors sweep, which stay fixed, how many repetitions?** Every swept factor must declare a `metadata_key` that is `factor: true` in the metadata contract, otherwise the campaign is refused (coverage that cannot be measured is worse than no sweep).
3. **What must positively hold at T-0?** Default is the experiment's `config/preflight_checklist.json`. Declare a campaign-scoped checklist only when the preconditions genuinely differ, written as a positive list of what must hold, never the flight list with entries removed (a gate the operator expects to see fail trains them to wave a NO-GO through).
4. **What does the operator do before vs during the trial?** `operator_steps` are read before, `operator_live_steps` while airborne. Mixing them is how a live action gets done too early or missed.
5. **What would prove the trial did what the campaign claims?** That is `verify_steps`. An exit code describes a process, only the bag describes the experiment. The runner's `verify_steps` are universal (did it fly), the campaign's are specific to what it asked a human to do (was vision actually in the loop). They merge, so never restate the runner's.

## Author, then validate
Copy the nearest campaign and adapt it. Then run all four, in order, inside the dev container, before anyone proposes `--execute`:

```bash
python3 experiments/common/scripts/campaign_spec.py experiments/<exp>/campaigns/<c>.yaml
python3 experiments/common/scripts/campaign_plan.py experiments/<exp>/campaigns/<c>.yaml
python3 -m pytest experiments/common/scripts/test_experiment_config_lint.py -q
python3 experiments/common/scripts/trial_runner.py experiments/<exp>/campaigns/<c>.yaml --limit 1
```

The dry run creates nothing (no bag, no metadata), so it is always safe. Count coverage on the machine that holds the bags, `campaign_plan.py` on the laptop cannot see a rig's trials.

## Decision point and logging
Present the expanded plan, the gate that will run, and the operator/verify steps to the user as one batched confirmation with your recommendation first. Log the campaign's rationale (the claim, the sweep choice, the gate decision) to the driving task note via `lorite-ai-chat-diary` as you go.
