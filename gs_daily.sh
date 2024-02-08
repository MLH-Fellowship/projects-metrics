SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR
echo -n "$GC_SA" | base64 -d > gs_credentials.json
source .venv/bin/activate
pip install -r requirements.txt
python3 git_metrics.py