import json
import os
from datetime import date
from pathlib import Path
import streamlit as st
from services import db
from services.gemini import ask
from data.sample import SAMPLES, CATEGORIES

st.set_page_config(page_title='VC Intelligence · Research Companion', page_icon='🧠', layout='wide', initial_sidebar_state='collapsed')

css_path = Path(__file__).parent / 'assets' / 'style.css'
st.markdown('<style>'+css_path.read_text(encoding='utf-8')+'</style>', unsafe_allow_html=True)
db.initialize()

for k, v in {'tab':'AI News', 'category':None, 'active_company':'', 'prompt':'', 'report':'', 'sources':[], 'chat':[]}.items():
    if k not in st.session_state:
        st.session_state[k] = v

with st.sidebar:
    st.markdown('### ⚙️ Gemini 设置')
    api_key = st.text_input('Gemini API Key', value=os.getenv('GEMINI_API_KEY',''), type='password', help='仅在当前运行环境使用；不要公开分享 API Key')
    model = st.text_input('模型 ID', value=os.getenv('GEMINI_MODEL','gemini-flash-latest'))
    use_search = st.checkbox('Google Search 联网检索', value=True)
    st.caption('请使用你已有的 Gemini API 配置；联网检索是否可用依模型及额度而定。')
    st.markdown('---')
    st.markdown('**新闻数据**')
    if st.button('载入 5 条演示新闻', use_container_width=True):
        if not db.list_news():
            for item in SAMPLES:
                db.save_news(item, demo=True)
            st.rerun()
        else:
            st.info('数据库已有数据，为防止重复，未载入演示项。')
    uploaded = st.file_uploader('导入 n8n 输出 JSON（可选）', type=['json'])
    if uploaded is not None and st.button('导入新闻 JSON', use_container_width=True):
        try:
            contents = json.load(uploaded)
            items = contents if isinstance(contents, list) else contents.get('items', [contents])
            for item in items:
                db.save_news(item)
            st.success(f'已导入 {len(items)} 条')
            st.rerun()
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            st.error(f'数据格式错误：{exc}')

# Header
left, right = st.columns([8, 2], vertical_alignment='center')
with left:
    st.markdown('<div class="brand"><div class="brand-icon">♧</div><div><div class="brand-name">VC Intelligence</div><div class="brand-sub">Personal Investment Research OS</div></div></div>', unsafe_allow_html=True)
with right:
    st.markdown('<div class="prototype">产品原型 · V2</div>', unsafe_allow_html=True)

# Four tabs implemented with buttons; unlike st.tabs this allows navigation programmatically
nav = st.columns(4, gap='medium')
for i, name in enumerate(['AI News', '公司研究', '产业链', '可比公司']):
    with nav[i]:
        kind = 'primary' if st.session_state.tab == name else 'secondary'
        if st.button(name, key=f'nav_{i}', type=kind, use_container_width=True):
            st.session_state.tab = name
            if name != 'AI News': st.session_state.category = None
            st.rerun()

st.markdown('<div class="content-divider"></div>', unsafe_allow_html=True)

def section_heading(heading, trail=''):
    a, b = st.columns([7,3], vertical_alignment='center')
    with a: st.markdown(f'<div class="section-heading">{heading}</div>', unsafe_allow_html=True)
    with b: st.markdown(f'<div class="section-trail">{trail}</div>', unsafe_allow_html=True)


def company_prompt(company, focus):
    past = db.research_history(company)[:2]
    context = '\n\n'.join(p['report'][:2500] for p in past)
    return f'''请对公司「{company}」进行 VC 初步投研，重点「{focus}」。
请按以下标题组织：公司定位/产品，客户和需求，产业链位置，商业模式及单位经济性，竞争对手及差异化，关键投资假设，支持证据与反证，风险，5 个尽调问题，待核实事项。
如果数据库里有历史研究，请明确指出结论是否变化、哪些信息需要更新。
【历史研究摘录，可能过时，仅作内部参考】\n{context or '无'}'''


def run_ai(prompt):
    try:
        with st.spinner('Gemini 正在研究并核实公开资料…'):
            return ask(prompt, api_key=api_key, model=model, use_search=use_search)
    except Exception as e:
        st.error(f'调用失败：{e}')
        return None, []


def show_sources(sources):
    if sources:
        with st.expander('联网检索来源（请人工核对）'):
            for x in sources:
                st.markdown(f"- [{x['title']}]({x['url']})")

if st.session_state.tab == 'AI News':
    if st.session_state.category:
        section_heading(st.session_state.category, '已入库条目 · 非实时新闻源')
        if st.button('← 返回资讯总览'):
            st.session_state.category = None
            st.rerun()
        news = db.list_news(st.session_state.category)
        if not news:
            st.info('暂无数据。可通过左侧导入 n8n JSON，或先载入演示新闻。')
        for n in news:
            with st.container(border=True):
                st.markdown(f"**{n['title']}**" + ('  ·  `演示`' if n['demo'] else ''))
                st.caption(' · '.join(s for s in [n['source'], n['published_at'], n['company']] if s))
                st.write(n['summary'])
                if n['url']: st.link_button('查看来源 ↗', n['url'])
                if n['company'] and st.button(f"研究 {n['company']}", key=f"research_news_{n['id']}"):
                    st.session_state.active_company = n['company']
                    st.session_state.tab = '公司研究'
                    st.rerun()
    else:
        section_heading('Daily AI Intelligence', f'{date.today().isoformat()} · 本地资料库')
        s = db.stats()
        a,b,c = st.columns(3)
        for col, count, name in [(a,s['total'],'已收录资讯'),(b,s['noteworthy'],'值得关注'),(c,s['projects'],'项目动态')]:
            with col:
                st.markdown(f'<div class="stat-number">{count}</div><div class="stat-label">{name}</div>', unsafe_allow_html=True)
        if not s['total']:
            st.caption('当前无新闻数据。左侧可导入 n8n JSON 或载入 5 条明确标记的演示样例。')
        elif s['demos']:
            st.caption(f'当前含 {s["demos"]} 条演示数据；以上为整个本地数据库统计，不代表今日实时新闻。')
        st.markdown('<div class="category-top"></div>', unsafe_allow_html=True)
        for index,(name,desc) in enumerate(CATEGORIES):
            a,b = st.columns([12,1],vertical_alignment='center')
            with a:
                st.markdown(f'<div class="cat-title">▤ &nbsp; {name}</div><div class="cat-sub">&emsp;&emsp; {desc}</div>', unsafe_allow_html=True)
            with b:
                if st.button('›',key=f'category_{index}', help=f'浏览{name}'):
                    st.session_state.category = name
                    st.rerun()
            if index < len(CATEGORIES)-1:
                st.markdown('<div class="cat-gap"></div>', unsafe_allow_html=True)

elif st.session_state.tab == '公司研究':
    section_heading('公司研究', 'Company Research · Gemini')
    company = st.text_input('公司名称', value=st.session_state.active_company, placeholder='如：Cursor、Sierra、Harvey')
    focus = st.selectbox('研究重点', ['综合投资分析','技术与竞争壁垒','商业模式与单位经济性','市场格局与投资风险'])
    if st.button('开始 / 更新研究', type='primary'):
        if not company.strip(): st.warning('请输入公司名称')
        else:
            st.session_state.active_company = company.strip()
            result, links = run_ai(company_prompt(company.strip(), focus))
            if result:
                db.save_research(company.strip(), focus, result, links)
                st.session_state.report, st.session_state.sources = result, links
                st.rerun()
    company = company.strip()
    if company:
        history = db.research_history(company)
        if history:
            st.markdown('#### 研究历史')
            for idx, rec in enumerate(history[:8]):
                with st.expander(f"{rec['created_at']} · {rec['focus']}", expanded=(idx==0)):
                    st.markdown(rec['report'])
                    show_sources(json.loads(rec['sources_json']))
                    st.download_button('下载 Markdown', rec['report'], file_name=f'{company}_research_{rec["id"]}.md',key=f'download_{rec["id"]}')
        else: st.info('还没有该公司的研究记录，开始研究后会自动保存到 SQLite。')
        st.markdown('#### 研究笔记')
        note = st.text_area('记录你的判断、反证或尽调问题', placeholder='哪些假设值得继续验证？', key='research_note')
        if st.button('保存笔记') and note.strip():
            db.save_note(company, note.strip())
            st.success('已存入本地研究笔记')
            st.rerun()
        for n in db.list_notes(company)[:6]:
            st.caption(n['created_at'])
            st.write(n['note'])

elif st.session_state.tab == '产业链':
    section_heading('产业链', 'Industry Ecosystem · 研究辅助')
    sector = st.selectbox('选择赛道', ['AI Infra','AI Agents','Robotics','太空算力'])
    stage_maps = {
      'AI Infra': [('上游', '芯片、算力硬件、数据中心'),('中游','云平台、模型部署、数据与开发工具'),('下游','AI 应用、企业客户、开发者')],
      'AI Agents': [('基础层','基模、推理、工具调用协议'),('编排层','Agent Runtime、评估、安全与记忆'),('应用层','行业工作流、企业部署与终端用户')],
      'Robotics': [('基础层','传感器、执行器、芯片'),('系统层','机器人本体、控制与具身模型'),('应用层','制造、物流、服务与其他部署场景')],
      '太空算力': [('产业上游','核心器件、通信与算力载荷'),('整星环节','卫星总体设计、分系统集成及交付'),('应用下游','在轨计算、遥感处理与算力服务客户')],
    }
    st.caption('下方是可供研究的简化分层框架，不代表已验证的完整产业图谱。')
    cols = st.columns(3)
    for col,(level,entities) in zip(cols,stage_maps[sector]):
        with col:
            with st.container(border=True):
                st.markdown(f'**{level}**')
                st.write(entities)
    target = st.text_input('目标公司（可选）', placeholder='输入后可让 Gemini 判断其产业链位置')
    if st.button('分析生态位', type='primary'):
        if not target.strip(): st.warning('请输入目标公司')
        else:
            result, links = run_ai(f'请分析「{target}」在「{sector}」产业链的具体生态位，上下游、竞争对手、客户、盈利位置和可能的护城河。请避免将商业航天整体产业链与卫星制造细分产业链混为一谈；区分事实、推测与待核实证据。')
            if result:
                st.session_state['map_result'],st.session_state['map_links']=result,links
    if st.session_state.get('map_result'):
        st.markdown(st.session_state['map_result'])
        show_sources(st.session_state.get('map_links',[]))

elif st.session_state.tab == '可比公司':
    section_heading('可比公司', 'Comparable Companies · Research')
    name = st.text_input('目标公司 / 赛道', placeholder='如：AI Coding Agent 或某家具体公司')
    st.caption('分析维度包括业务定位、产品、用户、商业模式及竞争差异。融资、估值、收入如缺少可核实来源必须留空。')
    if st.button('生成可比分析', type='primary'):
        if not name.strip(): st.warning('请输入目标公司或赛道')
        else:
            result, links = run_ai(f'''为 VC 分析师建立「{name}」的可比公司分析。先解释筛选逻辑，再选 5~8 家适合的公司。
输出 Markdown 对比表：公司、核心产品、目标客户、商业模式、差异化、公开融资/收入/估值（仅可核实的事实，注明截至日期，否则写未披露）。
最后解释可比性边界、上市/非上市口径差异、核心投资判断和仍需查证的资料。''')
            if result:
                st.session_state['comps_result'],st.session_state['comps_links']=result,links
    if st.session_state.get('comps_result'):
        st.markdown(st.session_state['comps_result'])
        show_sources(st.session_state.get('comps_links',[]))
        st.download_button('下载可比公司分析',st.session_state['comps_result'],file_name='comparables.md')

st.markdown('<div class="bottom-divider"></div>',unsafe_allow_html=True)
with st.form('followup', clear_on_submit=True):
    a,b = st.columns([12,2],vertical_alignment='bottom')
    with a:
        question = st.text_input('继续追问', placeholder='针对当前公司、图谱或可比表继续追问……',label_visibility='collapsed')
    with b: submit = st.form_submit_button('发送 ↗',use_container_width=True)
    if submit:
        if not question.strip(): st.warning('输入你想继续追问的问题')
        else:
            tab = st.session_state.tab
            company = st.session_state.active_company
            history = db.research_history(company)[:1] if company else []
            context = history[0]['report'][:5000] if history else ''
            result, links = run_ai(f'当前所在模块：{tab}；当前公司：{company or "未指定"}。\n已有研究背景（可能不完整）：{context}\n\n用户问题：{question}')
            if result:
                st.session_state.chat.append((question,result,links))
if st.session_state.chat:
    with st.expander('继续追问记录',expanded=True):
        for q, answer, links in reversed(st.session_state.chat[-5:]):
            st.markdown(f'**你：** {q}')
            st.markdown(answer)
            show_sources(links)
            st.divider()

st.caption('研究内容仅供辅助判断，不构成投资建议。请核实来源并避免上传未经授权的保密资料。')
