"""Decision pathway derivation for report-adjacent Phase 3 UX."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from .report_agent import Report, ReportManager

POSITIVE_KEYWORDS = {
    'accelerate', 'acceleration', 'adoption', 'advantage', 'expand', 'expansion', 'growth',
    'improve', 'improvement', 'momentum', 'opportunity', 'outperform', 'support', 'tailwind',
    'upside', 'win', 'strengthen', 'resilient', 'confidence', 'conversion', 'stabilize'
}

NEGATIVE_KEYWORDS = {
    'adverse', 'backlash', 'bear', 'block', 'collapse', 'contraction', 'decline', 'delay',
    'downside', 'drop', 'erosion', 'headwind', 'loss', 'pressure', 'pullback', 'regulatory',
    'risk', 'shock', 'slowdown', 'stress', 'threat', 'volatility', 'watchpoint', 'churn'
}

SIGNAL_STOPWORDS = {
    'the', 'and', 'for', 'with', 'from', 'that', 'this', 'into', 'across', 'under', 'while',
    'where', 'when', 'will', 'would', 'could', 'should', 'have', 'has', 'had', 'more', 'than',
    'over', 'such', 'their', 'there', 'them', 'they', 'about', 'after', 'before', 'through',
    'into', 'between', 'because', 'section', 'report', 'analysis', 'summary', 'finding',
    'findings', 'implication', 'implications', 'scenario', 'scenarios', 'watchpoints',
    'watchpoint'
}

PATHWAY_META = {
    'primary': {
        'id': 'primary-pathway',
        'label': 'Primary Pathway',
        'stance': 'primary',
        'description': 'Most evidence-supported directional path in the current report.'
    },
    'upside': {
        'id': 'upside-case',
        'label': 'Upside Case',
        'stance': 'upside',
        'description': 'Conditions that would compound favorable momentum beyond the base path.'
    },
    'downside': {
        'id': 'downside-case',
        'label': 'Downside Case',
        'stance': 'downside',
        'description': 'Failure path if pressure points, constraints, or adverse responses intensify.'
    }
}


def build_decision_pathways(report: Report) -> Dict[str, Any]:
    section_records = _collect_section_records(report)
    evidence_items = _extract_evidence(section_records)

    buckets = {
        'primary': [],
        'upside': [],
        'downside': [],
    }
    for item in evidence_items:
        buckets[_classify_bucket(item)].append(item)

    ranked = sorted(evidence_items, key=lambda item: item['weight'], reverse=True)
    for bucket_name in ('primary', 'upside', 'downside'):
        if buckets[bucket_name]:
            continue
        for item in ranked:
            if item not in buckets[bucket_name]:
                buckets[bucket_name].append(item)
            if len(buckets[bucket_name]) >= min(2, len(ranked)):
                break

    probabilities = _allocate_probabilities(buckets)
    pathways = []

    for bucket_name in ('primary', 'upside', 'downside'):
        selected = sorted(buckets[bucket_name], key=lambda item: item['weight'], reverse=True)[:4]
        meta = PATHWAY_META[bucket_name]
        pathways.append({
            'id': meta['id'],
            'label': meta['label'],
            'stance': meta['stance'],
            'probability': probabilities[bucket_name],
            'confidence': _confidence_label(selected),
            'summary': _build_summary(bucket_name, selected, report),
            'description': meta['description'],
            'key_signals': _build_key_signals(selected),
            'evidence': [_public_evidence(item) for item in selected],
        })

    ledger = [_public_evidence(item) for item in ranked[:12]]
    title = (report.outline.title if report.outline else None) or report.report_id
    root_question = report.simulation_requirement or (report.outline.summary if report.outline else '') or title

    return {
        'report_id': report.report_id,
        'title': title,
        'root_question': root_question,
        'primary_pathway_id': PATHWAY_META['primary']['id'],
        'methodology': 'Evidence-weighted scenario branches derived from completed report sections. Probabilities are navigation aids for decision review, not calibrated forecast odds.',
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'pathways': pathways,
        'evidence_ledger': ledger,
    }


def _collect_section_records(report: Report) -> List[Dict[str, Any]]:
    generated = ReportManager.get_generated_sections(report.report_id)
    outline_sections = list(report.outline.sections) if report.outline and report.outline.sections else []
    records: List[Dict[str, Any]] = []

    if generated:
        for idx, item in enumerate(generated, start=1):
            outline_title = outline_sections[idx - 1].title if idx - 1 < len(outline_sections) else None
            title, content = _split_section_markdown(item.get('content', ''), outline_title or f'Section {idx}')
            records.append({
                'section_index': item.get('section_index', idx),
                'section_title': title,
                'content': content,
            })
        return records

    for idx, section in enumerate(outline_sections, start=1):
        records.append({
            'section_index': idx,
            'section_title': section.title,
            'content': section.content or '',
        })
    return records


def _split_section_markdown(markdown: str, fallback_title: str) -> Tuple[str, str]:
    lines = (markdown or '').splitlines()
    title = fallback_title
    body_lines: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('## '):
            title = stripped[3:].strip() or fallback_title
            continue
        body_lines.append(line)
    return title, '\n'.join(body_lines).strip()


def _extract_evidence(section_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    for section in section_records:
        candidates = _candidate_snippets(section['content'])
        for snippet in candidates[:5]:
            evidence.append({
                'section_index': section['section_index'],
                'section_title': section['section_title'],
                'snippet': snippet,
                'weight': _snippet_weight(section['section_title'], snippet),
            })
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in sorted(evidence, key=lambda row: row['weight'], reverse=True):
        key = re.sub(r'\s+', ' ', item['snippet']).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _candidate_snippets(content: str) -> List[str]:
    lines = []
    for raw_line in (content or '').splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        stripped = re.sub(r'^#{1,6}\s+', '', stripped)
        stripped = re.sub(r'^[-*+]\s+', '', stripped)
        stripped = re.sub(r'^\d+[.)]\s+', '', stripped)
        stripped = stripped.strip('> ').strip()
        if len(stripped) < 30:
            continue
        lines.append(stripped)

    if len(lines) < 4:
        prose = re.sub(r'[`*_>#-]', ' ', content or '')
        prose = re.sub(r'\s+', ' ', prose).strip()
        sentences = re.split(r'(?<=[.!?])\s+', prose)
        lines.extend(sentence.strip() for sentence in sentences if len(sentence.strip()) >= 30)

    return lines


def _snippet_weight(section_title: str, snippet: str) -> float:
    lowered = snippet.lower()
    title_lower = (section_title or '').lower()
    numeric_hits = len(re.findall(r'\b\d+(?:\.\d+)?%?\b', snippet))
    positive_hits = sum(1 for word in POSITIVE_KEYWORDS if word in lowered or word in title_lower)
    negative_hits = sum(1 for word in NEGATIVE_KEYWORDS if word in lowered or word in title_lower)
    weight = 1.0 + numeric_hits * 0.35 + max(positive_hits, negative_hits) * 0.45
    if 'summary' in title_lower or 'finding' in title_lower:
        weight += 0.35
    if 'watch' in title_lower or 'risk' in title_lower:
        weight += 0.25
    return round(weight, 2)


def _classify_bucket(item: Dict[str, Any]) -> str:
    title = (item.get('section_title') or '').lower()
    snippet = (item.get('snippet') or '').lower()
    positive_hits = sum(1 for word in POSITIVE_KEYWORDS if word in title or word in snippet)
    negative_hits = sum(1 for word in NEGATIVE_KEYWORDS if word in title or word in snippet)

    if negative_hits > positive_hits:
        return 'downside'
    if positive_hits > negative_hits:
        return 'upside'
    if 'watch' in title or 'risk' in title:
        return 'downside'
    if 'implication' in title or 'opportunit' in title or 'recommend' in title:
        return 'upside'
    return 'primary'


def _allocate_probabilities(buckets: Dict[str, List[Dict[str, Any]]]) -> Dict[str, int]:
    raw_scores = {
        'primary': 4.6 + sum(item['weight'] for item in buckets['primary']) * 0.75,
        'upside': 2.2 + sum(item['weight'] for item in buckets['upside']) * 0.9,
        'downside': 2.2 + sum(item['weight'] for item in buckets['downside']) * 0.9,
    }
    total = sum(raw_scores.values()) or 1
    provisional = {key: int(round(value / total * 100)) for key, value in raw_scores.items()}

    for key in provisional:
        provisional[key] = max(15, provisional[key])

    while sum(provisional.values()) > 100:
        reducible = [key for key, value in provisional.items() if value > 15]
        if not reducible:
            break
        target = max(reducible, key=lambda name: provisional[name])
        provisional[target] -= 1

    while sum(provisional.values()) < 100:
        target = max(raw_scores, key=lambda name: raw_scores[name] - provisional[name])
        provisional[target] += 1

    return provisional


def _confidence_label(evidence: List[Dict[str, Any]]) -> str:
    if len(evidence) >= 4:
        return 'high'
    if len(evidence) >= 2:
        return 'medium'
    return 'low'


def _build_summary(bucket_name: str, evidence: List[Dict[str, Any]], report: Report) -> str:
    if not evidence:
        title = (report.outline.title if report.outline else None) or report.report_id
        return f'{PATHWAY_META[bucket_name]["label"]} remains provisional until more report evidence is available for {title}.'

    lead = evidence[0]
    lead_snippet = _trim_snippet(lead['snippet'], 140)
    if bucket_name == 'primary':
        return f"Current evidence points to {lead['section_title']} as the operating base case, anchored by: {lead_snippet}"
    if bucket_name == 'upside':
        return f"Upside opens if favorable signals compound beyond the base path, led by: {lead_snippet}"
    return f"Downside accelerates if pressure points harden, with the clearest warning from {lead['section_title']}: {lead_snippet}"


def _build_key_signals(evidence: List[Dict[str, Any]]) -> List[str]:
    signals: List[str] = []
    for item in evidence:
        snippet = item.get('snippet', '')
        metric_match = re.search(r'\b\d+(?:\.\d+)?%?\b[^.]{0,50}', snippet)
        if metric_match:
            signals.append(_trim_snippet(metric_match.group(0), 80))
            continue

        words = re.findall(r'[A-Za-z][A-Za-z\-/]{3,}', snippet)
        filtered = [word for word in words if word.lower() not in SIGNAL_STOPWORDS]
        if filtered:
            signals.append(' '.join(filtered[:4]))
        else:
            signals.append(_trim_snippet(snippet, 80))

    deduped: List[str] = []
    seen = set()
    for signal in signals:
        key = signal.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(signal)
    return deduped[:4]


def _public_evidence(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'section_index': item['section_index'],
        'section_title': item['section_title'],
        'section_ref': f"S{int(item['section_index']):02d}",
        'snippet': _trim_snippet(item['snippet'], 220),
        'weight': item['weight'],
    }


def _trim_snippet(snippet: str, max_len: int) -> str:
    cleaned = re.sub(r'\s+', ' ', snippet or '').strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + '…'
