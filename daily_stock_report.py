import os
import datetime
import akshare as ak
import pandas as pd
import requests

# ==========================================
# 工具函数：安全获取数据（统一容错）
# ==========================================
def safe_fetch(name, func, default="暂无数据"):
    try:
        result = func()
        print(f"[OK] {name} 获取成功")
        return result
    except Exception as e:
        print(f"[FAIL] {name} 获取失败: {e}")
        return default


# ==========================================
# 一、新闻抓取
# ==========================================
def get_finance_news():
    news_list = []
    keywords = ["美联储", "加息", "英伟达", "美光", "半导体", "AI", "算力",
                "政策", "国务院", "央行", "降准", "降息", "北向", "外资"]
    try:
        df = ak.stock_info_global_cls()
        for _, row in df.head(30).iterrows():
            title = str(row.get("标题", ""))
            content = str(row.get("内容", ""))[:100]
            if any(k in title or k in content for k in keywords):
                news_list.append(f"{title} — {content}")
    except Exception as e:
        print(f"财联社获取失败: {e}")
    if not news_list:
        news_list.append("今日暂无符合关键词的新闻。")
    return news_list


# ==========================================
# 二、大盘指数数据
# ==========================================
def get_market_index():
    try:
        df = ak.stock_zh_index_spot_sina()
        df = df[df["名称"].isin(["上证指数", "深证成指", "创业板指"])]
        return df.to_string(index=False)
    except Exception as e:
        return f"大盘指数获取失败: {e}"


# ==========================================
# 三、资金面数据
# ==========================================
def get_northbound_flow():
    """北向资金净流入"""
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北向资金")
        recent = df.tail(3)
        return recent.to_string(index=False)
    except Exception as e:
        return f"北向资金获取失败: {e}"


def get_margin_data():
    """两融余额（上交所）"""
    try:
        today = datetime.datetime.now().strftime('%Y%m%d')
        start = (datetime.datetime.now() - datetime.timedelta(days=10)).strftime('%Y%m%d')
        df = ak.stock_margin_sse(start_date=start, end_date=today)
        return df.tail(3).to_string(index=False)
    except Exception as e:
        return f"两融数据获取失败: {e}"


def get_lhb_data():
    """龙虎榜机构净买入"""
    try:
        today = datetime.datetime.now().strftime('%Y%m%d')
        df = ak.stock_lhb_detail_em(start_date=today, end_date=today)
        if df is not None and not df.empty:
            return df.head(10).to_string(index=False)
        return "今日暂无龙虎榜数据"
    except Exception as e:
        return f"龙虎榜获取失败: {e}"


# ==========================================
# 四、情绪面数据
# ==========================================
def get_zt_pool():
    """涨停池与跌停池统计"""
    try:
        today = datetime.datetime.now().strftime('%Y%m%d')
        zt = ak.stock_zt_pool_em(date=today)
        zt_count = len(zt) if zt is not None and not zt.empty else 0

        dt = ak.stock_zt_pool_dtgc_em(date=today)
        dt_count = len(dt) if dt is not None and not dt.empty else 0

        # 连板统计
        if zt is not None and not zt.empty and "连板数" in zt.columns:
            lianban = zt[zt["连板数"] >= 2]
            lianban_count = len(lianban)
        else:
            lianban_count = 0

        return f"涨停家数: {zt_count} | 跌停家数: {dt_count} | 连板家数: {lianban_count}"
    except Exception as e:
        return f"涨跌停统计获取失败: {e}"


# ==========================================
# 五、宏观数据
# ==========================================
def get_macro_data():
    """PMI / CPI / M2"""
    result = []
    try:
        pmi = ak.macro_china_pmi()
        result.append(f"PMI最新: {pmi.iloc[0].to_dict() if len(pmi) > 0 else '暂无'}")
    except:
        result.append("PMI获取失败")

    try:
        cpi = ak.macro_china_cpi()
        result.append(f"CPI最新: {cpi.iloc[0].to_dict() if len(cpi) > 0 else '暂无'}")
    except:
        result.append("CPI获取失败")

    try:
        m2 = ak.macro_china_money_supply()
        result.append(f"M2最新: {m2.iloc[0].to_dict() if len(m2) > 0 else '暂无'}")
    except:
        result.append("M2获取失败")

    return "\n".join(result)


# ==========================================
# 六、大宗商品
# ==========================================
def get_commodity_data():
    """全球大宗商品：原油、铜、黄金"""
    try:
        df = ak.futures_global_spot_em()
        if df is not None and not df.empty:
            key_items = df[df["名称"].str.contains("原油|铜|黄金|白银", na=False)]
            if not key_items.empty:
                return key_items.head(5).to_string(index=False)
        return "大宗商品数据暂不可用"
    except Exception as e:
        return f"大宗商品获取失败: {e}"


# ==========================================
# 七、亚太与美股指数
# ==========================================
def get_asia_pacific_index():
    """日经225、韩国KOSPI"""
    try:
        df = ak.index_global_spot_em()
        targets = df[df["名称"].str.contains("日经|韩国", na=False)]
        if not targets.empty:
            return targets[["名称", "最新价", "涨跌幅"]].to_string(index=False)
        return "亚太指数数据暂不可用"
    except Exception as e:
        return f"亚太指数获取失败: {e}"


def get_us_index():
    """美股三大指数：道指、纳指、标普500"""
    try:
        df = ak.index_us_stock_sina()
        targets = df[df["名称"].str.contains("道琼斯|纳斯达克|标普", na=False)]
        if not targets.empty:
            return targets[["名称", "最新价", "涨跌幅"]].to_string(index=False)
        return "美股指数数据暂不可用"
    except Exception as e:
        return f"美股指数获取失败: {e}"


# ==========================================
# 八、机构预期
# ==========================================
def get_forecast_data():
    """盈利预测排名"""
    try:
        df = ak.stock_rank_forecast_cninfo(date=datetime.datetime.now().strftime('%Y%m%d'))
        if df is not None and not df.empty:
            return df.head(10).to_string(index=False)
        return "暂无盈利预测数据"
    except Exception as e:
        return f"盈利预测获取失败: {e}"


# ==========================================
# 九、AI 综合分析（含仓位建议 + 走势预测）
# ==========================================
def summarize_with_ai(news_list, market_index, northbound, margin, lhb,
                      zt_stats, macro, commodity, forecast,
                      asia_pacific, us_index, api_key):
    prompt = f"""你是一名专业A股策略分析师。以下是今日多维度市场数据，请整理成一份简洁的早报。

【大盘指数】
{market_index}

【资金面】
北向资金: {northbound}
两融余额: {margin}
龙虎榜: {lhb}

【市场情绪】
{zt_stats}

【宏观数据】
{macro}

【大宗商品】
{commodity}

【亚太股市（日经/韩国）】
{asia_pacific}

【美股隔夜表现】
{us_index}

【机构预期】
{forecast}

【关键新闻】
{chr(10).join(news_list)}

请严格按照以下HTML格式输出，不要使用Markdown语法（不要用**、#、-等符号），直接输出HTML标签：

<h3>一、宏观环境</h3>
<p>内容（不超过3条，每条用<br>分隔）</p>

<h3>二、资金面与情绪面</h3>
<p>结合北向资金、两融、涨跌停数据，判断资金是流入还是流出，市场情绪是贪婪还是恐慌</p>

<h3>三、科技巨头与产业动态</h3>
<p>内容</p>

<h3>四、对A股可能的影响</h3>
<p>内容（利好/利空哪些板块）</p>

<h3>五、📊 建议仓位</h3>
<p>根据当前市场环境，给出建议仓位区间（如：30%-50%），并说明理由。格式：<strong>建议仓位：XX%-XX%</strong><br>理由：...</p>

<h3>六、📈 今日走势预测</h3>
<p>请结合以下三点给出今日大盘走势判断（如：震荡偏强/冲高回落/低开企稳等），并说明关键支撑位和压力位：<br>
1. 隔夜美股三大指数表现（道指/纳指/标普）<br>
2. 早盘日经225与韩国KOSPI的开盘方向<br>
3. 北向资金与涨跌停家数反映的A股内部情绪<br>
注意：历史上A股与外围存在“非对称联动”——外围大跌时A股跟随概率高，外围大涨时A股未必同步走强。请据此给出审慎判断。</p>

<h3>七、⚠️ 今日风险提示</h3>
<p>内容</p>

要求：
1. 语言精炼，每个板块不超过3条
2. 重要内容用 <strong>加粗</strong>
3. 建议仓位和走势预测要给出明确结论，不要模棱两可
4. 直接输出HTML，不要用代码块包裹，不要有任何额外说明文字
"""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    resp = requests.post("https://api.deepseek.com/chat/completions",
                         headers=headers, json=data)
    result = resp.json()
    if "choices" not in result:
        raise ValueError(f"DeepSeek 返回异常: {result}")

    content = result["choices"][0]["message"]["content"]
    content = content.replace("**", "").replace("```html", "").replace("```", "")
    return content


# ==========================================
# 十、HTML 报告模板
# ==========================================
def build_html_report(content):
    today = pd.Timestamp.now().strftime('%Y-%m-%d')
    html_content = f"""
    <div style="font-family:'Microsoft YaHei',Arial,sans-serif;max-width:680px;margin:0 auto;padding:16px;background:#f7f8fa;">
        <div style="background:#1a1a2e;color:#fff;padding:14px 18px;border-radius:8px 8px 0 0;">
            <h2 style="margin:0;font-size:18px;">📰 {today} 财经内参</h2>
        </div>
        <div style="background:#fff;padding:18px;border-radius:0 0 8px 8px;line-height:1.8;color:#333;font-size:14px;">
            {content}
        </div>
        <p style="color:#999;font-size:12px;text-align:center;margin-top:12px;">
            由 AI 自动生成，仅供参考，不构成投资建议
        </p>
    </div>
    """
    return html_content


# ==========================================
# 十一、推送（支持群组）
# ==========================================
def send_to_wechat(token, title, content, topic=None):
    url = "http://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": title,
        "content": content,
        "template": "html"
    }
    if topic:
        data["topic"] = topic
    response = requests.post(url, json=data)
    print("推送结果:", response.text)


# ==========================================
# 主程序入口
# ==========================================
if __name__ == "__main__":
    try:
        print("=== 开始获取多维度数据 ===")

        print("正在获取新闻...")
        news_list = get_finance_news()

        print("正在获取大盘指数...")
        market_index = get_market_index()

        print("正在获取北向资金...")
        northbound = safe_fetch("北向资金", get_northbound_flow)

        print("正在获取两融数据...")
        margin = safe_fetch("两融数据", get_margin_data)

        print("正在获取龙虎榜...")
        lhb = safe_fetch("龙虎榜", get_lhb_data)

        print("正在获取涨跌停统计...")
        zt_stats = safe_fetch("涨跌停统计", get_zt_pool)

        print("正在获取宏观数据...")
        macro = safe_fetch("宏观数据", get_macro_data)

        print("正在获取大宗商品...")
        commodity = safe_fetch("大宗商品", get_commodity_data)

        print("正在获取亚太指数...")
        asia_pacific = safe_fetch("亚太指数", get_asia_pacific_index)

        print("正在获取美股指数...")
        us_index = safe_fetch("美股指数", get_us_index)

        print("正在获取机构预期...")
        forecast = safe_fetch("机构预期", get_forecast_data)

        print("正在调用AI综合分析...")
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("未找到 DEEPSEEK_API_KEY")
        summary = summarize_with_ai(news_list, market_index, northbound, margin,
                                    lhb, zt_stats, macro, commodity, forecast,
                                    asia_pacific, us_index, api_key)

        print("正在生成报告...")
        title = "今日财经内参"
        content = build_html_report(summary)

        token = os.environ.get("PUSHPLUS_TOKEN")
        if not token:
            raise ValueError("未找到 PUSHPLUS_TOKEN")

        topic = os.environ.get("PUSHPLUS_TOPIC")  # 群组编码，可选
        print("正在推送到微信...")
        send_to_wechat(token, title, content, topic)
        print("执行完毕！")

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(error_msg)
        token = os.environ.get("PUSHPLUS_TOKEN")
        if token:
            send_to_wechat(token, "⚠️ 脚本运行报错", f"<pre>{error_msg}</pre>")
        else:
            print("连 token 都没取到，无法推送报错信息")
