SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR
source .venv/bin/activate
pip install -r requirements.txt
python3 git_metrics.py