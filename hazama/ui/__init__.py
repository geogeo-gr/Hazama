import sys
import os
import time
import logging
from PySide.QtGui import QApplication, QIcon, QFont, QFontMetrics, QMessageBox
from PySide.QtCore import QLocale, QTranslator, QLibraryInfo, QDateTime, QFile, QByteArray
import hazama.ui.rc
from hazama.config import (settings, appPath, saveSettings, isWin, isWin7OrLater,
                           isWinVistaOrLater, isWin8OrLater)


locale = None
# datetimeFmt may not contain time part (by default)
dateFmt = datetimeFmt = fullDatetimeFmt = None
font = None


def datetimeTrans(s, stripTime=False):
    """Convert datetime in database format to locale one."""
    dt = QDateTime.fromString(s, 'yyyy-MM-dd HH:mm')
    return locale.toString(dt, dateFmt if stripTime else datetimeFmt)


def currentDatetime():
    """Return current datetime in database format."""
    return time.strftime('%Y-%m-%d %H:%M')


def readRcTextFile(path):
    """Read whole text file from qt resources system."""
    assert path.startswith(':/')
    f = QFile(path)
    if not f.open(QFile.ReadOnly | QFile.Text):
        raise FileNotFoundError('failed to read rc text %s' % path)
    text = str(f.readAll())
    f.close()
    return text


def setTranslationLocale():
    global locale
    lang = settings['Main'].get('lang')
    sysLocale = QLocale.system()
    if lang and lang == sysLocale.name():
        locale = sysLocale
    elif lang and lang != sysLocale.name():
        # special case: application language is different from system's
        locale = QLocale(lang)
        QLocale.setDefault(locale)
    else:
        locale = sysLocale
        lang = settings['Main']['lang'] = locale.name()
    langPath = os.path.join(appPath, 'lang')
    logging.info('set translation(%s)', lang)
    global _trans, _transQt  # avoid being collected
    _trans = QTranslator()
    _trans.load(lang, langPath)
    _transQt = QTranslator()
    ret = _transQt.load('qt_' + lang,
                        QLibraryInfo.location(QLibraryInfo.TranslationsPath))
    if not ret:  # frozen
        _transQt.load('qt_' + lang, langPath)
    for i in [_trans, _transQt]: QApplication.instance().installTranslator(i)

    global dateFmt, datetimeFmt, fullDatetimeFmt
    timeFmt = settings['Main'].get('timeFormat')
    dateFmt = settings['Main'].get('dateFormat', locale.dateFormat())
    datetimeFmt = (dateFmt + ' ' + timeFmt) if timeFmt else dateFmt
    # use hh:mm because locale.timeFormat will include seconds
    fullDatetimeFmt = dateFmt + ' ' + (timeFmt or 'hh:mm')


def showErrors(type_, **extra_args):
    """Show variety of error dialogs."""
    app = QApplication.instance()
    if not app:
        app = init()
    {'dbError': lambda hint='': QMessageBox.critical(
        None,
        app.translate('Errors', 'Failed to access database'),
        app.translate('Errors', 'SQLite3: %s.\n\nPlease check database path(have permission?). '
                      'If it\'s corrupt, you may have to recover this file by hand or restore '
                      'from backups.') % hint),
     'dbLocked': lambda: QMessageBox.warning(
         None,
         app.translate('Errors', 'Multiple access error'),
         app.translate('Errors', 'This diary book is already open.')),
     'cantFile': lambda info: QMessageBox.warning(
         None,
         app.translate('Errors', 'Failed to access file'),
         app.translate('Errors', info))
     }[type_](**extra_args)


def setStdEditMenuIcons(menu):
    """Add system theme icons to QLineEdit and QTextEdit context-menu.
    :param menu: QMenu generated by createStandardContextMenu
    """
    (undo, redo, __, cut, copy, paste, delete, __, sel, *__) = menu.actions()
    undo.setIcon(QIcon.fromTheme('edit-undo'))
    redo.setIcon(QIcon.fromTheme('edit-redo'))
    cut.setIcon(QIcon.fromTheme('edit-cut'))
    copy.setIcon(QIcon.fromTheme('edit-copy'))
    paste.setIcon(QIcon.fromTheme('edit-paste'))
    delete.setIcon(QIcon.fromTheme('edit-delete'))
    sel.setIcon(QIcon.fromTheme('edit-select-all'))


def setStyleSheet():
    """If -stylesheet not in sys.argv, append custom.qss(if exists) to default one and
    load it. Otherwise load the one in sys.argv"""
    if '-stylesheet' in sys.argv:
        logging.info('override default StyleSheet by command line arg')
    else:
        ss = [readRcTextFile(':/default.qss')]
        # append theme part
        if settings['Main']['theme'] == 'colorful':
            ss.append(readRcTextFile(':/colorful.qss'))
            scheme = settings['ThemeColorful']['colorScheme']
            if scheme != 'green':
                ss.append(readRcTextFile(':/colorful-%s.qss' % scheme))
        # load custom
        if os.path.isfile('custom.qss'):
            logging.info('set custom StyleSheet')
            with open('custom.qss', encoding='utf-8') as f:
                ss.append(f.read())

        QApplication.instance().setStyleSheet(''.join(ss))


def winDwmExtendWindowFrame(winId, topMargin):
    """Extend background of title bar to toolbar. Only available on Windows
    because it depends on DWM. winId is PyCapsule object, which storing HWND."""
    if not isDwmUsable(): return
    from ctypes import (c_int, byref, pythonapi, c_void_p, c_char_p, py_object,
                        windll, Structure)

    # define prototypes & structures
    class Margin(Structure):
        _fields_ = [('left', c_int), ('right', c_int),
                    ('top', c_int), ('bottom', c_int)]
    pythonapi.PyCapsule_GetPointer.restype = c_void_p
    pythonapi.PyCapsule_GetPointer.argtypes = [py_object, c_char_p]

    winId = pythonapi.PyCapsule_GetPointer(winId, None)
    margin = Margin(0, 0, topMargin, 0)
    windll.dwmapi.DwmExtendFrameIntoClientArea(winId, byref(margin))

    return True


def isDwmUsable():
    """Check whether winDwmExtendWindowFrame usable."""
    if not isWin:
        return False
    if isWin8OrLater:
        # windows 8 or later always have DWM composition enabled, but API used below depends
        # on manifest file (we doesn't have it)
        return True
    elif not isWinVistaOrLater:
        return False
    else:
        from ctypes import byref, windll, c_bool

        b = c_bool()
        ret = windll.dwmapi.DwmIsCompositionEnabled(byref(b))
        return ret == 0 and b.value


def getDpiScaleRatio():
    dpi = QApplication.instance().desktop().logicalDpiX()  # when will x != y happen?
    return dpi / 96


def fixWidgetSizeOnHiDpi(widget):
    """Simply resize current size according to DPI."""
    ratio = getDpiScaleRatio()
    if ratio > 1:
        widget.resize(widget.size() * ratio)
        widget.setMinimumSize(widget.minimumSize() * ratio)  # after resize, prevent over sizing


def saveWidgetGeo(widget):
    settings['Main']['geoDpiRatio'] = str(getDpiScaleRatio())
    return str(widget.saveGeometry().toHex())


def restoreWidgetGeo(widget, geoStr):
    if not geoStr:
        return

    success = widget.restoreGeometry(QByteArray.fromHex(geoStr))
    ratio = getDpiScaleRatio()
    geoRatio = float(settings['Main'].get('geoDpiRatio', ratio))
    if success and abs(ratio - geoRatio) > 0.01:
        widget.resize(widget.size() / geoRatio * ratio)


def makeQIcon(*filenames):
    """A Shortcut to construct a QIcon which has multiple images. Try to add all sizes
    (xx.png & xx-big.png & xx-mega.png) when only one filename supplied."""
    ico = QIcon()
    if len(filenames) == 1:
        fname = filenames[0]
        ico.addFile(fname)
        assert '.' in fname
        b, ext = fname.rsplit('.')
        # they fails silently when file not exist
        ico.addFile(b + '-big.' + ext)
        ico.addFile(b + '-mega.' + ext)
    else:
        for i in filenames:
            ico.addFile(i)
    return ico


class Fonts:
    """Manage all fonts used in application"""
    def __init__(self):
        self.title = QFont()
        self.datetime = QFont()
        self.text = QFont()
        self.default = QApplication.instance().font()
        self.default_m = QFontMetrics(self.default, None)
        self.title_m = self.datetime_m = self.text_m = None

    def load(self):
        # passing None as 2nd arg to QFontMetrics make difference on high DPI
        self.title.fromString(settings['Font'].get('title'))
        self.title_m = QFontMetrics(self.title, None)
        self.datetime.fromString(settings['Font'].get('datetime'))
        self.datetime_m = QFontMetrics(self.datetime, None)
        self.text.fromString(settings['Font'].get('text'))
        self.text_m = QFontMetrics(self.text, None)
        defaultFont = settings['Font'].get('default') or self.getPreferredFont()
        if defaultFont:
            self.default.fromString(defaultFont)
            self.default_m = QFontMetrics(self.default, None)
            QApplication.instance().setFont(self.default)

    @staticmethod
    def getPreferredFont():
        """Return family of preferred font according to language and platform."""
        if isWin and settings['Main']['theme'] == '1px-rect' and getDpiScaleRatio() == 1:
            # old theme looks well with default bitmap fonts only in normal DPI, and
            # text of radio button will be cropped in ConfigDialog
            return None
        if isWin7OrLater:
            return {'zh_CN': 'Microsoft YaHei UI', 'ja_JP': 'Meiryo UI'}.get(locale.name())
        elif isWinVistaOrLater:
            return {'zh_CN': 'Microsoft YaHei', 'ja_JP': 'Meiryo'}.get(locale.name())
        return None


def init():
    app = QApplication(sys.argv)
    app.lastWindowClosed.connect(saveSettings)
    logging.debug('DPI scale ratio %s' % getDpiScaleRatio())

    app.setWindowIcon(makeQIcon(':/appicon-24.png', ':/appicon-48.png', ':/appicon-64.png'))

    setTranslationLocale()
    global font
    font = Fonts()
    font.load()

    setStyleSheet()
    return app
