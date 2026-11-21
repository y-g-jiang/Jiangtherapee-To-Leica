import sqlite3
from datetime import date
from pathlib import Path

from PySide6.QtCore import QObject,QStandardPaths,Qt,QTimer,QUrl,Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkReply,QNetworkRequest
from PySide6.QtWidgets import QApplication,QDialog,QHBoxLayout,QLabel,QPushButton,QVBoxLayout

from release_info import LIMIT,PRODUCT,REPOSITORY,SIGNAL_URL,SUPPORT_URL,VERSION,read_signal,version_tuple


def claim_month(directory,today):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    database=sqlite3.connect(str(directory/'startup.sqlite3'),timeout=.1)
    try:
        with database:
            database.execute('CREATE TABLE IF NOT EXISTS thanks (month TEXT PRIMARY KEY)')
            return database.execute('INSERT OR IGNORE INTO thanks VALUES (?)',(today.strftime('%Y-%m'),)).rowcount==1
    finally:database.close()


class UpdateCheck(QObject):
    checked=Signal(object)

    def __init__(self,parent):
        super().__init__(parent);self.manager=QNetworkAccessManager(self);self.reply=None
        self.manager.setRedirectPolicy(QNetworkRequest.NoLessSafeRedirectPolicy)
        self.deadline=QTimer(self);self.deadline.setSingleShot(True);self.deadline.timeout.connect(self.cancel)

    def start(self):
        if self.reply is not None:return
        request=QNetworkRequest(QUrl(SIGNAL_URL));request.setRawHeader(b'Accept',b'application/octet-stream');request.setRawHeader(b'Cache-Control',b'no-cache');request.setRawHeader(b'User-Agent',b'Jiangtherapee-To-Leica')
        request.setAttribute(QNetworkRequest.CacheLoadControlAttribute,QNetworkRequest.AlwaysNetwork)
        request.setAttribute(QNetworkRequest.CookieLoadControlAttribute,QNetworkRequest.Manual);request.setAttribute(QNetworkRequest.CookieSaveControlAttribute,QNetworkRequest.Manual)
        request.setMaximumRedirectsAllowed(5)
        self.reply=self.manager.get(request);self.reply.setReadBufferSize(LIMIT+1);self.reply.readyRead.connect(self.limit);self.reply.finished.connect(self.finish);self.deadline.start(10000)

    def limit(self):
        if self.reply is not None and self.reply.bytesAvailable()>LIMIT:self.cancel()

    def cancel(self):
        self.deadline.stop()
        if self.reply is not None:self.reply.abort()

    def finish(self):
        reply=self.reply;self.reply=None;self.deadline.stop();version=None
        try:
            if reply.error()==QNetworkReply.NoError and reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)==200 and reply.bytesAvailable()<=LIMIT:
                version=read_signal(bytes(reply.read(LIMIT+1)))
        except (ValueError,KeyError,TypeError,RecursionError):pass
        finally:reply.deleteLater()
        self.checked.emit(version)


class StartupNotices(QObject):
    def __init__(self,window,directory=None,clock=date.today,checker=None,opener=QDesktopServices.openUrl):
        super().__init__(window);self.window=window;self.clock=clock;self.opener=opener
        self.directory=directory if directory is not None else Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation))/'JiangtherapeeToLeica'
        self.checker=checker if checker is not None else UpdateCheck(self);self.checker.checked.connect(self.received)
        self.wake=QTimer(self);self.wake.setSingleShot(True);self.wake.timeout.connect(self.drain)
        self.active=None;self.month_pending=True;self.newer=None;self.started=False;self.stopped=False

    def start(self):
        if self.started or self.stopped:return
        self.started=True;self.wake.start(0);self.checker.start()

    def stop(self):
        self.stopped=True;self.wake.stop();self.checker.cancel()

    def received(self,version):
        if not self.stopped and version and version_tuple(version)>version_tuple(VERSION):
            self.newer=version;self.wake.start(0)

    def drain(self):
        if self.stopped or self.active is not None or not (self.month_pending or self.newer):return
        if not self.window.isVisible() or self.window.isMinimized() or self.window.exporting or self.window.active or QApplication.activeModalWidget():self.wake.start(500);return
        if self.month_pending:
            self.month_pending=False
            try:display=claim_month(self.directory,self.clock())
            except (OSError,sqlite3.Error):display=False
            if display:
                self.present('感谢使用 Jiangtherapee to Leica','感谢你用 JTL 显影照片。\n如果喜欢它，欢迎支持后续开发。','支持作者',SUPPORT_URL,'继续使用');return
        if self.newer:
            version=self.newer;self.newer=None
            self.present(f'发现新版本 V{version}',f'你正在使用 V{VERSION}。可以前往 GitHub 下载新版，也可以继续使用当前版本。','查看新版',f'{REPOSITORY}/releases/tag/v{version}','稍后再说')

    def present(self,title,body,action,url,dismiss):
        dialog=QDialog(self.window);self.active=dialog;dialog.setWindowTitle(PRODUCT);dialog.setWindowModality(Qt.WindowModal);dialog.setMinimumWidth(380)
        layout=QVBoxLayout(dialog);layout.setContentsMargins(24,21,24,19);layout.setSpacing(14)
        heading=QLabel(title);heading.setTextFormat(Qt.PlainText);heading.setObjectName('title');layout.addWidget(heading)
        message=QLabel(body);message.setTextFormat(Qt.PlainText);message.setWordWrap(True);layout.addWidget(message)
        row=QHBoxLayout();row.addStretch();later=QPushButton(dismiss);later.setDefault(True);later.clicked.connect(dialog.reject);row.addWidget(later)
        visit=QPushButton(action);visit.setObjectName('primary');visit.setAutoDefault(False);visit.clicked.connect(lambda:self.visit(dialog,url));row.addWidget(visit);layout.addLayout(row)
        dialog.finished.connect(self.dismissed);dialog.open();later.setFocus()

    def visit(self,dialog,url):
        self.opener(QUrl(url));dialog.accept()

    def dismissed(self):
        dialog=self.active;self.active=None
        if dialog is not None:dialog.deleteLater()
        if not self.stopped:self.wake.start(0)
