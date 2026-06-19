# Evidence-Driven Remediation Engine

This repository contains an autonomous remediation engine designed to evaluate live incident data against historical incidents and automatically execute or recommend remediation actions (or escalate to a human on-call) based on K-Nearest Neighbors, Expected Utility, and Safety Blast-Radius gates.

## Setup

The engine is built using standard Python 3. It has no major external dependencies other than `pyyaml` for parsing the actions configuration.

1. Install Python 3.9+
2. Install the required dependency:
   ```bash
   pip install pyyaml
   ```

## How to Run

### Run a Single Incident
You can evaluate a single incident (e.g., E01) by pointing the engine to the live incident data, the historical corpus, and the actions catalog. The engine will output its decision in JSON format to standard output.

```bash
python engine.py decide --incident eval/E01.json
```

### Run the Evaluation Grader
To automatically run the engine over all 8 evaluation incidents (`E01` to `E08`), save the outputs to `audit.jsonl`, and then grade the results:

**On Windows (PowerShell):**
```powershell
python -c "import subprocess; f = open('audit.jsonl', 'w', encoding='utf-8'); [f.write(subprocess.run(['python', 'engine.py', 'decide', '--incident', f'eval/E0{i}.json'], capture_output=True, text=True).stdout) for i in range(1, 9)]; f.close()"
python grade.py --audit audit.jsonl --expected eval/expected.json
```

**On Linux/macOS (Bash):**
```bash
rm -f audit.jsonl
for i in {1..8}; do
    python engine.py --incident eval/E0$i.json --history incidents_history.json --actions actions.yaml >> audit.jsonl
done
python grade.py --audit audit.jsonl --expected eval/expected.json
```

## Architecture Layers
1. **Layer 1 (features.py)**: Extracts and parses raw logs, trace anomalies, and metric deviations to build a normalized incident representation.
2. **Layer 2 (retrieval.py)**: Uses an outcome-weighted K-Nearest Neighbors algorithm to find the most similar historical incident, boosting successful actions and penalizing failed ones. Includes target mapping for service equivalencies.
3. **Layer 3 (decision.py)**: Calculates the expected utility of the chosen action and checks it against a blast-radius safety gate to determine whether it is safe to auto-act or if it should be escalated (`page_oncall`).
