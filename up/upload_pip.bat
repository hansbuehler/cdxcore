@echon off
echo ** PIP: to avoid having to provide a PyPI API key, modify $HOME/.pypirc **
REM ** PIP follows https://packaging.python.org/tutorials/packaging-projects/ **

cd C:\Users\hans\OneDrive\Python3\packages\cdxcore
CALL .\up\test.bat

@echo off
if not exist .vcdxcore echo "*** ERROR no ENVIRONMENT ***"
if not exist .vcdxcore exit 2 

if exist dist rmdir /Q /S dist
mkdir dist
call .vcdxcore\Scripts\activate

@echo on
python -m pip install -qq -U pip --no-input
pip install -qq -U twine build --no-input
python up\pip_modify_setup.py 
python -m build
python -m twine upload dist\*

@echo off
rmdir /Q /S dist
REM ** Install from pypi **

@echo on
pip uninstall -qq cdxcore --no-input
pip install --upgrade cdxcore --no-input
@echo off

echo ** GIT upload **

python up\git_message.py >.tmp.txt
set /p MESSAGE=< .tmp.txt
del /q .tmp.txt
REM ==> echo Python test showed %MESSAGE%
@echo on

git commit -a -m "%MESSAGE%"
git push

@echo off
call deactivate

echo ** cdxcore testing, pip, git done **


