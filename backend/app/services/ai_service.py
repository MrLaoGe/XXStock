import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)

def _get_client():
    from openai import OpenAI
    return OpenAI(base_url=settings.OPENAI_BASE_URL, api_key=settings.OPENAI_API_KEY)

def generate_stock_report(db, stock, quotes, financials, announcements):
    if not settings.OPENAI_API_KEY:
        return _template_report(stock, quotes, financials, announcements)

    client = _get_client()
    stock_info = dict(ts_code=stock.ts_code, name=stock.name, industry=stock.industry)
    quote_data = [dict(date=str(q.trade_date), close=q.close, pct_chg=q.pct_chg, volume=q.volume) for q in quotes[-30:]]
    fin_data = [dict(period=f.period, revenue=f.revenue, net_profit=f.net_profit, roe=f.roe, eps=f.eps) for f in financials[-8:]]
    news_data = [dict(title=a.title, date=str(a.publish_date), source=a.source) for a in announcements[:10]]

    context = json.dumps(dict(stock=stock_info, recent_quotes=quote_data, financials=fin_data, announcements=news_data), ensure_ascii=False, default=str)

    system_prompt = """你是一位专业的A股投资研究员。请根据提供的数据生成一份个股分析报告。
要求：
1. 报告结构包含：公司概览、近期行情、财务分析、公告新闻摘要、风险提示
2. 仅基于提供的数据进行分析，不得编造数据
3. 每个结论需标注引用的数据来源（如 [行情数据]、[财务数据]、[公告]）
4. 如数据不足，明确标注"数据不足"
5. 报告以 Markdown 格式输出
6. 最后附上免责声明：本报告仅供研究参考，不构成投资建议"""

    user_prompt = f"以下是 {stock.ts_code} {stock.name} 的最新数据：\n\n{context}\n\n请生成个股分析报告。"

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[dict(role="system", content=system_prompt), dict(role="user", content=user_prompt)],
            temperature=0.3,
            max_tokens=3000
        )
        content = response.choices[0].message.content
        refs = dict(quotes_count=len(quotes), financials_count=len(financials), announcements_count=len(announcements),
                    source="database", stock_ts_code=stock.ts_code)
        return content, refs
    except Exception as e:
        logger.error("AI report generation failed: %s", e)
        return _template_report(stock, quotes, financials, announcements)

def _template_report(stock, quotes, financials, announcements):
    lines = [f"# {stock.name} ({stock.ts_code}) 个股分析报告\n"]
    lines.append(f"**行业**: {stock.industry or '数据缺失'} | **市场**: {stock.market or '数据缺失'}\n")
    if quotes:
        latest = quotes[-1]
        lines.append("## 近期行情 [行情数据]\n")
        lines.append(f"- 最新收盘价: {latest.close}")
        lines.append(f"- 涨跌幅: {latest.pct_chg}%")
        lines.append(f"- 近30日样本数: {min(len(quotes), 30)} 条\n")
    else:
        lines.append("## 近期行情\n\n数据不足\n")
    if financials:
        fin = financials[-1]
        lines.append("## 财务分析 [财务数据]\n")
        lines.append(f"- 报告期: {fin.period}")
        lines.append(f"- 营业收入: {fin.revenue}")
        lines.append(f"- 净利润: {fin.net_profit}")
        lines.append(f"- ROE: {fin.roe}%")
        lines.append(f"- EPS: {fin.eps}\n")
    else:
        lines.append("## 财务分析\n\n数据不足\n")
    if announcements:
        lines.append("## 近期公告 [公告]\n")
        for a in announcements[:5]:
            lines.append(f"- [{a.publish_date}] {a.title}")
        lines.append("")
    else:
        lines.append("## 近期公告\n\n数据不足\n")
    lines.append("---\n")
    lines.append("*免责声明：本报告仅供研究参考，不构成投资建议。*")
    content = "\n".join(lines)
    refs = dict(quotes_count=len(quotes), financials_count=len(financials), announcements_count=len(announcements),
                source="database", stock_ts_code=stock.ts_code, model="template")
    return content, refs

def agent_answer(db, question, stock=None, quotes=None, financials=None, announcements=None):
    if not settings.OPENAI_API_KEY:
        return dict(answer="AI 服务未配置。请设置 OPENAI_API_KEY 环境变量后重启服务。", references=[])

    client = _get_client()
    context_parts = []
    refs = []
    if stock:
        context_parts.append(f"股票信息: {stock.ts_code} {stock.name} 行业={stock.industry}")
        refs.append(dict(type="stock", ts_code=stock.ts_code))
    if quotes:
        recent = quotes[-10:]
        context_parts.append("近10日行情: " + json.dumps([dict(date=str(q.trade_date), close=q.close, pct_chg=q.pct_chg) for q in recent], ensure_ascii=False))
        refs.append(dict(type="quotes", count=len(recent)))
    if financials:
        context_parts.append("最新财务: " + json.dumps([dict(period=f.period, revenue=f.revenue, net_profit=f.net_profit, roe=f.roe) for f in financials[-3:]], ensure_ascii=False))
        refs.append(dict(type="financials", count=len(financials[-3:])))
    if announcements:
        context_parts.append("近期公告: " + json.dumps([dict(title=a.title, date=str(a.publish_date)) for a in announcements[:5]], ensure_ascii=False))
        refs.append(dict(type="announcements", count=len(announcements[:5])))

    context = "\n".join(context_parts) if context_parts else "数据库中未找到相关数据"
    system_prompt = """你是A股投研助手。仅基于提供的数据回答用户问题。
如果数据不足以回答，明确说明"根据当前数据库中的数据，无法回答该问题"。
回答需标注引用的数据类型。不构成投资建议。"""

    user_prompt = f"用户问题: {question}\n\n数据库上下文:\n{context}"

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[dict(role="system", content=system_prompt), dict(role="user", content=user_prompt)],
            temperature=0.3,
            max_tokens=1000
        )
        answer = response.choices[0].message.content
        return dict(answer=answer, references=refs)
    except Exception as e:
        logger.error("Agent answer failed: %s", e)
        return dict(answer=f"AI 服务调用失败: {str(e)}", references=refs)
