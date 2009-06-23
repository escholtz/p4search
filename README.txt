Perforce Changelist Search (aka p4search)

Dependencies
1. Python 2.5
2. wxPython 2.8
3. p4python25
4. matplotlib-0.98.5.2
5. numpy-1.2.1
6. py2exe-0.6.9

Install
1. Installers for all of the dependencies listed above can be found in the dependencies
folder. Once you get those setup, you should hopefully be able to run p4search.py
2. In order to build an executable, run the command: python setup.py py2exe
(Note that you need to use python 2.5, so if you have multiple versions of
python installed, you can run: c:\python25\python.exe setup.py py2exe)