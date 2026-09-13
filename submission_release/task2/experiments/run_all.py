"""One-command reproducible experiment pipeline."""
from experiments.run_benchmark import run
from experiments.analyze_results import main as analyze


if __name__ == "__main__":
    run(base_scenarios=400, replicates=25, seed=20260911)
    analyze()
