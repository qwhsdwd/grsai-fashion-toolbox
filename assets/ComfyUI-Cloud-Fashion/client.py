import base64
import errno
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import shutil
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

if os.name == 'nt':
    import msvcrt
    fcntl = None
else:
    import fcntl
    msvcrt = None


class CloudError(RuntimeError):
    pass


class RequestNotSent(CloudError):
    """The HTTPS connection failed before any API request was sent."""


class ConnectionNotEstablished(OSError):
    pass


class ConnectingHTTPSConnection(http.client.HTTPSConnection):
    def request(self, *args, **kwargs):
        # Connect before HTTPConnection builds/sends the request. Only this
        # phase is safe to retry for a paid POST; never retry request/read.
        original_timeout = self.timeout
        if isinstance(original_timeout, (int, float)):
            self.timeout = min(original_timeout, 15)
        try:
            for attempt in range(3):
                try:
                    self.connect()
                    break
                except OSError as error:
                    self.close()
                    if isinstance(error, ssl.SSLCertVerificationError) or attempt == 2:
                        raise ConnectionNotEstablished(str(error)) from None
                    time.sleep(0.5 * (attempt + 1))
        finally:
            self.timeout = original_timeout
        self.sock.settimeout(original_timeout)
        return super().request(*args, **kwargs)


class ConnectingHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        return self.do_open(ConnectingHTTPSConnection, request, context=self._context)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def read_credentials(config_path=None):
    path = Path(config_path) if config_path is not None else Path(__file__).resolve().parent / 'config.local.json'
    if not path.exists():
        path = Path.home() / '.config/grsai/credentials.json'
    config = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    key = (os.environ.get('GRSAI_API_KEY') or config.get('api_key', '')).strip()
    base = (os.environ.get('GRSAI_BASE_URL') or config.get('base_url', 'https://grsaiapi.com')).rstrip('/')
    if not key:
        raise CloudError('请运行节点目录中的 configure.py 配置自己的 GrsAI Key，或在 config.local.json 填写 api_key。')
    if base not in ('https://grsaiapi.com', 'https://grsai.dakka.com.cn'):
        raise CloudError('base_url 必须使用 GrsAI 文档中的全球节点或国内节点。')
    return base, key


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    temporary.replace(path)


def unwrap(body):
    return body['data'] if isinstance(body.get('data'), dict) else body


def validate_media_url(url):
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname or ''
    if parsed.scheme != 'https' or not hostname or parsed.username or parsed.password:
        raise CloudError('结果链接不是有效的 HTTPS 媒体链接。')
    if hostname == 'localhost' or hostname.endswith(('.local', '.internal')):
        raise CloudError('结果链接不能指向本机或内网。')
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise CloudError('结果链接不能指向内网地址。')


def job_identity(kind, payload, generation=0):
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
        raise CloudError('重新生成批次必须是大于或等于0的整数。')
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    name = f'自动-{fingerprint[:24]}-{generation}'
    digest = hashlib.sha256((kind + ':' + name).encode()).hexdigest()[:24]
    return name, digest, fingerprint


def lock_file(handle):
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    if os.fstat(handle.fileno()).st_size == 0:
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as error:
        if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            raise BlockingIOError('Task is already locked') from None
        raise


class GrsaiClient:
    def __init__(self, state_dir, base=None, key=None, poll_interval=15, wait_seconds=3600):
        self.base, self.key = (base, key) if base and key else read_credentials()
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.poll_interval = poll_interval
        self.wait_seconds = wait_seconds
        self.opener = urllib.request.build_opener(NoRedirect(), ConnectingHTTPSHandler())

    def request(self, path, payload=None):
        headers = {'Authorization': 'Bearer ' + self.key, 'User-Agent': 'ComfyUI-Cloud-Fashion/1.0'}
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode()
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.base + path, data=data, headers=headers)
        try:
            with self.opener.open(request, timeout=90) as response:
                raw = response.read(2 * 1024 * 1024)
        except urllib.error.HTTPError as error:
            detail = error.read(4096).decode('utf-8', errors='replace').replace(self.key, '[REDACTED]')
            try:
                body = json.loads(detail)
                detail = str(body.get('error') or body.get('message') or body.get('code') or '接口拒绝请求')
            except json.JSONDecodeError:
                detail = '接口未返回可解析的错误信息'
            raise CloudError(f'GrsAI HTTP {error.code}: {detail[:400]}') from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            detail = str(error).replace(self.key, '[REDACTED]')
            reason = error.reason if isinstance(error, urllib.error.URLError) else error
            if isinstance(reason, ConnectionNotEstablished):
                raise RequestNotSent(f'GrsAI HTTPS 连接失败，请求尚未发送：{detail[:300]}') from None
            raise CloudError(f'GrsAI 网络请求失败：{detail[:300]}') from None
        try:
            body = json.loads(raw.decode().replace(self.key, '[REDACTED]'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise CloudError('GrsAI 返回了无法解析的响应。') from None
        if not isinstance(body, dict):
            raise CloudError('GrsAI 返回格式错误。')
        return unwrap(body)

    def download(self, url, target):
        validate_media_url(url)
        temporary = target.with_suffix(target.suffix + '.part')
        request = urllib.request.Request(url, headers={'User-Agent': 'ComfyUI-Cloud-Fashion/1.0'})
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as handle, urllib.request.urlopen(request, timeout=120) as response:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 512 * 1024 * 1024:
                    raise CloudError('结果文件超过 512MB，已停止下载；线上任务已保存，可继续取回。')
                handle.write(chunk)
        if not total:
            raise CloudError('接口返回了空媒体文件。')
        temporary.replace(target)

    def migrate_legacy_job(self, kind, fingerprint, record, job_name):
        candidates = []
        for old_record in self.state_dir.glob('*.json'):
            state = json.loads(old_record.read_text(encoding='utf-8'))
            if (state.get('identity_version') != 2 and state.get('kind') == kind
                    and state.get('fingerprint') == fingerprint):
                candidates.append((old_record, state))
        # Prefer a reusable completed task, then a known ID, then an uncertain
        # submission. All of these must be preserved rather than submitted again.
        candidates.sort(key=lambda item: (
            item[1].get('endpoint') != self.base,
            item[1].get('phase') not in ('downloaded', 'succeeded'),
            not bool(item[1].get('id')),
            item[1].get('phase') == 'connection_failed',
        ))
        if not candidates:
            return
        old_record = candidates[0][0]
        fd = os.open(old_record.with_suffix('.lock'), os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(fd, 'r+b') as lock:
            try:
                lock_file(lock)
            except BlockingIOError:
                raise CloudError('相同素材的旧任务正在执行，请等待完成后重试。') from None
            state = json.loads(old_record.read_text(encoding='utf-8'))
            suffix = '.mp4' if kind == 'video' else '.png'
            old_media, new_media = old_record.with_suffix(suffix), record.with_suffix(suffix)
            if old_media.exists() and old_media.stat().st_size:
                temporary = new_media.with_suffix(suffix + '.part')
                shutil.copyfile(old_media, temporary)
                temporary.chmod(0o600)
                temporary.replace(new_media)
            state.update(identity_version=2, generation=0, job_name=job_name,
                         migrated_from=old_record.name)
            if new_media.exists():
                state['file'] = str(new_media)
            save_json(record, state)

    def run(self, kind, job_name, payload, check_interrupt=lambda: None, on_progress=lambda value: None, generation=0):
        # job_name remains accepted for older workflows; identity now comes from
        # the actual request so changing materials never requires a manual name.
        job_name, digest, fingerprint = job_identity(kind, payload, generation)
        record = self.state_dir / (digest + '.json')
        lock_path = self.state_dir / (digest + '.lock')
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(lock_fd, 'r+b') as lock:
            try:
                lock_file(lock)
            except BlockingIOError:
                raise CloudError('相同素材和参数的任务正在执行，请等待当前任务完成。') from None
            if not record.exists() and generation == 0:
                self.migrate_legacy_job(kind, fingerprint, record, job_name)
            state = json.loads(record.read_text(encoding='utf-8')) if record.exists() else None
            if state:
                if state['fingerprint'] != fingerprint:
                    raise CloudError('自动任务记录与当前素材不一致，已停止提交；请检查任务记录。')
                if state['endpoint'] != self.base:
                    raise CloudError('该任务在另一个 GrsAI 节点提交，请使用原节点续查。')
                if not state.get('id') and state.get('phase') != 'connection_failed':
                    raise CloudError(f'任务「{job_name}」上次提交状态未能确认，已阻止重复扣费。请先核对中转站记录；确认需要重新生成时，把节点里的「重新生成批次」加1再运行。')
            if state and state.get('id'):
                body = state['response']
            else:
                check_interrupt()
                state = {'kind': kind, 'job_name': job_name, 'fingerprint': fingerprint,
                         'identity_version': 2, 'generation': generation,
                         'endpoint': self.base, 'phase': 'submitting', 'created_at': time.time(),
                         'model': payload['model'], 'submitted_posts': 1}
                save_json(record, state)
                try:
                    body = self.request('/v1/api/generate', payload)
                except RequestNotSent as error:
                    state.update(phase='connection_failed', submitted_posts=0, error=str(error))
                    save_json(record, state)
                    raise CloudError(str(error) + '\n保持原参数和原任务编号（自动）再运行即可。') from None
                except CloudError as error:
                    state.update(phase='submission_uncertain', error=str(error))
                    save_json(record, state)
                    raise CloudError(str(error) + '\n提交记录已保存，不会自动重新提交。') from None
                state.update(id=body.get('id'), response=body, phase='submitted')
                save_json(record, state)
                if not state['id']:
                    raise CloudError('接口未返回任务 ID，已停止自动重试。请检查中转站任务记录。')
            task_id = state['id']
            deadline = time.monotonic() + self.wait_seconds
            last_progress = None
            while body.get('status') != 'succeeded':
                check_interrupt()
                status = body.get('status')
                if status in ('failed', 'violation', 'cancelled', 'canceled'):
                    detail = str(body.get('error') or '服务端没有给出原因')[:400]
                    raise CloudError(f'线上任务 {task_id} 失败：{detail}。重新生成请把「重新生成批次」加1。')
                if status not in ('running', 'pending', 'queued', 'processing', 'submitted'):
                    raise CloudError(f'线上任务 {task_id} 状态未知：{status}。任务记录已保留。')
                progress = int(body.get('progress', 0))
                if progress != last_progress:
                    on_progress(progress)
                    print(f'[线上工具箱] {kind} {task_id}: {progress}%')
                    last_progress = progress
                if time.monotonic() >= deadline:
                    raise CloudError(f'线上任务 {task_id} 尚未完成。保持相同素材、参数和批次再运行会继续查询，不会重新扣费。')
                until = min(time.monotonic() + self.poll_interval, deadline)
                while time.monotonic() < until:
                    check_interrupt()
                    time.sleep(max(0, min(0.5, until - time.monotonic())))
                body = self.request('/v1/api/result?' + urllib.parse.urlencode({'id': task_id}))
                state.update(response=body, phase=body.get('status'), checked_at=time.time())
                save_json(record, state)
            results = body.get('results') or []
            if not results or not results[0].get('url'):
                raise CloudError(f'线上任务 {task_id} 成功但没有媒体链接；任务记录已保留。')
            suffix = '.mp4' if kind == 'video' else '.png'
            target = self.state_dir / (digest + suffix)
            if not target.exists() or not target.stat().st_size:
                check_interrupt()
                self.download(results[0]['url'], target)
            state.update(phase='downloaded', file=str(target), finished_at=time.time())
            save_json(record, state)
            on_progress(100)
            return target, task_id


def image_payload(prompt, size, images):
    return {'model': 'gpt-image-2.5', 'prompt': prompt, 'aspectRatio': size,
            'quality': 'auto', 'images': images, 'replyType': 'async'}


def video_payload(prompt, resolution, duration, orientation, seed, images):
    if resolution == '1080p' and duration > 10:
        raise CloudError('GrsAI H3 的 1080P 最多支持 10 秒；请缩短时长或选择 768P。')
    return {'model': 'minimax-h3', 'prompt': prompt, 'resolution': resolution,
            'duration': duration, 'aspectRatio': orientation, 'seed': seed,
            'images': images, 'replyType': 'async'}
