import importlib.util
import hashlib
import errno
import os
import io
import json
import http.client
from pathlib import Path
import tempfile
import ssl
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
import urllib.error


ROOT = Path(__file__).resolve().parents[1] / 'assets/ComfyUI-Cloud-Fashion'
spec = importlib.util.spec_from_file_location('cloud_client', ROOT / 'client.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
spec = importlib.util.spec_from_file_location('cloud_prompts', ROOT / 'prompts.py')
prompts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prompts)


class FakeClient(client.GrsaiClient):
    def __init__(self, directory, fail_submit=False, fail_poll=False):
        super().__init__(directory, base='https://grsaiapi.com', key='private-test-key', poll_interval=0)
        self.posts = 0
        self.gets = 0
        self.downloads = 0
        self.fail_submit = fail_submit
        self.fail_poll = fail_poll

    def request(self, path, payload=None):
        if payload is not None:
            self.posts += 1
            if self.fail_submit:
                raise client.CloudError('transport uncertain')
            return {'id': 'own-test-task', 'status': 'running', 'progress': 12}
        self.gets += 1
        if self.fail_poll:
            self.fail_poll = False
            raise client.CloudError('temporary query failure')
        return {'id': 'own-test-task', 'status': 'succeeded', 'results': [{'url': 'https://example.com/result.png'}]}

    def download(self, url, target):
        self.downloads += 1
        target.write_bytes(b'mock-media')


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.api = FakeClient(self.directory.name)
        self.payload = client.image_payload('test', '941x1672', ['reference'])

    def test_repeating_same_job_reuses_result_without_another_paid_post(self):
        first = self.api.run('outfit_image', 'same-job', self.payload)
        second = self.api.run('outfit_image', 'same-job', self.payload)
        self.assertEqual(first, second)
        self.assertEqual((self.api.posts, self.api.downloads), (1, 1))

    def test_changed_material_or_parameter_automatically_creates_a_new_job(self):
        first, _ = self.api.run('outfit_image', 'same-job', self.payload)
        changes = [
            {'images': ['different-person', 'garment']},
            {'images': ['reference', 'bottom', 'pose']},
            {'prompt': 'different instructions'},
            {'aspectRatio': '1024x1024'},
        ]
        paths = {first}
        for change in changes:
            paths.add(self.api.run('outfit_image', 'same-job', {**self.payload, **change})[0])
        self.assertEqual(len(paths), 5)
        self.assertEqual(self.api.posts, 5)
        self.assertEqual(self.api.run('outfit_image', 'same-job', self.payload)[0], first)
        self.assertEqual(self.api.posts, 5)

    def test_automatic_identity_survives_restart_and_ignores_legacy_labels(self):
        first = self.api.run('outfit_image', '人物换装-001', self.payload)
        restarted = FakeClient(self.directory.name)
        second = restarted.run('outfit_image', '自动', dict(reversed(list(self.payload.items()))))
        self.assertEqual(first, second)
        self.assertEqual((restarted.posts, restarted.downloads), (0, 0))

    def test_generation_batch_creates_one_new_job_for_unchanged_materials(self):
        original = self.api.run('outfit_image', '自动', self.payload)[0]
        reroll = self.api.run('outfit_image', '自动', self.payload, generation=1)[0]
        self.assertNotEqual(original, reroll)
        self.assertEqual(self.api.run('outfit_image', '自动', self.payload, generation=1)[0], reroll)
        self.assertEqual(self.api.posts, 2)

    def legacy_record(self, phase='downloaded', task_id='legacy-task'):
        digest = hashlib.sha256('outfit_image:人物换装-001'.encode()).hexdigest()[:24]
        record = Path(self.directory.name) / (digest + '.json')
        state = {'kind': 'outfit_image', 'job_name': '人物换装-001',
                 'fingerprint': hashlib.sha256(json.dumps(self.payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                 'endpoint': self.api.base, 'phase': phase, 'model': self.payload['model']}
        if task_id:
            state.update(id=task_id, response={'id': task_id, 'status': 'succeeded',
                'results': [{'url': 'https://example.com/legacy.png'}]})
            record.with_suffix('.png').write_bytes(b'legacy-media')
        client.save_json(record, state)
        return record

    def test_old_completed_job_is_migrated_without_another_paid_submission(self):
        record = self.legacy_record()
        path, task_id = self.api.run('outfit_image', '自动', self.payload)
        self.assertEqual((path.read_bytes(), task_id), (b'legacy-media', 'legacy-task'))
        self.assertEqual((self.api.posts, self.api.downloads), (0, 0))
        self.assertTrue(record.exists())

    def test_old_uncertain_submission_stays_blocked_after_switching_to_auto(self):
        self.legacy_record(phase='submission_uncertain', task_id=None)
        with self.assertRaisesRegex(client.CloudError, '阻止重复扣费'):
            self.api.run('outfit_image', '自动', self.payload)
        self.assertEqual(self.api.posts, 0)

    def test_old_job_lock_prevents_migration_during_active_submission(self):
        record = self.legacy_record()
        with record.with_suffix('.lock').open('w+b') as lock:
            client.lock_file(lock)
            with self.assertRaisesRegex(client.CloudError, '正在执行'):
                self.api.run('outfit_image', '自动', self.payload)
        self.assertEqual(self.api.posts, 0)

    def test_auto_submission_remains_locked_against_concurrent_identical_runs(self):
        def submit(path, payload=None):
            with self.assertRaisesRegex(client.CloudError, '正在执行'):
                FakeClient(self.directory.name).run('outfit_image', '另一个旧编号', self.payload)
            return {'id': 'own-test-task', 'status': 'succeeded',
                    'results': [{'url': 'https://example.com/result.png'}]}
        with patch.object(self.api, 'request', side_effect=submit) as request:
            self.api.run('outfit_image', '自动', self.payload)
        self.assertEqual(request.call_count, 1)

    def test_same_payload_in_different_workflow_kinds_uses_separate_jobs(self):
        image = self.api.run('text_image', '自动', self.payload)[0]
        outfit = self.api.run('outfit_image', '自动', self.payload)[0]
        self.assertNotEqual(image, outfit)
        self.assertEqual(self.api.posts, 2)

    def test_windows_lock_uses_a_nonblocking_byte_range_from_the_start(self):
        windows = SimpleNamespace(LK_NBLCK=2, locking=Mock())
        with tempfile.TemporaryFile('w+b') as handle:
            with patch.object(client, 'fcntl', None), patch.object(client, 'msvcrt', windows):
                client.lock_file(handle)
            windows.locking.assert_called_once_with(handle.fileno(), 2, 1)
            handle.seek(0)
            self.assertEqual(handle.read(1), b'0')

    def test_windows_busy_lock_becomes_the_same_actionable_error(self):
        windows = SimpleNamespace(LK_NBLCK=2, locking=Mock(side_effect=OSError(errno.EACCES, 'busy')))
        with tempfile.TemporaryFile('w+b') as handle:
            with patch.object(client, 'fcntl', None), patch.object(client, 'msvcrt', windows):
                with self.assertRaises(BlockingIOError):
                    client.lock_file(handle)

    def test_installation_local_api_config_is_loaded_without_home_credentials(self):
        config = Path(self.directory.name) / 'config.local.json'
        client.save_json(config, {'api_key': 'recipient-own-key', 'base_url': 'https://grsai.dakka.com.cn/'})
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(client.read_credentials(config), ('https://grsai.dakka.com.cn', 'recipient-own-key'))

    def test_environment_credentials_override_installation_config(self):
        config = Path(self.directory.name) / 'config.local.json'
        client.save_json(config, {'api_key': 'local-key', 'base_url': 'https://grsaiapi.com'})
        with patch.dict(os.environ, {'GRSAI_API_KEY': 'environment-key', 'GRSAI_BASE_URL': 'https://grsai.dakka.com.cn'}, clear=True):
            self.assertEqual(client.read_credentials(config), ('https://grsai.dakka.com.cn', 'environment-key'))

    def test_query_failure_resumes_existing_id_without_resubmission(self):
        self.api.fail_poll = True
        with self.assertRaises(client.CloudError):
            self.api.run('outfit_image', 'resume-job', self.payload)
        path, task_id = self.api.run('outfit_image', 'resume-job', self.payload)
        self.assertTrue(path.exists())
        self.assertEqual(task_id, 'own-test-task')
        self.assertEqual(self.api.posts, 1)

    def test_uncertain_submit_is_never_automatically_repeated(self):
        self.api.fail_submit = True
        with self.assertRaises(client.CloudError):
            self.api.run('outfit_image', 'uncertain-job', self.payload)
        self.api.fail_submit = False
        with self.assertRaisesRegex(client.CloudError, '阻止重复扣费'):
            self.api.run('outfit_image', 'uncertain-job', self.payload)
        self.assertEqual(self.api.posts, 1)

    def test_connection_failure_can_resume_same_job_because_nothing_was_sent(self):
        with patch.object(self.api, 'request', side_effect=client.RequestNotSent('TLS failed')):
            with self.assertRaisesRegex(client.CloudError, '原任务编号'):
                self.api.run('outfit_image', 'not-sent-job', self.payload)
        state = json.loads(next(Path(self.directory.name).glob('*.json')).read_text())
        self.assertEqual((state['phase'], state['submitted_posts']), ('connection_failed', 0))
        self.assertTrue(self.api.run('outfit_image', 'not-sent-job', self.payload)[0].exists())
        self.assertEqual(self.api.posts, 1)

    def test_tls_eof_is_retried_before_paid_post_is_sent(self):
        connection = client.ConnectingHTTPSConnection('example.com', timeout=90)
        self.addCleanup(connection.close)
        def connect(*args):
            if connect_mock.call_count == 1:
                raise ssl.SSLEOFError('UNEXPECTED_EOF_WHILE_READING')
            connection.sock = Mock()
        with patch.object(http.client.HTTPSConnection, 'connect', side_effect=connect) as connect_mock, \
                patch.object(http.client.HTTPSConnection, 'request') as send_mock, \
                patch.object(client.time, 'sleep'):
            connection.request('POST', '/v1/api/generate', b'paid-request')
        self.assertEqual(connect_mock.call_count, 2)
        send_mock.assert_called_once_with('POST', '/v1/api/generate', b'paid-request')
        self.assertEqual(connection.timeout, 90)

    def test_exhausted_handshakes_never_send_the_paid_request(self):
        connection = client.ConnectingHTTPSConnection('example.com', timeout=90)
        with patch.object(http.client.HTTPSConnection, 'connect', side_effect=ssl.SSLEOFError('EOF')) as connect_mock, \
                patch.object(http.client.HTTPSConnection, 'request') as send_mock, \
                patch.object(client.time, 'sleep'):
            with self.assertRaises(client.ConnectionNotEstablished):
                connection.request('POST', '/v1/api/generate', b'paid-request')
        self.assertEqual(connect_mock.call_count, 3)
        send_mock.assert_not_called()

    def test_certificate_verification_failure_is_not_retried_or_bypassed(self):
        connection = client.ConnectingHTTPSConnection('example.com', timeout=90)
        with patch.object(http.client.HTTPSConnection, 'connect', side_effect=ssl.SSLCertVerificationError('invalid certificate')) as connect_mock, \
                patch.object(http.client.HTTPSConnection, 'request') as send_mock:
            with self.assertRaises(client.ConnectionNotEstablished):
                connection.request('POST', '/v1/api/generate', b'paid-request')
        self.assertEqual(connect_mock.call_count, 1)
        send_mock.assert_not_called()

    def test_failure_after_connection_does_not_replay_paid_post(self):
        connection = client.ConnectingHTTPSConnection('example.com', timeout=90)
        connection.sock = Mock()
        self.addCleanup(connection.close)
        with patch.object(http.client.HTTPSConnection, 'connect') as connect_mock, \
                patch.object(http.client.HTTPSConnection, 'request', side_effect=ssl.SSLEOFError('EOF while sending')) as send_mock:
            with self.assertRaises(ssl.SSLEOFError):
                connection.request('POST', '/v1/api/generate', b'paid-request')
        connect_mock.assert_called_once()
        send_mock.assert_called_once()

    def test_urllib_connection_failure_is_marked_not_sent(self):
        error = urllib.error.URLError(client.ConnectionNotEstablished('TLS EOF'))
        with patch.object(self.api.opener, 'open', side_effect=error):
            with self.assertRaises(client.RequestNotSent):
                client.GrsaiClient.request(self.api, '/v1/api/generate', self.payload)

    def test_different_provider_node_cannot_receive_an_existing_task_id(self):
        self.api.run('outfit_image', 'same-job', self.payload)
        self.api.base = 'https://grsai.dakka.com.cn'
        with self.assertRaisesRegex(client.CloudError, '原节点'):
            self.api.run('outfit_image', 'same-job', self.payload)
        self.assertEqual(self.api.posts, 1)

    def test_job_name_cannot_escape_state_directory(self):
        path, _ = self.api.run('outfit_image', '../../escape', self.payload)
        self.assertEqual(path.parent, Path(self.directory.name))

    def test_api_key_is_redacted_from_provider_errors(self):
        error = urllib.error.HTTPError('https://grsaiapi.com/v1/api/generate', 401, 'Unauthorized', {},
                                       io.BytesIO(b'{"error":"private-test-key is invalid"}'))
        self.addCleanup(error.close)
        with patch.object(self.api.opener, 'open', side_effect=error):
            with self.assertRaises(client.CloudError) as caught:
                client.GrsaiClient.request(self.api, '/v1/api/generate', self.payload)
        self.assertNotIn('private-test-key', str(caught.exception))

    def test_download_does_not_send_authorization_to_media_host(self):
        captured = []
        def open_media(request, **kwargs):
            captured.append(dict(request.header_items()))
            return io.BytesIO(b'result')
        target = Path(self.directory.name) / 'result.png'
        with patch('urllib.request.urlopen', side_effect=open_media):
            client.GrsaiClient.download(self.api, 'https://example.com/media.png', target)
        self.assertFalse(any(k.lower() == 'authorization' for k in captured[0]))

    def test_internal_media_targets_are_rejected(self):
        for url in ['http://example.com/a', 'https://localhost/a', 'https://127.0.0.1/a', 'https://192.168.1.2/a']:
            with self.assertRaises(client.CloudError):
                client.validate_media_url(url)

    def test_h3_1080p_limit_is_checked_before_submission(self):
        with self.assertRaises(client.CloudError):
            client.video_payload('test', '1080p', 11, 'portrait', 1, ['image'])
        self.assertEqual(client.video_payload('test', '1080p', 10, 'portrait', 1, ['image'])['duration'], 10)

    def test_clothing_worn_by_another_person_only_contributes_garments(self):
        text = prompts.outfit_prompt('', True, False, False)
        self.assertIn('不要复制图2穿衣者的脸', text)
        self.assertIn('保持图1人物原本的姿势', text)

    def test_pose_reference_index_tracks_optional_bottom_image(self):
        self.assertIn('图3只提供姿势', prompts.outfit_prompt('', True, False, True))
        self.assertIn('图4只提供姿势', prompts.outfit_prompt('', True, True, True))


if __name__ == '__main__':
    unittest.main()
