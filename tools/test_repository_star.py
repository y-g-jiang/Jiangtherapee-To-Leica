import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import call,patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QObject,Qt,Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QWidget
import repository_star as star
from release_info import REPOSITORY
from startup_notices import StartupNotices


class NoUpdate(QObject):
    checked=Signal(object)
    def start(self):pass
    def cancel(self):pass


class StarTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.window=QWidget();self.window.exporting=False;self.window.active=None;self.window.show();self.links=[]
        self.today=date(2026,11,26);self.ui=StartupNotices(self.window,self.temp.name,lambda:self.today,NoUpdate(),lambda url:self.links.append(url.toString()) or True)
        self.action=self.ui.stars;self.toolbar=star.StarButton(self.action)

    def tearDown(self):
        self.ui.stop();self.toolbar.close();self.window.close();self.window.deleteLater();self.temp.cleanup();self.app.processEvents()

    def wait(self,condition):
        deadline=time.monotonic()+5
        while not condition() and time.monotonic()<deadline:
            self.app.processEvents();time.sleep(.005)
        self.assertTrue(condition())

    def welcome(self):
        self.ui.start();self.ui.drain();self.app.processEvents();self.assertIsNotNone(self.ui.active)
        return self.ui.active.findChild(star.StarButton)

    def test_first_use_shared_success(self):
        with patch.object(star,'star_with_git',return_value=True) as git, patch.object(star,'star_with_cli') as cli:
            welcome=self.welcome();git.assert_not_called();cli.assert_not_called()
            welcome.click();self.toolbar.click();self.wait(lambda:self.action.completed)
            self.toolbar.click();git.assert_called_once();cli.assert_not_called()
            self.assertEqual(self.links,[])
            for button in (welcome,self.toolbar):
                self.assertEqual(button.text(),'☆ Star');self.assertTrue(button.isEnabled())

    def test_fallback_to_cli_or_browser_and_later_month(self):
        trail=[]
        def git(cancel):trail.append('git');return False
        def cli():trail.append('gh');return len(trail)>2
        with patch.object(star,'star_with_git',side_effect=git),patch.object(star,'star_with_cli',side_effect=cli):
            welcome=self.welcome();welcome.click();self.wait(lambda:bool(self.links));self.assertEqual(self.links,[REPOSITORY]);self.assertEqual(trail,['git','gh'])
            self.assertIs(self.app.activeModalWidget(),self.ui.active)
            self.ui.active.reject();self.toolbar.click();self.wait(lambda:self.action.completed);self.assertEqual(trail,['git','gh','git','gh']);self.assertEqual(self.links,[REPOSITORY])
            self.today=date(2026,12,1);self.ui.month_pending=True;self.ui.drain();self.assertIsNone(self.ui.active.findChild(star.StarButton))

    def test_enter_skips_star(self):
        with patch.object(star,'find_tool') as command:
            self.welcome();self.assertEqual(self.ui.active.focusWidget().text(),'继续使用');QTest.keyClick(self.ui.active,Qt.Key_Return);self.wait(lambda:self.ui.active is None);command.assert_not_called()

    def test_close_cancels_fallback(self):
        with patch.object(star,'star_with_git',side_effect=lambda event:event.wait(2) and False),patch.object(star,'star_with_cli') as cli:
            self.toolbar.click();pending=self.action.pending;self.ui.stop();pending.result(timeout=3);self.action.finish()
            cli.assert_not_called();self.assertEqual(self.links,[])

    def test_background_start(self):
        with patch.object(star,'star_with_git',return_value=False) as git,patch.object(star,'star_with_cli',return_value=False) as cli:
            self.action.start(background=True);self.wait(lambda:self.action.pending is None)
            self.assertFalse(self.action.completed);git.assert_called_once();cli.assert_called_once();self.assertEqual(self.links,[])
            self.toolbar.click();self.wait(lambda:bool(self.links));self.assertEqual(self.links,[REPOSITORY])
            self.assertEqual(git.call_count,2);self.assertEqual(cli.call_count,2)

    def test_git_scoped_check_and_add(self):
        data=b'protocol=https\nhost=github.com\nusername=example\npassword=test-fixture\n'
        for responses,expected in (([204],True),([404,204],True),([404,403],False),([401],False),([None],False)):
            with self.subTest(responses=responses),patch.object(star,'find_tool',return_value='git'),patch.object(star,'run_local',return_value=subprocess.CompletedProcess([],0,data)) as helper,patch.object(star,'star_api',side_effect=responses) as api:
                self.assertEqual(star.star_with_git(threading.Event()),expected)
                self.assertEqual(helper.call_args.args[1],b'protocol=https\nhost=github.com\npath=y-g-jiang/Jiangtherapee-To-Leica.git\n\n');self.assertEqual(helper.call_args.args[0][-2:],['credential','fill'])
                methods=['GET','PUT'] if responses[0]==404 else ['GET'];self.assertEqual(api.call_args_list,[call(method,b'Bearer test-fixture') for method in methods])

    def test_missing_and_mismatched_credentials(self):
        for result in (None,subprocess.CompletedProcess([],1,b''),subprocess.CompletedProcess([],0,b'protocol=https\nhost=other.test\npassword=test-fixture\n')):
            with patch.object(star,'find_tool',return_value='git'),patch.object(star,'run_local',return_value=result),patch.object(star,'star_api') as api:
                self.assertFalse(star.star_with_git(threading.Event()));api.assert_not_called()

    def test_star_destination_and_silent_cli(self):
        with patch.object(star.http.client,'HTTPSConnection') as https:
            connection=https.return_value;connection.getresponse.return_value.status=204
            self.assertEqual(star.star_api('PUT',b'Bearer test-fixture'),204)
            self.assertEqual(https.call_args.args,('api.github.com',));self.assertEqual(connection.request.call_args.args,('PUT','/user/starred/y-g-jiang/Jiangtherapee-To-Leica'));connection.close.assert_called_once()
        with patch.object(star,'find_tool',return_value='gh'),patch.object(star,'run_local',return_value=subprocess.CompletedProcess([],0)) as run:
            self.assertTrue(star.star_with_cli());run.assert_called_once_with(['gh','api','--hostname','github.com','--method','PUT','--silent',star.STAR_PATH])
