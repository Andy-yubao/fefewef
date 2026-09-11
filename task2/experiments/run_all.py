"""One-command reproducible experiment pipeline."""
from experiments.run_benchmark import run
from experiments.analyze_results import main as analyze
from experiments.make_figures import main as figures
from experiments.run_studies import main as studies


if __name__ == "__main__":
    run(base_scenarios=400, replicates=25, seed=20260911)
    studies(n_study_scenarios=12, n_convergence_scenarios=6)
    analyze()
    figures()
