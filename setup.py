#!/usr/bin/env python3
import sys
import os
from os import path
from glob import glob
from distutils.core import Command
from distutils.errors import DistutilsExecError
from distutils.spawn import find_executable, spawn
sys.path.append(path.realpath('hazama/'))
from hazama import __version__


class build_qt(Command):
    description = 'build Qt files(.ts .ui .rc)'
    user_options = [('ts', 't', 'compile ts files only'),
                    ('ui', 'u', 'compile ui files only'),
                    ('rc', 'r', 'compile rc files only')]

    def initialize_options(self):
        self.ts, self.ui, self.rc = (0,) * 3

    def finalize_options(self): pass

    def run(self):
        methods = [self.compile_ts, self.compile_ui, self.compile_rc]
        for opt, m in zip([self.ts, self.ui, self.rc], methods):
            if opt:
                m()
                break
        else:
            for i in methods: i()

    @staticmethod
    def compile_ui():
        for i in glob(path.join('hazama', 'ui', '*.ui')):
            spawn(['pyside-uic', '-o', i.split('.')[0]+'_ui.py', '-x', i])
        # fix importing error in generated files
        # resource will be imported in ui.__init__
        for i in glob(path.join('hazama', 'ui', '*_ui.py')):
            with open(i, 'r', encoding='utf-8') as f:
                text = [l for l in f if not l.startswith('import res_rc')]
            with open(i, 'w', encoding='utf-8') as f:
                f.write(''.join(text))

    @staticmethod
    def compile_rc():
        spawn(['pyside-rcc', '-py3', path.join('res', 'res.qrc'), '-o',
               path.join('hazama', 'ui', 'rc.py')])

    @staticmethod
    def compile_ts():
        lang_dir = path.join('hazama', 'lang')
        if not path.isdir(lang_dir): os.mkdir(lang_dir)

        lres = find_executable('lrelease') or find_executable('lrelease-qt4')
        if lres is None:
            raise DistutilsExecError('lrelease not found')

        for i in glob(path.join('i18n', '*.ts')):
            qm_filename = path.basename(i).split('.')[0] + '.qm'
            spawn([lres, i, '-qm', path.join(lang_dir, qm_filename)])


class update_ts(Command):
    description = 'Update translation files'
    user_options = []

    def initialize_options(self): pass

    def finalize_options(self): pass

    def run(self):
        spawn(['pyside-lupdate', path.join('i18n', 'lupdateguide')])


if sys.platform == 'win32':
    from cx_Freeze import setup, Executable
    import PySide

    pyside_dir = path.dirname(PySide.__file__)
    os.environ['PATH'] += ';' + pyside_dir  # for executing qt tools

    # prepare translation files
    ts = list(glob('hazama/lang/*.qm'))  # application's translations
    ts += [path.join(pyside_dir, 'translations', 'qt_%s')
           % path.basename(i) for i in ts]  # corresponding Qt translations
    all_ts = [(i, '../lang/%s' % path.basename(i)) for i in ts]
    main = Executable('hazama/hazama.py',
                      base='Win32GUI',
                      icon='res/appicon/appicon.ico',
                      appendScriptToLibrary=False,
                      appendScriptToExe=True,
                      targetDir='build')
    extra_opts = dict(
        options={'build_exe': {
            'include_files': all_ts,
            'includes': ['PySide.QtCore', 'PySide.QtGui'],
            'excludes': ['tkinter', 'PySide.QtNetwork', 'distutils'],
            'build_exe': 'build/lib',  # dir for exe and dependent files
            'init_script': path.join(os.getcwd(), 'utils', 'cx_freeze_init.py')}},
        executables=[main])
else:
    from distutils.core import setup
    extra_opts = {}


setup(name='Hazama',
      author='krrr',
      url='https://github.com/krrr/Hazama',
      version=__version__,
      description='A simple cross-platform diary program',
      requires=['PySide'],
      cmdclass={'build_qt': build_qt, 'update_ts': update_ts},
      **extra_opts)
