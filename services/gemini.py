import os

SYSTEM = '''你是一名审慎的科技 VC 研究伙伴，服务初级投资分析师。对事实和推断严格区分，
不编造融资额、估值、收入、客户数量。尽量引用公开来源和日期；未知内容写「待核实」。
重点帮助用户培养自主判断：解释逻辑、列反证和后续尽调问题。用清晰的中文 Markdown 回复。'''


def ask(prompt, api_key='', model='gemini-flash-latest', use_search=True):
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError('请先安装 requirements.txt 中的 google-genai') from exc
    key = api_key or os.getenv('GEMINI_API_KEY', '')
    if not key:
        raise RuntimeError('未配置 GEMINI_API_KEY，请在 .env/环境变量或侧边设置中填写')
    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(system_instruction=SYSTEM,
        tools=[types.Tool(google_search=types.GoogleSearch())] if use_search else None)
    response = client.models.generate_content(model=model, contents=prompt, config=config)
    content = response.text or '模型未返回正文，请调整输入后重试。'
    links = []
    for candidate in response.candidates or []:
        grounding = getattr(candidate, 'grounding_metadata', None)
        for chunk in getattr(grounding, 'grounding_chunks', None) or []:
            web = getattr(chunk, 'web', None)
            if web and getattr(web, 'uri', None):
                entry = {'title': getattr(web, 'title', None) or '网页来源', 'url': web.uri}
                if entry not in links:
                    links.append(entry)
    return content, links
