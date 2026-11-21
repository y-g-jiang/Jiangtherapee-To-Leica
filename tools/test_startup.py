import json
import os
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEventLoop,QObject,QTimer,Signal
from PySide6.QtWidgets import QApplication,QLabel,QPushButton,QWidget
import startup_notices as notices
from release_info import LIMIT,REPOSITORY,SUPPORT_URL,VERSION,read_signal,version_tuple,windows_asset

def document(version='1.0.10'):
    return {'schema':1,'product':'JTL','channel':'stable','release':{'version':version,'package':{'size':1024,'sha256':'a'*64,'url':f'{REPOSITORY}/releases/download/v{version}/{windows_asset(version)}'}}}

class Checker(QObject):
    checked=Signal(object)
    def __init__(self):super().__init__();self.calls=0
    def start(self):self.calls+=1
    def cancel(self):pass

class StartupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_signal(self):
        for version in ('0.1.0',VERSION,'1.0.10','2.0.0'):self.assertEqual(read_signal(json.dumps(document(version)).encode()),version)
        self.assertLess(version_tuple(VERSION),version_tuple('1.0.10'));self.assertIsNone(read_signal(b'{"schema":1,"channel":"stable","product":"JTL","release":null}'))
        for root,key,value in (('','schema',True),('','product','JSR'),('','channel','beta'),('release','version','1.0.3-rc1'),('release','version','1.0.03'),('package','url','https://other.invalid/new'),('package','sha256','?'),('package','size',True)):
            item=document();target=item if not root else item['release'] if root=='release' else item['release']['package'];target[key]=value
            with self.assertRaises(ValueError):read_signal(json.dumps(item).encode())

    def test_concurrent_month_claim(self):
        with tempfile.TemporaryDirectory() as directory,ThreadPoolExecutor(4) as pool:
            self.assertEqual(sum(pool.map(lambda _:notices.claim_month(directory,date(2026,12,1)),range(8))),1)
            self.assertTrue(notices.claim_month(directory,date(2027,1,1)));self.assertFalse(notices.claim_month(directory,date(2026,12,31)))

    def test_startup_sequence(self):
        with tempfile.TemporaryDirectory() as directory:
            visits=[];window=QWidget();window.exporting=False;window.active=None;window.show();today=[date(2026,11,30)]
            def launch():
                check=Checker();ui=notices.StartupNotices(window,directory,lambda:today[0],check,lambda url:visits.append(url.toString()));ui.start();ui.start();self.assertEqual(check.calls,1);return ui,check
            def click(ui,name):next(button for button in ui.active.findChildren(QPushButton) if button.text()==name).click();self.app.processEvents()
            ui,check=launch();window.exporting=True;check.checked.emit('1.0.10');ui.drain();self.assertIsNone(ui.active);window.exporting=False;ui.drain();self.assertTrue(any('感谢' in s.text() for s in ui.active.findChildren(QLabel)));click(ui,'继续使用');ui.drain();click(ui,'查看新版');ui.stop()
            ui,check=launch();check.checked.emit('1.0.1');ui.drain();self.assertIsNone(ui.active);check.checked.emit(VERSION);ui.drain();self.assertIsNone(ui.active);ui.stop()
            today[0]=date(2026,12,1);ui,check=launch();ui.drain();click(ui,'支持作者');ui.stop();self.assertEqual(visits,[REPOSITORY+'/releases/tag/v1.0.10',SUPPORT_URL]);window.close()

    def test_async_network(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                redirects={'/latest':'/tag','/tag':'/ok','/loop':'/loop'}
                if self.path in redirects:
                    self.send_response(302);self.send_header('Location',redirects[self.path]);self.end_headers();return
                if self.path=='/stall':time.sleep(.3)
                self.send_response(503 if self.path=='/down' else 200);self.end_headers()
                payload=b'x'*(LIMIT+1) if self.path=='/oversize' else b'{' if self.path=='/invalid' else json.dumps(document()).encode()
                try:self.wfile.write(payload)
                except OSError:pass
        with ThreadingHTTPServer(('127.0.0.1',0),Handler) as server:
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                for endpoint,expected in [('ok','1.0.10'),('latest','1.0.10'),('loop',None),('down',None),('invalid',None),('oversize',None),('stall',None)]:
                    loop=QEventLoop();result=[];check=notices.UpdateCheck(None);check.checked.connect(lambda v:(result.append(v),loop.quit()));failsafe=QTimer();failsafe.setSingleShot(True);failsafe.timeout.connect(loop.quit);failsafe.start(2500)
                    with patch.object(notices,'SIGNAL_URL',f'http://127.0.0.1:{server.server_port}/{endpoint}'):
                        check.start()
                        if endpoint=='stall':check.deadline.start(30)
                        loop.exec()
                    failsafe.stop();self.assertEqual(result,[expected])
            finally:server.shutdown()

if __name__=='__main__':unittest.main()
