
echo =====================================================================================
echo PIP build
echo To avoid having to provide a PyPI API key, modify $HOME/.pypirc
echo =====================================================================================

REM https://packaging.python.org/tutorials/packaging-projects/
cd C:\Users\hans\OneDrive\Python3\packages\cdxcore

CALL .\up\test.bat

REM: always exists because of 'test' 
REM: call python -m venv .vcdxcore
if not exist .vcdxcore echo "*** ERROR no ENVIRONMENT ***"
if not exist .vcdxcore exit 2 

if exist dist rmdir /Q /S dist
mkdir dist
call .vcdxcore\Scripts\activate
python -m -y pip install -U pip twine build

REM ** create distribution **
pip install -q -U twine build
python up\pip_modify_setup.py 
python -m build
python -m twine upload dist\*
rmdir /Q /S dist

REM test pip install
pip --no-input uninstall -q cdxcore
pip -y install --upgrade cdxcore

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


