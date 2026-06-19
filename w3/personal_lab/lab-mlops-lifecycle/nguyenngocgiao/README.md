# MLOps Lifecycle Pipeline

To run the complete pipeline from start to finish, please follow these steps:

1. **Initialize the stack and generate data** (Run from root folder `lab-mlops-lifecycle`):
   ```bash
   bash data-pack/scripts/start_stack.sh
   uv run python data-pack/data/generate_data.py
   ```
2. **Train the baseline model**: Navigate to the `nguyenngocgiao` directory and run:
   ```bash
   uv run python pipeline.py --data ../data-pack/data/baseline.csv
   ```
3. **Start the FastAPI server**: In a separate terminal, launch the server to expose the `production` model:
   ```bash
   uv run python serve.py
   ```
4. **Trigger drift detection and retraining**: Simulate a production shift by executing the orchestrator:
   ```bash
   uv run python retrain.py --reference ../data-pack/data/baseline.csv --current ../data-pack/data/drifted.csv --serve-url http://localhost:8000 --holdout ../data-pack/data/holdout.csv --post-deploy-eval ../data-pack/data/post_deploy_eval.csv --auto-approve
   ```
   *(This step will automatically detect drift, train v2, validate it against the holdout set, promote it via a blue-green swap, and evaluate 24 post-deploy cycles to test the auto-rollback mechanism).*
