"""Per-user preferences and Windows login startup registration."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'MicBoost'


def settings_path():
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.config'))
    return base / 'MicBoost' / 'settings.json'


def load_preferences(path=None):
    try:
        data = json.loads((path or settings_path()).read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {}
        gain = data.get('gain_db', 12)
        if not isinstance(gain, (int, float)) or not math.isfinite(gain):
            gain = 12
        result = {
            'gain_db': min(36, max(0, gain)),
            'input': data.get('input') if isinstance(data.get('input'), str) else '',
            'output': data.get('output') if isinstance(data.get('output'), str) else '',
            'auto_start': data.get('auto_start') is True,
        }
        if isinstance(data.get('audio'), dict):
            audio = data['audio']
            threshold = audio.get('gate_db', -55)
            if not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
                threshold = -55
            result['audio'] = {key: audio.get(key) is True for key in ('low_cut', 'noise_gate', 'compressor')}
            result['audio']['gate_db'] = min(-25, max(-70, threshold))
        return result
    except (OSError, ValueError):
        return {}


def save_preferences(data, path=None):
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def device_identity(label):
    # Device numbers can change after a reboot; keep the name and host API.
    return label.split(': ', 1)[-1]


def find_device(labels, identity):
    matches = [label for label in labels if device_identity(label) == identity]
    return matches[0] if len(matches) == 1 else ''


def login_command():
    executable = Path(sys.executable).resolve()
    if getattr(sys, 'frozen', False):
        return subprocess.list2cmdline([str(executable), '--login'])
    windowed = executable.with_name('pythonw.exe')
    if not windowed.is_file():
        raise OSError('pythonw.exeが見つかりません。Setup.batの準備を確認してください。')
    return subprocess.list2cmdline([
        str(windowed), str(Path(__file__).with_name('main.py').resolve()), '--login'
    ])


def register_login(enabled):
    if sys.platform != 'win32':
        raise OSError('Windowsログイン時の自動起動はWindows専用です。')
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, login_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass
