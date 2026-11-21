"""从本地 CSV 读取 AI 新闻；不编造字段，缺失显示为未知。"""
from __future__ import annotations

import csv
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / 'data' / 'ai_news_database.csv'

# 临时「早期机会」启发式（CSV 无 Sourcing 评分，明确标注非正式评分）
MEGA_COMPANIES = {
    'anthropic', 'openai', 'google', 'alphabet', 'apple', 'nvidia', 'meta',
    'microsoft', 'amazon', 'tesla', 'samsung', 'ibm', 'oracle', 'intel',
    'amd', 'broadcom', 'salesforce', 'adobe', 'palantir', 'crowdstrike',
    'palo alto networks', 'john deere', 'foxconn', 'yahoo', 'reuters',
}

EARLY_OPPORTUNITY_RULES = [
    '临时规则（非 Sourcing 评分）：事件类型为 Funding 或 Product',
    '临时规则（非 Sourcing 评分）：重要性 ≤ 3（若重要性未知则跳过本条）',
    '临时规则（非 Sourcing 评分）：至少有一家非大型科技/AI 巨头公司；无公司名时仍保留为候选',
]

FALLBACK_SAMPLES = [
    {
        'news_date': '2026-11-21',
        'published_at': '2026-11-21T00:00:00.000Z',
        'title': 'Demo: Agent tooling update (placeholder)',
        'title_zh': '示例：Agent 开发工具更新观察',
        'summary_zh': '演示条目：正式接入 n8n CSV 后，此处显示真实来源、摘要与事件类型。',
        'summary_en': 'Demo item only. Replace with real n8n CSV export.',
        'category': 'Product',
        'companies': '',
        'importance': 3,
        'source': 'DEMO',
        'url': '',
        'demo': True,
    },
    {
        'news_date': '2026-11-21',
        'published_at': '2026-11-21T00:00:00.000Z',
        'title': 'Demo: Model capability and cost signal',
        'title_zh': '示例：模型能力与成本变化',
        'summary_zh': '演示条目：跟踪模型发布、基准表现与推理成本。金额与估值须核实来源。',
        'summary_en': 'Demo item only. Do not treat as market fact.',
        'category': 'Research',
        'companies': '',
        'importance': 4,
        'source': 'DEMO',
        'url': '',
        'demo': True,
    },
    {
        'news_date': '2026-11-21',
        'published_at': '2026-11-21T00:00:00.000Z',
        'title': 'Demo: Early-stage AI funding tracker',
        'title_zh': '示例：早期 AI 创业公司融资追踪',
        'summary_zh': '演示条目：真实融资金额、投资方与轮次必须核实来源，未知请标为未知。',
        'summary_en': 'Demo funding placeholder. No fabricated round size.',
        'category': 'Funding',
        'companies': '示例初创',
        'importance': 2,
        'source': 'DEMO',
        'url': '',
        'demo': True,
    },
    {
        'news_date': '2026-11-21',
        'published_at': '2026-11-21T00:00:00.000Z',
        'title': 'Demo: AI infra market signal',
        'title_zh': '示例：AI Infra 市场信号',
        'summary_zh': '演示条目：供应链、模型部署与数据基础设施动态。',
        'summary_en': 'Demo industry placeholder.',
        'category': 'Industry',
        'companies': '',
        'importance': 3,
        'source': 'DEMO',
        'url': '',
        'demo': True,
    },
    {
        'news_date': '2026-11-21',
        'published_at': '2026-11-21T00:00:00.000Z',
        'title': 'Demo: Policy watch placeholder',
        'title_zh': '示例：政策与监管观察',
        'summary_zh': '演示条目：政策类资讯用于重点关注视图演示。',
        'summary_en': 'Demo policy placeholder.',
        'category': 'Policy',
        'companies': '',
        'importance': 4,
        'source': 'DEMO',
        'url': '',
        'demo': True,
    },
]


def _unknown(value: str | None) -> str:
    text = (value or '').strip()
    return text if text else '未知'


def _parse_importance(raw: str | None):
    text = (raw or '').strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_companies(raw: str | None) -> list[str]:
    text = (raw or '').strip()
    if not text:
        return []
    parts = []
    for chunk in text.replace('，', ',').split(','):
        name = chunk.strip()
        if name and name not in parts:
            parts.append(name)
    return parts


def normalize_row(row: dict, demo: bool = False) -> dict:
    companies = _parse_companies(row.get('companies') or row.get('company'))
    importance = _parse_importance(str(row.get('importance', '')) if row.get('importance') is not None else '')
    if importance is None and isinstance(row.get('importance'), int):
        importance = row['importance']
    return {
        'news_date': _unknown(row.get('news_date')),
        'published_at': _unknown(row.get('published_at')),
        'title': _unknown(row.get('title')),
        'title_zh': _unknown(row.get('title_zh') or row.get('title')),
        'summary_zh': _unknown(row.get('summary_zh') or row.get('summary')),
        'summary_en': _unknown(row.get('summary_en')),
        'category': _unknown(row.get('category')),
        'companies': companies,
        'companies_raw': _unknown(', '.join(companies) if companies else ''),
        'importance': importance,
        'source': _unknown(row.get('source')),
        'url': (row.get('url') or '').strip(),
        'demo': bool(demo or row.get('demo')),
    }


def load_news_csv(path: Path | None = None) -> tuple[list[dict], str | None]:
    """返回 (新闻列表, 提示信息)。CSV 不存在时回退示例数据。"""
    csv_path = path or CSV_PATH
    if not csv_path.exists():
        items = [normalize_row(x, demo=True) for x in FALLBACK_SAMPLES]
        return items, f'未找到 {csv_path.name}，已载入本地示例数据（演示，非真实新闻）。'
    items = []
    with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not any((v or '').strip() for v in row.values()):
                continue
            items.append(normalize_row(row, demo=False))
    items.sort(key=lambda x: x.get('published_at') or '', reverse=True)
    return items, None


def is_mega_company(name: str) -> bool:
    key = name.strip().lower()
    if key in MEGA_COMPANIES:
        return True
    return any(mega in key or key in mega for mega in MEGA_COMPANIES)


def match_early_opportunity(item: dict) -> bool:
    category = (item.get('category') or '').strip()
    if category not in {'Funding', 'Product'}:
        return False
    importance = item.get('importance')
    if importance is None or importance > 3:
        return False
    companies = item.get('companies') or []
    if not companies:
        return True
    return any(not is_mega_company(c) for c in companies)


def match_focus(item: dict) -> bool:
    importance = item.get('importance')
    if importance is not None and importance >= 4:
        return True
    return (item.get('category') or '') in {'Policy', 'Funding'} and (importance or 0) >= 3


def match_industry(item: dict) -> bool:
    return (item.get('category') or '') in {'Industry', 'Policy', 'Research'}


VIEW_FILTERS = {
    '重点关注': match_focus,
    '早期机会': match_early_opportunity,
    '行业动态': match_industry,
}


def filter_news(
    items: list[dict],
    view: str = '重点关注',
    keyword: str = '',
    category: str = '全部',
    importance_min: str = '全部',
) -> list[dict]:
    matcher = VIEW_FILTERS.get(view, match_focus)
    result = [x for x in items if matcher(x)]

    kw = (keyword or '').strip().lower()
    if kw:
        result = [
            x for x in result
            if kw in (x.get('title_zh') or '').lower()
            or kw in (x.get('title') or '').lower()
            or kw in (x.get('summary_zh') or '').lower()
            or kw in (x.get('summary_en') or '').lower()
            or kw in (x.get('companies_raw') or '').lower()
            or kw in (x.get('source') or '').lower()
            or kw in (x.get('category') or '').lower()
        ]

    if category and category != '全部':
        result = [x for x in result if x.get('category') == category]

    if importance_min and importance_min != '全部':
        try:
            threshold = int(importance_min)
            result = [
                x for x in result
                if x.get('importance') is not None and x['importance'] >= threshold
            ]
        except ValueError:
            pass

    return result


def list_categories(items: list[dict]) -> list[str]:
    cats = sorted({x.get('category') for x in items if x.get('category') and x.get('category') != '未知'})
    return ['全部'] + cats


def format_published(value: str) -> str:
    text = (value or '').strip()
    if not text or text == '未知':
        return '未知'
    if 'T' in text:
        return text.replace('T', ' ').replace('Z', ' UTC')
    return text


def importance_label(value) -> str:
    if value is None:
        return '未知'
    return str(value)
