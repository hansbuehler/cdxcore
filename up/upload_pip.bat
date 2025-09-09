#@echo off

echo =====================================================================================
echo PIP build
echo To avoid having to provide a PyPI API key, modify $HOME/.pypirc
echo =====================================================================================

REM https://packaging.python.org/tutorials/packaging-projects/
cd C:\Users\hans\OneDrive\Python3\packages\cdxcore
if exist dist rmdir /Q /S dist

REM ** run tests **
if not exist .vcdxcore call python -m venv .vcdxcore
call .vcdxcore\Scripts\activate
call python -m pip install -U pip pytest twine build
call pip uninstall -qq cdxcore
call pip install -e .
call pytest

REM ** create distribution **
mkdir dist
call pip install -q -U twine build
call python up\pip_modify_setup.py 
call python -m build
call python -m twine upload dist\*
rmdir /Q /S dist

REM test pip install
call pip uninstall -q cdxcore
pip install --upgrade cdxcore

echo =====================================================================================
echo GIT upload
echo Uses cdxcore version to set git message
echo =====================================================================================

echo GIT upload
python up\git_message.py >.tmp.txt
set /p MESSAGE=< .tmp.txt
del /q .tmp.txt
REM echo Python test showed %MESSAGE%
git commit -a -m "%MESSAGE%"
git push

call deactivate

echo =====================================================================================
echo cdxcore pip, git done
echo =====================================================================================


