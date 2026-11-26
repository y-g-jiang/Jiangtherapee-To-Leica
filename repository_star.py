import http.client
import os
import subprocess
import sys
import threading
from concurrent.futures import Future
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, QUrl
from PySide6.QtWidgets import QPushButton

from release_info import REPOSITORY


REPO_SLUG = REPOSITORY.removeprefix('https://github.com/')
STAR_PATH = '/user/starred/' + REPO_SLUG


def find_tool(name):
    if sys.platform == 'win32':
        suffix = Path('Git', 'cmd') if name == 'git' else Path('GitHub CLI')
        folders = [Path(os.environ[key]) / suffix for key in ('ProgramFiles', 'ProgramW6432') if os.environ.get(key)]
        filename = name + '.exe'
    else:
        folders = [Path('/opt/homebrew/bin'), Path('/usr/local/bin'), Path('/usr/bin')]
        filename = name
    folders.extend(Path(entry.strip('"')) for entry in os.get_exec_path() if entry)
    for folder in folders:
        if folder.is_absolute() and folder != Path.cwd():
            program = folder / filename
            if program.is_file() and os.access(program, os.X_OK):
                return str(program)
    return None


def run_local(command, input_data=None):
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith(('GIT_', 'GCM_TRACE', 'GH_DEBUG'))}
    for key in ('SSH_ASKPASS', 'GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN'):
        env.pop(key, None)
    env.update(GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never', GH_PROMPT_DISABLED='1',
               GH_NO_UPDATE_NOTIFIER='1', GH_TELEMETRY_DISABLED='1')
    try:
        return subprocess.run(command, input=input_data, stdin=subprocess.DEVNULL if input_data is None else None,
                              stdout=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, env=env, cwd=Path.home().anchor, timeout=10,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired):
        return None


def star_api(method, authorization):
    connection = http.client.HTTPSConnection('api.github.com', timeout=6)
    try:
        connection.request(method, STAR_PATH, body=b'' if method == 'PUT' else None,
                           headers={'Authorization': authorization, 'User-Agent': 'Jiangtherapee-To-Leica',
                                    'Accept': 'application/vnd.github+json', 'Cache-Control': 'no-cache'})
        return connection.getresponse().status
    except (OSError, http.client.HTTPException, ValueError):
        return None
    finally:
        connection.close()


def star_with_git(cancelled):
    program = find_tool('git')
    if not program:
        return False
    if sys.platform == 'darwin' and program == '/usr/bin/git':
        tools = run_local(['/usr/bin/xcode-select', '-p'])
        if not tools or tools.returncode:
            return False
    query = f'protocol=https\nhost=github.com\npath={REPO_SLUG}.git\n\n'.encode('ascii')
    command = [program, '-c', 'credential.interactive=never', '-c', 'core.askPass=', 'credential', 'fill']
    result = run_local(command, query)
    if not result or result.returncode or cancelled.is_set():
        return False
    fields = dict(line.split(b'=', 1) for line in result.stdout.splitlines() if b'=' in line)
    token = fields.get(b'password', b'')
    if fields.get(b'protocol') != b'https' or fields.get(b'host') != b'github.com' or not token or not token.isascii():
        return False
    authorization = b'Bearer ' + token
    status = star_api('GET', authorization)
    if status == 204:
        return True
    return status == 404 and not cancelled.is_set() and star_api('PUT', authorization) == 204


def star_with_cli():
    program = find_tool('gh')
    if not program:
        return False
    result = run_local([program, 'api', '--hostname', 'github.com', '--method', 'PUT', '--silent', STAR_PATH])
    return result is not None and result.returncode == 0


class StarButton(QPushButton):
    def __init__(self, action):
        super().__init__('☆ Star')
        self.setAutoDefault(False)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip('用本机已登录的账号给 JTL 加 Star。')
        self.clicked.connect(action.start)


class RepositoryStar(QObject):
    def __init__(self, window, opener):
        super().__init__(window)
        self.opener = opener
        self.cancelled = threading.Event()
        self.completed = False
        self.pending = None
        self.background = False
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.finish)

    @staticmethod
    def attempt(pending, cancelled):
        success = False
        try:
            if not cancelled.is_set():
                success = star_with_git(cancelled)
            if not success and not cancelled.is_set():
                success = star_with_cli()
        finally:
            pending.set_result(success)

    def start(self, background=False):
        if self.cancelled.is_set() or self.pending is not None or self.completed:
            return
        self.background = background
        self.pending = Future()
        threading.Thread(target=self.attempt, args=(self.pending, self.cancelled), daemon=True).start()
        self.timer.start()

    def finish(self):
        if self.pending is None or not self.pending.done():
            return
        self.timer.stop()
        self.completed = self.pending.result()
        self.pending = None
        if not self.completed and not self.background and not self.cancelled.is_set():
            self.opener(QUrl(REPOSITORY))

    def stop(self):
        self.cancelled.set()
        self.timer.stop()
