from distutils.core import setup
import py2exe
import os
import sys

# This is needed to give the app the Windows XP skin rather than the
# dull Windows 2k skin.
manifest = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1"
manifestVersion="1.0">
<assemblyIdentity
    version="0.64.1.0"
    processorArchitecture="x86"
    name="Controls"
    type="win32"
/>
<description>%(prog)s Program</description>
<dependency>
    <dependentAssembly>
        <assemblyIdentity
            type="win32"
            name="Microsoft.Windows.Common-Controls"
            version="6.0.0.0"
            processorArchitecture="X86"
            publicKeyToken="6595b64144ccf1df"
            language="*"
        />
    </dependentAssembly>
</dependency>
</assembly>
"""

# This links provides the best source/example for how to use py2exe that I've found.
# And I looked at a LOT of examples.
# http://www.mail-archive.com/matplotlib-devel@lists.sourceforge.net/msg01745.html

pythonpath = os.path.dirname(sys.executable)

# This is a matplotlib configuration file that can cause the .exe to fail if it is not
# setup right or modified incorrectly. The only change I made from the distribution was
# to change the backend from TkAgg to Agg
data = [('mpl-data', [pythonpath + '\Lib\site-packages\matplotlib\mpl-data\matplotlibrc'])]
data.extend(['README.txt'])
data.extend(['.\dependencies\gdiplus.dll'])
data.extend(['.\dependencies\msvcp71.dll'])
data.extend(['.\dependencies\P4API.pyd'])
# MSCVR71.dll should be copied copied automatically. If it isn't add a statement here to do so.

setup(windows=[{'script':'p4search.py', 
                'icon_resources':[(1,'magnifier.ico')],
                'other_resources': [(24,1,manifest)],
                'includes': [],
                }],
    options = {"py2exe": {
                    #'optimize': 2, # Uncommenting this causes a crash, have not investigated yet.
                    'bundle_files': 1,
                    'compressed': 1, # Seems to drop the size of the entire folder by more than 50%
                    #'packages' : [],
                    #'includes' : [],
                    'excludes': ['Tkinter'], # Don't copy the tcl folder
                    'dll_excludes': ['libgdk-win32-2.0-0.dll',
                        'libgdk_pixbuf-2.0-0.dll',
                        'libgobject-2.0-0.dll']
                    }},
    zipfile = None, # Puts the zip file into the executable (rather than a separate file)
    data_files=data,
)