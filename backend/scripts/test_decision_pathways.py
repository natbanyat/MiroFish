"""Smoke tests for report decision pathways derivation."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.api.report import get_decision_pathways
from app.services.report_agent import ReportManager
from app.services.report_decision_pathways import build_decision_pathways


@pytest.fixture()
def report(tmp_path):
    original_reports_dir = ReportManager.REPORTS_DIR
    ReportManager.REPORTS_DIR = str(tmp_path)

    report_id = 'test_pathways_001'
    folder = tmp_path / report_id
    folder.mkdir(parents=True, exist_ok=True)

    outline = {
        'title': 'AI Adoption Pathways',
        'summary': 'Review the base case, upside, and downside branches for enterprise AI adoption.',
        'sections': [
            {
                'title': 'Executive Summary',
                'content': 'Base case remains intact with 18% adoption growth and stronger conversion across core customers.'
            },
            {
                'title': 'Upside Opportunities',
                'content': 'Upside expands if product momentum accelerates, win rates improve, and expansion revenue compounds.'
            },
            {
                'title': 'Risk Watchpoints',
                'content': 'Downside emerges if regulatory pressure rises, churn increases, and enterprise budgets pull back.'
            },
        ],
    }

    meta = {
        'report_id': report_id,
        'simulation_id': 'sim_pathways_001',
        'graph_id': 'graph_pathways_001',
        'simulation_requirement': 'What are the most decision-useful scenario branches?',
        'status': 'completed',
        'outline': outline,
        'markdown_content': '# AI Adoption Pathways\n\n## Executive Summary\n\nBase case remains intact with 18% adoption growth and stronger conversion across core customers.\n\n## Upside Opportunities\n\nUpside expands if product momentum accelerates, win rates improve, and expansion revenue compounds.\n\n## Risk Watchpoints\n\nDownside emerges if regulatory pressure rises, churn increases, and enterprise budgets pull back.\n',
        'created_at': '2026-04-14T00:00:00',
        'completed_at': '2026-04-14T00:05:00',
        'error': None,
        'error_details': None,
    }

    with open(folder / 'meta.json', 'w', encoding='utf-8') as f:
        json.dump(meta, f)

    for idx, section in enumerate(outline['sections'], start=1):
        with open(folder / f'section_{idx:02d}.md', 'w', encoding='utf-8') as f:
            f.write(f"## {section['title']}\n\n{section['content']}\n")

    try:
        yield ReportManager.get_report(report_id)
    finally:
        ReportManager.REPORTS_DIR = original_reports_dir



def test_build_decision_pathways(report):
    pathways = build_decision_pathways(report)

    assert pathways['report_id'] == report.report_id
    assert pathways['primary_pathway_id'] == 'primary-pathway'
    assert len(pathways['pathways']) == 3
    assert sum(item['probability'] for item in pathways['pathways']) == 100
    assert pathways['evidence_ledger'], 'expected non-empty evidence ledger'

    labels = {item['label'] for item in pathways['pathways']}
    assert labels == {'Primary Pathway', 'Upside Case', 'Downside Case'}



def test_decision_pathways_endpoint_importable():
    assert callable(get_decision_pathways)
