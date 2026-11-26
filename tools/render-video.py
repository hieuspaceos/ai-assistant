#!/usr/bin/env python3
"""render-video.py — dựng video hướng dẫn dạng screencast từ scene.json

Cách hoạt động (giải thích cho người không biết code):
  scene.json là "kịch bản phim" — liệt kê từng động tác: mở tab, gõ chữ,
  bấm nút, trợ lý trả lời. Script này:
    1. Đọc giọng nói cho từng câu thoại — ưu tiên VieNeu-TTS local
       (TTS_PY = python của venv đã `pip install vieneu`, TTS_VOICE =
       tên giọng preset), fallback `say` trên macOS / System.Speech
       trên Windows — để biết mỗi cảnh kéo dài bao lâu.
    2. Dùng trình duyệt chạy ngầm chụp ảnh scene-player.html ở từng thời
       điểm — mỗi ảnh là một khung hình của phim.
    3. ffmpeg ghép khung hình + giọng đọc thành video.mp4, kèm phụ đề
       .vtt cùng tên (cue = câu thoại, theo đúng offset timeline).

Chạy:  python3 tools/render-video.py my-course/lesson-XX/scene.json [-o out.mp4]
       TTS_PY=~/.local/share/vieneu-venv/bin/python TTS_VOICE="Trúc Ly" \
         python3 tools/render-video.py <scene.json>
"""
import base64, json, os, platform, re, shutil, socket, struct, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from urllib.parse import quote, urlparse
from urllib.request import urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 12                      # khung hình/giây trong đoạn có chuyển động
W, H = 1280, 720

# ---------- tiện ích ----------

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def sh(cmd_list):
    r = subprocess.run(cmd_list, capture_output=True)
    return r.returncode == 0

def find_browser():
    """Tìm một trình duyệt Chromium có thể chụp ảnh màn hình ngầm."""
    sysname = platform.system()
    if sysname == 'Darwin':
        cands = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
            '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
        ]
    elif sysname == 'Windows':
        pf = [os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)'),
              os.environ.get('ProgramFiles', 'C:/Program Files'),
              os.environ.get('LOCALAPPDATA', '')]
        cands = [os.path.join(p, 'Microsoft/Edge/Application/msedge.exe') for p in pf] + \
                [os.path.join(p, 'Google/Chrome/Application/chrome.exe') for p in pf]
    else:
        cands = ['chromium', 'chromium-browser', 'google-chrome', 'microsoft-edge']
    for c in cands:
        if shutil.which(c) or os.path.exists(c):
            return c
    return None

# ---------- giọng đọc ----------

def tts(text, out_wav, workdir):
    """Sinh file wav đọc `text`. Trả về True nếu được."""
    # ưu tiên VieNeu-TTS local: TTS_PY = python của venv đã `pip install vieneu`
    tts_py = os.environ.get('TTS_PY')
    if tts_py and os.path.exists(tts_py):
        helper = os.path.join(ROOT, 'tools', 'tts-vieneu.py')
        raw = os.path.join(workdir, 'seg-raw.wav')
        if run([tts_py, helper, text, raw]).returncode == 0:
            # vieneu trả 48kHz — chuẩn hoá về 44.1kHz mono cho đồng nhất với say
            return sh(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw,
                       '-ar', '44100', '-ac', '1', out_wav])
    sysname = platform.system()
    if sysname == 'Darwin':
        aiff = os.path.join(workdir, 'seg.aiff')
        r = run(['say', '-v', 'Linh', '-o', aiff, text])
        if r.returncode != 0:          # máy không có giọng Linh → giọng mặc định
            r = run(['say', '-o', aiff, text])
            if r.returncode != 0:
                return False
        return sh(['ffmpeg', '-y', '-loglevel', 'error', '-i', aiff,
                   '-ar', '44100', '-ac', '1', out_wav])
    if sysname == 'Windows':
        ps = ("Add-Type -AssemblyName System.Speech; "
              "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              "$s.SetOutputToWaveFile('{}'); $s.Speak('{}'); $s.Dispose()").format(
                  out_wav.replace("'", "''"), text.replace("'", "''"))
        return run(['powershell', '-NoProfile', '-Command', ps]).returncode == 0
    # linux: thử espeak nếu có
    if shutil.which('espeak'):
        return sh(['espeak', '-v', 'vi', '-w', out_wav, text])
    return False

def wav_dur(path):
    r = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', path])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0

# ---------- timeline ----------

DEFAULTS = {'card': 2.6, 'say': 0, 'move': 0.8, 'click': 1.0, 'flash': 1.4,
            'send': 0.5, 'tab': 0.5, 'work': 1.6, 'files': 0.8, 'bubble': 0.9,
            'type': None, 'pause': 0.4}

def bake(scene, workdir):
    """Gán dur cho mỗi step; sinh audio cho step có 'say'. Trả về (steps, audio)."""
    steps, acc = [], 0.0
    for i, s in enumerate(scene['steps']):
        s = dict(s)
        aud = 0.0
        if s.get('say'):
            w = os.path.join(workdir, f'voice{i:02d}.wav')
            if tts(s['say'], w, workdir):
                aud = wav_dur(w)
                s['_w'] = w
                s['_aud'] = aud
        if 'dur' in s:
            base = float(s['dur'])
        elif s['kind'] == 'type':
            base = len(s['text']) / s.get('cps', 13) + 0.3
        elif s['kind'] == 'bubble':
            base = len(s['text']) * s.get('reveal', 0.045) + 0.5
        else:
            base = DEFAULTS.get(s['kind'], 0.8)
        s['dur'] = max(aud + 0.35 if aud else 0, base)
        s['start'] = acc
        acc += s['dur']
        steps.append(s)
    # offset audio = start của step chứa nó; wav gắn thẳng vào step lúc tts
    # nên một câu tts lỗi không làm câu sau bị phát nhầm thời điểm
    fixed = [(s['start'], s['_w']) for s in steps if '_w' in s]
    return steps, fixed, acc

# ---------- chụp frame ----------

ANIMATED = {'move', 'click', 'type', 'send', 'bubble', 'flash'}

def frame_times(steps, total):
    """Các thời điểm cần chụp: đoạn động chụp dày theo FPS, đoạn tĩnh 1 ảnh."""
    ts = set()
    for s in steps:
        if s['kind'] in ANIMATED:
            t = s['start']
            while t < s['start'] + s['dur']:
                ts.add(round(t, 3)); t += 1 / FPS
        else:
            ts.add(round(s['start'] + min(0.15, s['dur'] * 0.4), 3))
    ts.add(round(total - 0.05, 3))
    return sorted(ts)

def shoot(browser, base_url, t, out):
    url = f"{base_url}{'&' if '?' in base_url else '?'}t={t}"
    for flag in ('--headless=new', '--headless'):
        r = subprocess.run(
            [browser, flag, '--disable-gpu', '--hide-scrollbars', '--mute-audio',
             '--virtual-time-budget=1500',
             '--force-device-scale-factor=1', f'--window-size={W},{H}',
             f'--screenshot={out}', url],
            capture_output=True, timeout=60)
        if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 5000:
            return True
    return False

# ---------- chụp nhanh qua CDP ----------
# Mở trình duyệt một lần, rồi bảo nó "nhảy tới giây t, chụp ảnh" lặp lại
# qua giao thức CDP — thay vì mở trình duyệt mới cho mỗi khung hình.

class WS:
    """Client websocket tối thiểu (đủ dùng cho CDP), không cần thư viện ngoài."""
    def __init__(self, url, timeout=30):
        u = urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n"
               "Upgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        buf = b''
        while b'\r\n\r\n' not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError('websocket handshake thất bại')
            buf += chunk
        if b' 101' not in buf.split(b'\r\n', 1)[0]:
            raise RuntimeError('websocket bị từ chối')

    def _read(self, n):
        buf = b''
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise RuntimeError('websocket đóng đột ngột')
            buf += chunk
        return buf

    def send(self, payload):
        data = payload.encode()
        mask = os.urandom(4)
        n = len(data)
        if n < 126:
            head = struct.pack('!BB', 0x81, 0x80 | n)
        elif n < 65536:
            head = struct.pack('!BBH', 0x81, 0x80 | 126, n)
        else:
            head = struct.pack('!BBQ', 0x81, 0x80 | 127, n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(head + mask + masked)

    def recv(self):
        msg = b''
        while True:
            b1, b2 = self._read(2)
            fin, op = b1 & 0x80, b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack('!H', self._read(2))[0]
            elif n == 127:
                n = struct.unpack('!Q', self._read(8))[0]
            if b2 & 0x80:
                mask = self._read(4)
            payload = self._read(n)
            if b2 & 0x80:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if op == 9:                      # ping → pong (client phải tự mask)
                pm = os.urandom(4)
                pp = bytes(b ^ pm[i % 4] for i, b in enumerate(payload))
                self.sock.sendall(b'\x8a\x80' + pm + pp)
                continue
            msg += payload
            if fin:
                return msg.decode('utf-8', 'replace')

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


class CDP:
    """Điều khiển một trình duyệt Chromium qua DevTools Protocol."""
    def __init__(self, browser, page_url, workdir):
        prof = os.path.join(workdir, 'profile')
        self.proc = subprocess.Popen(
            [browser, '--headless=new', '--disable-gpu', '--mute-audio',
             '--hide-scrollbars', '--force-device-scale-factor=1',
             f'--window-size={W},{H}', '--remote-debugging-port=0',
             f'--user-data-dir={prof}', 'about:blank'],
            stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
        # đọc dòng "DevTools listening on ws://..." từ stderr (qua thread
        # để có timeout — tránh treo nếu trình duyệt không in ra)
        import queue
        q = queue.Queue()
        def _reader():
            for line in self.proc.stderr:
                m = re.search(r'DevTools listening on (ws://\S+)', line)
                if m:
                    q.put(m.group(1)); return
            q.put(None)
        Thread(target=_reader, daemon=True).start()
        try:
            ws_browser = q.get(timeout=20)
        except queue.Empty:
            ws_browser = None
        if not ws_browser:
            raise RuntimeError('không đọc được địa chỉ CDP của trình duyệt')
        port = int(urlparse(ws_browser).port)
        # lấy websocket của tab đầu tiên
        targets = None
        for _ in range(40):
            try:
                targets = json.load(urlopen(
                    f'http://127.0.0.1:{port}/json/list', timeout=2))
                if any(t.get('type') == 'page' for t in targets):
                    break
            except Exception:
                pass
            time.sleep(0.25)
        page = next(t for t in targets if t.get('type') == 'page')
        self.ws = WS(page['webSocketDebuggerUrl'])
        self._id = 0
        self.call('Emulation.setDeviceMetricsOverride', {
            'width': W, 'height': H, 'deviceScaleFactor': 1, 'mobile': False})

    def call(self, method, params=None):
        self._id += 1
        self.ws.send(json.dumps({'id': self._id, 'method': method,
                                 'params': params or {}}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get('id') == self._id:
                if 'error' in r:
                    raise RuntimeError(f"CDP {method}: {r['error']}")
                return r.get('result', {})

    def wait_ready(self, page_url, timeout=20):
        self.call('Page.enable')
        self.call('Page.navigate', {'url': page_url})
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = self.call('Runtime.evaluate', {
                'expression': '!!window.__ready', 'returnByValue': True})
            if r.get('result', {}).get('value'):
                return
            time.sleep(0.15)
        raise RuntimeError('player không sẵn sàng (thiếu __seek?)')

    def seek_shoot(self, t, out):
        self.call('Runtime.evaluate', {
            'expression': f'window.__seek({t})', 'returnByValue': True})
        r = self.call('Page.captureScreenshot', {'format': 'png'})
        with open(out, 'wb') as f:
            f.write(base64.b64decode(r['data']))

    def close(self):
        self.ws.close()
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def cdp_capture(browser, base_url, jobs):
    """Chụp toàn bộ frame bằng một trình duyệt. Trả về list t lỗi (rỗng = ok)."""
    cdp = CDP(browser, base_url, workdir=os.path.dirname(jobs[0][2]) or '.')
    try:
        cdp.wait_ready(base_url)
        fail = []
        for i, t, out in jobs:
            try:
                cdp.seek_shoot(t, out)
                print(f'   frame t={t:6.2f}s ok', end='\r', flush=True)
            except Exception:
                fail.append(t)
        print()
        return fail
    finally:
        cdp.close()

# ---------- main ----------

def main():
    if len(sys.argv) < 2:
        sys.exit('Dùng: render-video.py <đường-dẫn-scene.json> [-o video.mp4]')
    scene_path = os.path.abspath(sys.argv[1])
    out_mp4 = (sys.argv[sys.argv.index('-o') + 1] if '-o' in sys.argv
               else os.path.join(os.path.dirname(scene_path), 'video.mp4'))
    scene = json.load(open(scene_path, encoding='utf-8'))

    browser = find_browser()
    if not browser:
        sys.exit('Không tìm thấy trình duyệt Chrome/Edge/Brave để chụp khung hình.')
    if not shutil.which('ffmpeg'):
        sys.exit('Thiếu ffmpeg.')
    print(f'[1/5] trình duyệt: {os.path.basename(browser)}')

    workdir = tempfile.mkdtemp(prefix='scene-')
    try:
        steps, audio, total = bake(scene, workdir)
        print(f'[2/5] timeline {total:.1f}s, {len(audio)} câu thoại')

        # server tĩnh phục vụ project root (player + scene)
        os.chdir(ROOT)
        baked_json = json.dumps(
            {**scene, 'steps': [{k: v for k, v in s.items() if not k.startswith('_')}
                                for s in steps]},
            ensure_ascii=False)
        # chuỗi "</script>" trong text scene phá thẻ script đang nhúng vào
        baked_json = baked_json.replace('</', '<\\/')
        # nhúng scene thẳng vào HTML — tránh race giữa fetch và lúc chụp
        player_html = open(os.path.join(ROOT, 'tools/scene-player.html'),
                           encoding='utf-8').read()
        inline = '<script>window.SCENE_INLINE = ' + baked_json + ';</script>\n'
        marker = '<script>\nvar SCENE_URL'
        if marker in player_html:
            player_html = player_html.replace(marker, inline + marker)
        elif '</head>' in player_html:
            # marker lạc hậu sau khi sửa scene-player → chèn trước </head>
            player_html = player_html.replace('</head>', inline + '</head>', 1)
        else:
            player_html = inline + player_html
        if 'window.SCENE_INLINE' not in player_html.split('SCENE_URL')[0]:
            print('[!] cảnh báo: không nhúng được scene vào player — kiểm tra lại scene-player.html')
        player_bytes = player_html.encode()
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
            def do_GET(self):
                # chặn dotfile/dot-folder + JSON điều khiển giống serve.py —
                # server này cũng phục vụ project root, chứa .devin/
                # secrets.local.json và các file quyền/cấu hình
                parts = [p for p in urlparse(self.path).path.split('/') if p]
                if any(p.startswith('.') for p in parts):
                    self.send_error(404)
                    return
                low = [p.lower() for p in parts]
                if (len(low) == 2 and low[0] == "my-course" and low[1] in (
                        "permissions.json", "connections.json", "config.json",
                        "bots.json", "bot.md")) or low == ["brain.json"]:
                    self.send_error(404)
                    return
                if self.path.startswith('/player.html'):
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(player_bytes)))
                    self.end_headers()
                    self.wfile.write(player_bytes)
                else:
                    super().do_GET()
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), Quiet)
        Thread(target=httpd.serve_forever, daemon=True).start()
        port = httpd.server_address[1]
        base_url = f'http://127.0.0.1:{port}/player.html'

        times = frame_times(steps, total)
        print(f'[3/5] chụp {len(times)} khung hình…')
        fdir = os.path.join(workdir, 'frames'); os.makedirs(fdir)
        jobs = [(i, t, os.path.join(fdir, f'f{i:04d}.png'))
                for i, t in enumerate(times)]
        fail = None
        try:
            fail = cdp_capture(browser, base_url, jobs)
        except Exception as e:
            print(f'   ! CDP không dùng được ({e}) — chuyển sang chụp từng frame')
        if fail is None:                     # đường dự phòng: mở browser mỗi frame
            fail = []
            with ThreadPoolExecutor(max_workers=4) as ex:
                for ok, i, t in ex.map(
                        lambda j: (shoot(browser, base_url, j[1], j[2]), j[0], j[1]),
                        jobs):
                    if not ok:
                        fail.append(t)
                    else:
                        print(f'   frame t={t:6.2f}s ok', end='\r', flush=True)
            print()
        if fail:
            print(f'   ! {len(fail)} frame lỗi ở t={fail[:5]} — video có thể giật nhẹ')
        httpd.shutdown()

        # concat list với duration từng ảnh
        lst = os.path.join(workdir, 'list.txt')
        with open(lst, 'w') as f:
            f.write('ffconcat version 1.0\n')
            for i in range(len(times)):
                fp = os.path.join(fdir, f'f{i:04d}.png')
                if not os.path.exists(fp):
                    continue
                dur = (times[i + 1] - times[i]) if i + 1 < len(times) else 0.1
                f.write(f"file '{fp}'\nduration {dur:.3f}\n")
            f.write(f"file '{os.path.join(fdir, f'f{len(times)-1:04d}.png')}'\n")

        print('[4/5] ghép khung hình…')
        vtmp = os.path.join(workdir, 'v.mp4')
        r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat',
                            '-safe', '0', '-i', lst, '-vf', 'format=yuv420p',
                            '-c:v', 'libx264', '-crf', '21', '-preset', 'medium',
                            '-movflags', '+faststart', vtmp], capture_output=True)
        if r.returncode != 0:
            sys.exit('ffmpeg ghép video lỗi:\n' + r.stderr.decode()[:800])

        print('[5/5] trộn giọng đọc…')
        if audio:
            cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', vtmp,
                   '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono']
            fc, labels = [], ['[1:a]']
            for k, (off, w) in enumerate(audio):
                cmd += ['-i', w]
                ms = int(off * 1000)
                fc.append(f'[{k + 2}:a]adelay={ms}|{ms}[d{k}]')
                labels.append(f'[d{k}]')
            fc.append(''.join(labels) + f'amix=inputs={len(labels)}:normalize=0[aout]')
            cmd += ['-filter_complex', ';'.join(fc), '-map', '0:v', '-map', '[aout]',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-shortest', out_mp4]
        else:
            cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', vtmp,
                   '-c', 'copy', out_mp4]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            sys.exit('ffmpeg trộn audio lỗi:\n' + r.stderr.decode()[:800])

        print(f'xong → {out_mp4} ({os.path.getsize(out_mp4)//1024} KB)')

        # phụ đề .vtt cùng tên video — cue = câu thoại, theo đúng offset timeline
        cues = [(s['start'], s['start'] + s.get('_aud', s['dur']), s['say'])
                for s in steps if s.get('_w')]
        if cues:
            def ts(t):
                m, s_ = divmod(t, 60)
                return f'{int(m):02d}:{s_:06.3f}'
            vtt = 'WEBVTT\n\n' + '\n\n'.join(
                f'{ts(a)} --> {ts(b)}\n{text}' for a, b, text in cues) + '\n'
            vpath = os.path.splitext(out_mp4)[0] + '.vtt'
            open(vpath, 'w', encoding='utf-8').write(vtt)
            print(f'xong → {vpath} ({len(cues)} cues)')
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

if __name__ == '__main__':
    main()
