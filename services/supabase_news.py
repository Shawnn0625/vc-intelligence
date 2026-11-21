"""通过 Supabase REST / PostgREST 读取 public.ai_news；不硬编码密钥。"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from services.ai_news import load_news_csv, normalize_row

DEFAULT_PAGE_SIZE = 200
DEFAULT_MAX_ROWS = 1000
REQUEST_TIMEOUT = 25

# 标准 Kong 网关路径（n8n / 旧版 JWT key 常用）
REST_TABLE_PATH = '/rest/v1/ai_news'
# 部分 sb_secret_ / sb_publishable_ 密钥会直连 PostgREST 根路径
DIRECT_TABLE_PATH = '/ai_news'


class SupabaseNewsError(RuntimeError):
    """Supabase 配置缺失或请求失败（不含密钥细节）。"""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        api_code: str | None = None,
        api_message: str | None = None,
        api_hint: str | None = None,
        request_path: str | None = None,
        project_host: str | None = None,
        diagnostics: list[str] | None = None,
    ):
        super().__init__(message)
        self.http_status = http_status
        self.api_code = api_code
        self.api_message = api_message
        self.api_hint = api_hint
        self.request_path = request_path
        self.project_host = project_host
        self.diagnostics = diagnostics or []


def _safe_secret_get(name: str) -> str:
    """优先环境变量，其次 st.secrets；绝不把密钥写入日志。"""
    value = (os.getenv(name) or '').strip()
    if value:
        return value
    try:
        import streamlit as st
        secrets = getattr(st, 'secrets', None)
        if secrets is None:
            return ''
        raw = secrets.get(name, '')
        return str(raw or '').strip()
    except Exception:
        return ''


def normalize_project_url(raw_url: str) -> str:
    """SUPABASE_URL 只保留项目基础地址，去掉误粘贴的 /rest/v1 等路径。"""
    text = (raw_url or '').strip().strip('"').strip("'")
    if not text:
        return ''
    # 去掉误写的表路径后缀
    lowered = text.rstrip('/')
    for suffix in (
        '/rest/v1/ai_news',
        '/rest/v1/',
        '/rest/v1',
        '/ai_news',
    ):
        if lowered.lower().endswith(suffix):
            lowered = lowered[: -len(suffix)]
            break
    parsed = urllib.parse.urlparse(lowered)
    if not parsed.scheme or not parsed.netloc:
        return lowered.rstrip('/')
    return f'{parsed.scheme}://{parsed.netloc}'.rstrip('/')


def get_supabase_credentials() -> tuple[str, str]:
    url = normalize_project_url(_safe_secret_get('SUPABASE_URL'))
    key = _safe_secret_get('SUPABASE_KEY')
    return url, key


def supabase_configured() -> bool:
    url, key = get_supabase_credentials()
    return bool(url and key)


def project_host(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc or '未知'
    except Exception:
        return '未知'


def _companies_to_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, list):
        return ', '.join(str(x).strip() for x in value if str(x).strip())
    return str(value)


def row_from_supabase(row: dict) -> dict:
    payload = {
        'news_date': row.get('news_date'),
        'published_at': row.get('published_at'),
        'title': row.get('title'),
        'title_zh': row.get('title_zh'),
        'summary_zh': row.get('summary_zh'),
        'summary_en': row.get('summary_en'),
        'category': row.get('category'),
        'companies': _companies_to_text(row.get('companies')),
        'importance': row.get('importance'),
        'source': row.get('source'),
        'url': row.get('url') or '',
        'demo': False,
    }
    item = normalize_row(payload, demo=False)
    if row.get('id') is not None:
        item['id'] = row.get('id')
    return item


def _scrub_secrets(text: str, api_key: str = '') -> str:
    """从错误文本中移除可能泄露的密钥片段。"""
    cleaned = text or ''
    if api_key:
        cleaned = cleaned.replace(api_key, '[REDACTED]')
    cleaned = re.sub(r'Bearer\s+\S+', 'Bearer [REDACTED]', cleaned, flags=re.I)
    cleaned = re.sub(r'sb_(secret|publishable)_[A-Za-z0-9_-]+', r'sb_\1_[REDACTED]', cleaned)
    cleaned = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[REDACTED_JWT]', cleaned)
    return cleaned[:500]


def _parse_error_body(raw: str, api_key: str = '') -> tuple[str | None, str | None, str | None]:
    raw = (raw or '').strip()
    if not raw:
        return None, None, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None, _scrub_secrets(raw, api_key), None
    if not isinstance(payload, dict):
        return None, _scrub_secrets(raw, api_key), None
    code = payload.get('code')
    message = payload.get('message')
    hint = payload.get('hint')
    return (
        str(code) if code is not None else None,
        _scrub_secrets(str(message), api_key) if message is not None else None,
        _scrub_secrets(str(hint), api_key) if hint is not None else None,
    )


def build_diagnostics(
    *,
    http_status: int | None = None,
    api_code: str | None = None,
    api_message: str | None = None,
    api_hint: str | None = None,
    request_path: str | None = None,
    project_host_name: str | None = None,
    tried_paths: list[str] | None = None,
) -> list[str]:
    lines = [
        '诊断（不含 API Key）：',
        f'· 项目 Host：{project_host_name or "未知"}',
        f'· 表：public.ai_news',
        f'· 请求路径：{request_path or "未知"}',
    ]
    if tried_paths:
        lines.append(f'· 已尝试路径：{", ".join(tried_paths)}')
    if http_status is not None:
        lines.append(f'· HTTP：{http_status}')
    if api_code:
        lines.append(f'· 错误 code：{api_code}')
    if api_message:
        lines.append(f'· 错误 message：{api_message}')
    if api_hint:
        lines.append(f'· 错误 hint：{api_hint}')

    if api_code == 'PGRST205':
        lines.extend([
            '· PGRST205：PostgREST schema cache 中找不到该表。',
            '· 请检查：表是否存在于 public.ai_news；是否已暴露给 Data API；',
            '· 是否与 n8n 写入的为同一 Supabase 项目；必要时在 Dashboard 刷新 schema cache。',
        ])
    elif api_code == 'PGRST125':
        lines.extend([
            '· PGRST125：请求路径对当前网关/密钥无效。',
            '· 标准路径为 /rest/v1/ai_news；部分 sb_secret_ 密钥需使用 /ai_news（PostgREST 根路径）。',
            '· 请确认 SUPABASE_URL 仅为 https://<project-ref>.supabase.co，不要带 /rest/v1。',
        ])
    elif http_status == 404:
        lines.append('· HTTP 404：请核对项目地址、表名暴露情况，以及密钥类型与路径是否匹配。')

    lines.append('· 请确认 SUPABASE_URL 仅含项目基础地址，不要把 Secret Key 写进 URL。')
    return lines


def _candidate_table_paths(api_key: str) -> list[str]:
    """按密钥类型排序候选路径；始终兼容 /rest/v1/ai_news 与直连 /ai_news。"""
    key = (api_key or '').strip()
    if key.startswith('sb_secret_') or key.startswith('sb_publishable_'):
        return [DIRECT_TABLE_PATH, REST_TABLE_PATH]
    return [REST_TABLE_PATH, DIRECT_TABLE_PATH]


def _request_page(
    base_url: str,
    api_key: str,
    table_path: str,
    offset: int,
    limit: int,
) -> list[dict]:
    endpoint = f'{base_url.rstrip("/")}{table_path}'
    query = urllib.parse.urlencode({
        'select': 'id,news_date,published_at,title,title_zh,summary_zh,summary_en,category,companies,importance,source,url,created_at,updated_at',
        'order': 'published_at.desc',
        'limit': str(limit),
        'offset': str(offset),
    })
    req = urllib.request.Request(
        f'{endpoint}?{query}',
        headers={
            'apikey': api_key,
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json',
            'Accept-Profile': 'public',
        },
        method='GET',
    )
    host = project_host(base_url)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            body = resp.read().decode('utf-8')
            status = getattr(resp, 'status', 200)
    except urllib.error.HTTPError as exc:
        raw = ''
        try:
            raw = exc.read().decode('utf-8', errors='replace')
        except Exception:
            raw = ''
        api_code, api_message, api_hint = _parse_error_body(raw, api_key)
        diagnostics = build_diagnostics(
            http_status=exc.code,
            api_code=api_code,
            api_message=api_message,
            api_hint=api_hint,
            request_path=table_path,
            project_host_name=host,
        )
        raise SupabaseNewsError(
            f'Supabase HTTP {exc.code}' + (f' · {api_code}' if api_code else ''),
            http_status=exc.code,
            api_code=api_code,
            api_message=api_message,
            api_hint=api_hint,
            request_path=table_path,
            project_host=host,
            diagnostics=diagnostics,
        ) from None
    except urllib.error.URLError as exc:
        reason = _scrub_secrets(str(getattr(exc, 'reason', exc)), api_key)
        diagnostics = build_diagnostics(
            request_path=table_path,
            project_host_name=host,
            api_message=f'网络错误：{reason}',
        )
        raise SupabaseNewsError(
            f'Supabase 网络错误：{reason}',
            request_path=table_path,
            project_host=host,
            diagnostics=diagnostics,
        ) from None
    except TimeoutError:
        diagnostics = build_diagnostics(
            request_path=table_path,
            project_host_name=host,
            api_message='请求超时',
        )
        raise SupabaseNewsError(
            'Supabase 请求超时',
            request_path=table_path,
            project_host=host,
            diagnostics=diagnostics,
        ) from None

    if status >= 400:
        api_code, api_message, api_hint = _parse_error_body(body, api_key)
        diagnostics = build_diagnostics(
            http_status=status,
            api_code=api_code,
            api_message=api_message,
            api_hint=api_hint,
            request_path=table_path,
            project_host_name=host,
        )
        raise SupabaseNewsError(
            f'Supabase HTTP {status}' + (f' · {api_code}' if api_code else ''),
            http_status=status,
            api_code=api_code,
            api_message=api_message,
            api_hint=api_hint,
            request_path=table_path,
            project_host=host,
            diagnostics=diagnostics,
        )

    try:
        data = json.loads(body) if body else []
    except json.JSONDecodeError:
        diagnostics = build_diagnostics(
            request_path=table_path,
            project_host_name=host,
            api_message='返回了无法解析的 JSON',
        )
        raise SupabaseNewsError(
            'Supabase 返回了无法解析的 JSON',
            request_path=table_path,
            project_host=host,
            diagnostics=diagnostics,
        ) from None

    if not isinstance(data, list):
        diagnostics = build_diagnostics(
            request_path=table_path,
            project_host_name=host,
            api_message='返回格式异常（期望数组）',
        )
        raise SupabaseNewsError(
            'Supabase 返回格式异常（期望数组）',
            request_path=table_path,
            project_host=host,
            diagnostics=diagnostics,
        )
    return data


def _path_worth_retry(exc: SupabaseNewsError) -> bool:
    if exc.api_code in {'PGRST125', 'PGRST205'}:
        return True
    return exc.http_status == 404


def fetch_ai_news(
    url: str,
    api_key: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> list[dict]:
    """分页读取 ai_news，按 published_at 倒序。自动兼容 /rest/v1/ai_news 与 /ai_news。"""
    base_url = normalize_project_url(url)
    if not base_url or not api_key:
        raise SupabaseNewsError('缺少 SUPABASE_URL 或 SUPABASE_KEY')

    page_size = max(1, min(int(page_size), 1000))
    max_rows = max(1, int(max_rows))
    candidates = _candidate_table_paths(api_key)
    table_path = candidates[0]
    first_batch: list[dict] | None = None

    for idx, candidate in enumerate(candidates):
        try:
            first_batch = _request_page(
                base_url, api_key, candidate, offset=0, limit=min(page_size, max_rows),
            )
            table_path = candidate
            break
        except SupabaseNewsError as exc:
            if idx < len(candidates) - 1 and _path_worth_retry(exc):
                continue
            tried = candidates[: idx + 1]
            exc.diagnostics = build_diagnostics(
                http_status=exc.http_status,
                api_code=exc.api_code,
                api_message=exc.api_message,
                api_hint=exc.api_hint,
                request_path=exc.request_path,
                project_host_name=project_host(base_url),
                tried_paths=tried,
            )
            raise exc

    collected: list[dict] = list(first_batch or [])
    # 若首页未满页，说明已取完；否则继续按 offset 分页
    while len(collected) < max_rows and len(first_batch or []) >= min(page_size, max_rows):
        offset = len(collected)
        limit = min(page_size, max_rows - offset)
        batch = _request_page(base_url, api_key, table_path, offset=offset, limit=limit)
        if not batch:
            break
        collected.extend(batch)
        if len(batch) < limit:
            break
        first_batch = batch  # 仅用于判断是否可能还有下一页

    return [row_from_supabase(row) for row in collected]


def format_error_for_ui(exc: BaseException) -> str:
    """生成可在页面展示的安全诊断文本。"""
    if isinstance(exc, SupabaseNewsError):
        parts = [str(exc)]
        if exc.diagnostics:
            parts.append('\n'.join(exc.diagnostics))
        else:
            parts.extend(build_diagnostics(
                http_status=exc.http_status,
                api_code=exc.api_code,
                api_message=exc.api_message,
                api_hint=exc.api_hint,
                request_path=exc.request_path,
                project_host_name=exc.project_host,
            ))
        return _scrub_secrets('\n'.join(parts))
    return _scrub_secrets(f'请求异常：{exc}')


def utc_now_label() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


def load_news_feed(force_csv: bool = False) -> dict:
    """
    优先 Supabase；仅缺少配置或连接失败时回退 CSV。
    云端成功返回空列表时不回退 CSV。
    """
    refreshed_at = utc_now_label()

    if force_csv:
        items, csv_hint = load_news_csv()
        source = 'demo' if csv_hint else 'csv'
        return {
            'items': items,
            'source': source,
            'label': '本地演示数据' if source == 'demo' else '本地 CSV',
            'message': csv_hint or '已强制使用本地 CSV（非云端实时数据）。',
            'diagnostics': None,
            'refreshed_at': refreshed_at,
            'used_fallback': True,
        }

    url, key = get_supabase_credentials()
    if not url or not key:
        items, csv_hint = load_news_csv()
        source = 'demo' if csv_hint else 'csv'
        msg = '未配置 SUPABASE_URL / SUPABASE_KEY，已回退本地数据（非云端实时）。'
        if csv_hint:
            msg = f'{msg} {csv_hint}'
        return {
            'items': items,
            'source': source,
            'label': '本地演示数据' if source == 'demo' else '本地 CSV（回退）',
            'message': msg,
            'diagnostics': None,
            'refreshed_at': refreshed_at,
            'used_fallback': True,
        }

    try:
        items = fetch_ai_news(url, key)
    except SupabaseNewsError as exc:
        items, csv_hint = load_news_csv()
        source = 'demo' if csv_hint else 'csv_fallback'
        msg = f'Supabase 连接失败，已回退本地数据（非云端实时）。原因：{exc}'
        if csv_hint:
            msg = f'{msg} {csv_hint}'
        return {
            'items': items,
            'source': source,
            'label': '本地演示数据' if source == 'demo' else '本地 CSV（回退）',
            'message': msg,
            'diagnostics': format_error_for_ui(exc),
            'refreshed_at': refreshed_at,
            'used_fallback': True,
        }

    return {
        'items': items,
        'source': 'supabase',
        'label': 'Supabase · public.ai_news',
        'message': None,
        'diagnostics': None,
        'refreshed_at': refreshed_at,
        'used_fallback': False,
    }
