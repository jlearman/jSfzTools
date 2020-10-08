rem Batch file to build demo
rem - NOT TESTED

python ..\source\jCutSamps.py -f notes layers\*.wav
mkdir notes
python ..\source\jMap.py sf1 notes\*.wav
