"""Endpoint-level checks for section regeneration state handling."""

import json
import os
import sys

import pytest
from flask import Flask

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.api import report_bp
from app.api import report as report_api
from app.models.task import TaskManager, TaskStatus
from app.services.report_agent import ReportGenerationError, ReportManager


class ImmediateThread:
    def __init__(self, target=None, daemon=None, args=None, kwargs=None):
        self._target = target
        self._args = args or ()
        self._kwargs = kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


class DummyAgentSuccess:
    def __init__(self, *args, **kwargs):
        pass

    def regenerate_section(self, report_id, section_index, progress_callback=None):
        if progress_callback:
            progress_callback('regenerating', 60, 'regenerating section')
        ReportManager.save_section(
            report_id,
            section_index,
            ReportManager.load_outline(report_id).sections[section_index - 1],
        )
        return 'ok'


class DummyAgentFailure:
    def __init__(self, *args, **kwargs):
        pass

    def regenerate_section(self, report_id, section_index, progress_callback=None):
        raise ReportGenerationError(
            'LLM timed out',
            error_type='llm_timeout',
            retryable=True,
            stage='regenerating',
        )


@pytest.fixture()
def client(tmp_path, monkeypatch):
    original_reports_dir = ReportManager.REPORTS_DIR
    ReportManager.REPORTS_DIR = str(tmp_path)
    monkeypatch.setattr(report_api.threading, 'Thread', ImmediateThread)
    monkeypatch.setattr(report_api.LLMClient, 'from_boost_config', staticmethod(lambda: object()))

    app = Flask(__name__)
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    app.register_blueprint(report_bp, url_prefix='/api/report')

    try:
        yield app.test_client()
    finally:
        ReportManager.REPORTS_DIR = original_reports_dir
        TaskManager()._tasks.clear()



def _write_report(tmp_root, report_id='report_regen_endpoint'):
    folder = tmp_root / report_id
    folder.mkdir(parents=True, exist_ok=True)

    outline = {
        'title': 'Endpoint Regen Report',
        'summary': 'Report summary',
        'sections': [
            {'title': 'Section One', 'content': ''},
            {'title': 'Section Two', 'content': ''},
            {'title': 'Section Three', 'content': ''},
        ],
    }
    meta = {
        'report_id': report_id,
        'simulation_id': 'sim_endpoint_001',
        'graph_id': 'graph_endpoint_001',
        'simulation_requirement': 'Validate regen endpoint state handling',
        'status': 'completed',
        'outline': outline,
        'markdown_content': '# Endpoint Regen Report\n',
        'created_at': '2026-04-14T00:00:00',
        'completed_at': '2026-04-14T00:05:00',
        'error': None,
        'error_details': None,
    }
    progress = {
        'status': 'completed',
        'progress': 100,
        'message': 'Done',
        'current_section': None,
        'completed_sections': ['Section One'],
        'updated_at': '2026-04-14T00:05:00',
    }

    with open(folder / 'meta.json', 'w', encoding='utf-8') as f:
        json.dump(meta, f)
    with open(folder / 'outline.json', 'w', encoding='utf-8') as f:
        json.dump(outline, f)
    with open(folder / 'progress.json', 'w', encoding='utf-8') as f:
        json.dump(progress, f)
    with open(folder / 'section_01.md', 'w', encoding='utf-8') as f:
        f.write('## Section One\n\nExisting content.\n')

    return report_id



def test_regenerate_section_marks_task_failed_when_report_still_incomplete(client, tmp_path, monkeypatch):
    report_id = _write_report(tmp_path)
    monkeypatch.setattr(report_api, 'ReportAgent', DummyAgentSuccess)

    response = client.post(f'/api/report/{report_id}/regenerate-section', json={'section_index': 2})
    payload = response.get_json()

    assert response.status_code == 200
    task_id = payload['data']['task_id']
    task = TaskManager().get_task(task_id)
    assert task is not None
    assert task.status == TaskStatus.FAILED
    assert 'missing sections' in (task.error or '')



def test_regenerate_section_persists_structured_failure_on_report(client, tmp_path, monkeypatch):
    report_id = _write_report(tmp_path)
    monkeypatch.setattr(report_api, 'ReportAgent', DummyAgentFailure)

    response = client.post(f'/api/report/{report_id}/regenerate-section', json={'section_index': 2})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload['success'] is True

    report = ReportManager.get_report(report_id)
    progress = ReportManager.get_progress(report_id)
    task = TaskManager().get_task(payload['data']['task_id'])

    assert report.status.value == 'failed'
    assert report.error_details is not None
    assert report.error_details['error_type'] == 'llm_timeout'
    assert report.error_details['retryable'] is True
    assert progress['status'] == 'failed'
    assert task.status == TaskStatus.FAILED

    status_response = client.get('/api/report/generate/status', query_string={'report_id': report_id})
    status_payload = status_response.get_json()

    assert status_response.status_code == 200
    assert status_payload['data']['status'] == 'failed'
    assert status_payload['data']['retryable'] is True
    assert status_payload['data']['error_type'] == 'llm_timeout'
