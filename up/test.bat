@echo off
echo *** Prepare ***
@if not exist up (
    echo ERROR: required directory "up" does not exist. Call this from the package root directory 1>&2
    exit /b 1
)

if not exist .vcdxcore call python -m venv .vcdxcore
call .vcdxcore\Scripts\activate

REM ** pip install **

@echo on
python -m pip install -qq -U pip pytest twine build --no-input
@echo off

REM ** cdxcore local install **
:: pip uninstall -qq cdxcore --no-input creates a wired error message
@echo on
pip install -q U -e . --no-input
@echo off

REM ** Flake and test **
@echo on
flake8 .\cdxcore --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 .\tests --count --select=E9,F63,F7,F82 --show-source --statistics
pytest
@echo off

call deactivate

