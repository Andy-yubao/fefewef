# Figure source manifest

| Section / slot | Title | Status | Source | Current destination |
|---|---|---|---|---|
| section5 / (5)-fig1 | Single detection-point bearing-error wedge | `direct_use` | `task1/figures/fig1_single_bearing_wedge.*`; `task1/demo/demo_single_wedge.py` | `paper_assets/paper_figures/section5/` and archived originals |
| section5 / (5)-fig2 | Multi-station intersection with local enlargement | `programmatically_generated` | `task1/demo/demo_multi_intersection.py`; `geometry.json`; two independent source panels | final two-panel figure plus source panels in `paper_assets/` |
| section5 / (5)-fig3 | Active target disk clipping | `programmatically_generated` | `task1/demo/demo_circle_clipping.py`; parameterized `geometry.json` | final redraw plus source output in `paper_assets/` |
| section5 / (5)-fig4 | Hexagon counterexample and minimum-covering-circle check | `direct_use` | `task1/figures/fig4_hexagon_counterexample.*`; `task1/demo/demo_hexagon_counterexample.py` | `paper_assets/paper_figures/section5/` and archived originals |
| section6 / (6)-fig1 | First localization region and second-point candidate regions | `deferred` | `task2/results/figures/q2_geometry_candidate_regions.*`; `task2/experiments/make_figures.py` | deferred source registration |
| section7 / (7)-opening-A | Realistic quadruped robot searching for an interference source | `needs_ai_generation` (candidate generated) | built-in image generation; prompt file | `paper_assets/paper_figures/section7/` |
| section7 / (7)-opening-B | Standalone artistic mathematical-model abstraction (right image) | `needs_ai_generation` (candidate generated) | built-in image generation; prompt file | `paper_assets/paper_figures/section7/` |
| section6 / (6)-fig1 | First localization region and second-point candidate regions | `programmatically_generated` | `task2/experiments/make_figures.py`; existing raw data | `paper_assets/paper_figures/section6/` |
| section6 / (6)-fig2 | Second detection points selected by four strategies | `programmatically_generated` | `task2/experiments/make_figures.py`; `selected_points.csv` | `paper_assets/paper_figures/section6/` |
| section6 / (6)-fig3 | Empirical CDF of localization diameter | `programmatically_generated` | `task2/experiments/make_figures.py`; `evaluations.csv` | `paper_assets/paper_figures/section6/` |

All repository paths are relative to the repository root. The supplied PDFs were used to confirm the paper slots and captions; they are not treated as editable source assets.
