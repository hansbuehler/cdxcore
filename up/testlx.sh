cd ./up
cd ..

python -m venv .vcdxcore_linux
source .vcdxcore_linux/bin/activate
python -m pip install -qq -U pip pytest twine build --no-input
pip install -q -U -e . --no-input
flake8 ./cdxcore --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 ./tests --count --select=E9,F63,F7,F82 --show-source --statistics
pytest tests
