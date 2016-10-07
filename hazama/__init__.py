# Copyright (C) 2016 krrr <guogaishiwo@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
__version__ = '1.0.1'
__desc__ = 'A simple cross-platform diary application'
__author__ = 'krrr'


# ---- Project Coding Guide ----
# 1. Don't use lambda as slot, it may cause segfault (obj destroyed but signal not disconnected).
# 2. Class definition order: __init__, Qt's methods, methods, slots

# ---- Notes ----


def main_entry():
    import time
    start_time = time.clock()
    import logging
    import sys
    from hazama import config

    config.changeCWD()
    config.init()

    level = logging.DEBUG if config.settings['Main'].getboolean('debug') else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=level)
    logging.info('Hazama v%s  (%s, Py%d.%d.%d)', __version__, sys.platform, *sys.version_info[:3])
    logging.info('Diary book path: ' + config.db.path)

    from hazama import ui, diarybook, updater
    from hazama import updater
    app = ui.init()
    from hazama.ui.mainwindow import MainWindow

    w = MainWindow()
    w.show()
    logging.debug('startup took %.2f sec', time.clock()-start_time)

    if config.settings['Main'].getboolean('backup'):
        try:
            diarybook.backup()
        except OSError as e:
            from hazama.ui import showErrors
            showErrors('cantFile', str(e))  # message not correct here, ignore it...

    if config.settings['Update'].getboolean('needClean'):
        updater.cleanBackup()
        config.settings['Update']['needClean'] = str(False)

    ret = app.exec_()
    del w  # force close all child window of MainWindow

    diarybook.DiaryBook.instance.disconnect()
    config.saveSettings()

    # segfault might happen if not wait for them
    for i in [updater.checkUpdateTask, updater.installUpdateTask]:
        if i is not None:
            logging.debug('waiting for %s to exit', i)
            i.wait()
    return ret
