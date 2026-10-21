import os
import sys
import time
import datetime
import akshare as ak
import pandas as pd
import requests

# ==========================================
# 一、工具与基础函数
# ==========================================
def is_trading_day():
    """判断今天是否为 A 股交易日"""
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    try:
        df = ak.tool_trade_date_hist_sina()
        trade_dates = df['trade_date'].astype(str).tolist()
        return today_str in trade_dates
    except Exception as e:
        print(f"获取交易日历失败: {e}")
        return datetime.datetime.now().weekday() < 5

def safe_fetch(name, func, default="暂无数据", retries=3, delay=8):
    """安全获取数据，支持重试"""
    for attempt in range(retries):
        try:
            result = func()
            if result and "获取失败" not in str(result) and "暂不可用" not in str(result):
                print(f"[OK] {name} 获取成功 (尝试 {attempt + 1}/{retries})")
                return result
            else:
                print(f"[WARN] {name} 返回空或错误，尝试 {attempt + 1}/{retries}")
        except Exception as e:
            print(f"[FAIL] {name} 获取失败 (尝试 {attempt + 1}/{retries}): {e}")
        if attempt < retries - 1:
            time.sleep(delay)
    print(f"[ERROR] {name} 在 {retries} 次尝试后仍失败")
    return default


# ==========================================
# 二、各维度数据抓取函数
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

def get_market_index():
    indices = {
        "上证指数": {"em": "000001", "sina": "sh000001", "tx": "sh000001"},
        "深证成指": {"em": "399001", "sina": "sz399001", "tx": "sz399001"},
        "创业板指": {"em": "399006", "sina": "sz399006", "tx": "sz399006"}
    }
    result_lines = []
    today = datetime.datetime.now()
    start_date = (today - datetime.timedelta(days=15)).strftime('%Y%m%d')
    end_date = today.strftime('%Y%m%d')

    for name, codes in indices.items():
        df = None
        # 方法1：东方财富
        try:
            df = ak.index_zh_a_hist(symbol=codes["em"], period="daily", start_date=start_date, end_date=end_date)
            if df is not None and len(df) >= 2:
                print(f"[OK] {name} 使用东财接口")
        except Exception:
            df = None

        # 方法2：新浪财经
        if df is None:
            try:
                df = ak.stock_zh_index_daily(symbol=codes["sina"])
                if df is not None and len(df) >= 2:
                    df = df.rename(columns={"date": "日期", "close": "收盘", "volume": "成交量"})
                    df["涨跌幅"] = df["收盘"].pct_change() * 100
                    df["成交额"] = df.get("amount", df["成交量"])
            except Exception:
                df = None

        # 方法3：腾讯财经
        if df is None:
            try:
                df = ak.stock_zh_index_daily_tx(symbol=codes["tx"])
                if df is not None and len(df) >= 2:
                    df = df.rename(columns={"date": "日期", "close": "收盘", "amount": "成交额"})
                    df["涨跌幅"] = df["收盘"].pct_change() * 100
            except Exception:
                df = None

        # 解析
        if df is not None and len(df) >= 2:
            last = df.iloc[-1]
            prev = df.iloc[-2]
            date_str = str(last.get("日期", ""))[:10]
            close = last.get("收盘", "暂无")
            change = last.get("涨跌幅", "暂无")
            amount = last.get("成交额", 0)
            prev_amount = prev.get("成交额", 0)

            if pd.isna(amount): amount = 0
            if pd.isna(prev_amount): prev_amount = 0

            amount_yi = amount / 100000000 if amount else 0
            prev_amount_yi = prev_amount / 100000000 if prev_amount else 0
            diff = amount_yi - prev_amount_yi

            if diff > 0:
                volume_status = f"较前日放量 {diff:.0f}亿"
            elif diff < 0:
                volume_status = f"较前日缩量 {abs(diff):.0f}亿"
            else:
                volume_status = "较前日持平"

            result_lines.append(f"{name}（{date_str}）：收盘 {close}（{change:.2f}%），成交额 {amount_yi:.0f}亿，{volume_status}")
        else:
            result_lines.append(f"{name}：所有接口均获取失败")

    return "\n".join(result_lines) if result_lines else "大盘指数获取失败"

def get_market_fund_flow():
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {"secid": "1.000001", "secid2": "0.399001", "klt": "101", "lmt": "0", "fields1": "f1,f2,f3,f7", "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        klines = data.get("data", {}).get("klines", [])
        if not klines: return "大盘主力资金数据暂不可用"
        lines = []
        for k in klines[-3:]:
            parts = k.split(",")
            date = parts[0]
            main_net = float(parts[1]) / 100000000
            direction = "流入" if main_net > 0 else "流出"
            lines.append(f"{date}：主力净{direction} {abs(main_net):.0f}亿")
        return "大盘主力资金流向（近3日）：\n" + "\n".join(lines)
    except Exception:
        return "大盘主力资金数据暂不可用"

def get_sector_fund_flow():
    try:
        df = ak.stock_fund_flow_industry(symbol="即时")
        if df is not None and not df.empty:
            name_col = "行业" if "行业" in df.columns else df.columns[1]
            net_col = "净额" if "净额" in df.columns else None
            if net_col is None:
                if "流入资金" in df.columns and "流出资金" in df.columns:
                    df["_net"] = df["流入资金"] - df["流出资金"]
                    net_col = "_net"
            else:
                df_sorted = df.sort_values(net_col, ascending=False)
                lines = ["【资金流入前5板块（同花顺）】"]
                for _, row in df_sorted.head(5).iterrows():
                    lines.append(f"  {row[name_col]}：{row[net_col]:.1f}亿")
                lines.append("【资金流出前5板块（同花顺）】")
                for _, row in df_sorted.tail(5).iterrows():
                    lines.append(f"  {row[name_col]}：{row[net_col]:.1f}亿")
                return "\n".join(lines)
    except Exception:
        pass

    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {"pn": "1", "pz": "100", "po": "1", "np": "1", "ut": "bd1d9ddb04089700cf9c27f6f7426281", "fltt": "2", "invt": "2", "fid": "f62", "fs": "m:90+t:3", "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87"}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("diff", [])
        if items:
            df = pd.DataFrame(items)
            df_sorted = df.sort_values("f62", ascending=False)
            lines = ["【资金流入前5板块（东财）】"]
            for _, row in df_sorted.head(5).iterrows():
                lines.append(f"  {row.get('f14', '')}：{row.get('f62', 0) / 100000000:.1f}亿")
            lines.append("【资金流出前5板块（东财）】")
            for _, row in df_sorted.tail(5).iterrows():
                lines.append(f"  {row.get('f14', '')}：{row.get('f62', 0) / 100000000:.1f}亿")
            return "\n".join(lines)
    except Exception:
        pass

    return "板块资金流向数据暂不可用"

def get_margin_data():
    try:
        today = datetime.datetime.now().strftime('%Y%m%d')
        start = (datetime.datetime.now() - datetime.timedelta(days=10)).strftime('%Y%m%d')
        df = ak.stock_margin_sse(start_date=start, end_date=today)
        return df.tail(3).to_string(index=False)
    except Exception as e:
        return f"两融数据获取失败: {e}"

def get_lhb_data():
    try:
        today = datetime.datetime.now().strftime('%Y%m%d')
        df = ak.stock_lhb_detail_em(start_date=today, end_date=today)
        if df is not None and not df.empty:
            return df.head(10).to_string(index=False)
        return "今日暂无龙虎榜数据"
    except Exception as e:
        return f"龙虎榜获取失败: {e}"

def get_zt_pool():
    try:
        today = datetime.datetime.now().strftime('%Y%m%d')
        zt = ak.stock_zt_pool_em(date=today)
        zt_count = len(zt) if zt is not None and not zt.empty else 0
        dt = ak.stock_zt_pool_dtgc_em(date=today)
        dt_count = len(dt) if dt is not None and not dt.empty else 0
        lianban_count = len(zt[zt["连板数"] >= 2]) if zt is not None and not zt.empty and "连板数" in zt.columns else 0
        return f"涨停家数: {zt_count} | 跌停家数: {dt_count} | 连板家数: {lianban_count}"
    except Exception as e:
        return f"涨跌停统计获取失败: {e}"

def get_macro_data():
    result = []
    try:
        pmi = ak.macro_china_pmi()
        result.append(f"PMI最新: {pmi.iloc[0].to_dict() if len(pmi) > 0 else '暂无'}")
    except: result.append("PMI获取失败")
    try:
        cpi = ak.macro_china_cpi()
        result.append(f"CPI最新: {cpi.iloc[0].to_dict() if len(cpi) > 0 else '暂无'}")
    except: result.append("CPI获取失败")
    try:
        m2 = ak.macro_china_money_supply()
        result.append(f"M2最新: {m2.iloc[0].to_dict() if len(m2) > 0 else '暂无'}")
    except: result.append("M2获取失败")
    return "\n".join(result)

def get_commodity_data():
    try:
        df = ak.futures_global_spot_em()
        if df is not None and not df.empty:
            key_items = df[df["名称"].str.contains("原油|铜|黄金|白银", na=False)]
            if not key_items.empty:
                return key_items.head(5).to_string(index=False)
        return "大宗商品数据暂不可用"
    except Exception as e:
        return f"大宗商品获取失败: {e}"

def get_asia_pacific_index():
    try:
        df = ak.index_global_spot_em()
        name_col = next((c for c in ["名称", "指数名称", "name", "Name"] if c in df.columns), None)
        if name_col:
            targets = df[df[name_col].str.contains("日经|韩国|KOSPI|Nikkei", na=False)]
            if not targets.empty:
                price_col = next((c for c in ["最新价", "最新", "close", "价格"] if c in targets.columns), None)
                change_col = next((c for c in ["涨跌幅", "涨幅", "change_pct"] if c in targets.columns), None)
                lines = []
                for _, row in targets.iterrows():
                    lines.append(f"{row[name_col]}: {row[price_col] if price_col else '暂无'}（{row[change_col] if change_col else '暂无'}%）")
                return "（东财实时）\n" + "\n".join(lines)
    except Exception: pass

    try:
        import yfinance as yf
        tickers = {"日经225": "^N225", "韩国KOSPI": "^KS11"}
        lines = []
        for name, code in tickers.items():
            data = yf.Ticker(code).history(period="2d")
            if not data.empty:
                latest, prev = data.iloc[-1], data.iloc[-2] if len(data) >= 2 else data.iloc[-1]
                change = (latest["Close"] - prev["Close"]) / prev["Close"] * 100
                lines.append(f"{name}（{data.index[-1].date()}）: 收盘 {latest['Close']:.2f}，涨跌幅 {change:.2f}%")
        if lines:
            return "（yfinance）\n" + "\n".join(lines)
    except Exception: pass

    return "亚太指数数据暂不可用"

def get_us_index():
    try:
        import yfinance as yf
        tickers = {"道琼斯": "^DJI", "纳斯达克": "^IXIC", "标普500": "^GSPC"}
        lines = []
        for name, code in tickers.items():
            data = yf.Ticker(code).history(period="2d")
            if not data.empty:
                latest, prev = data.iloc[-1], data.iloc[-2] if len(data) >= 2 else data.iloc[-1]
                change = (latest["Close"] - prev["Close"]) / prev["Close"] * 100
                lines.append(f"{name}（{data.index[-1].date()}）: 收盘 {latest['Close']:.2f}，涨跌幅 {change:.2f}%")
        if lines:
            return "（yfinance）\n" + "\n".join(lines)
    except Exception: pass

    try:
        df = ak.stock_us_spot_em()
        name_col = next((c for c in ["名称", "name", "Name"] if c in df.columns), None)
        if name_col:
            targets = df[df[name_col].str.contains("道琼斯|纳斯达克|标普", na=False)]
            if not targets.empty:
                price_col = next((c for c in ["最新价", "现价", "close"] if c in targets.columns), None)
                change_col = next((c for c in ["涨跌幅", "涨幅"] if c in targets.columns), None)
                lines = [f"{row[name_col]}: {row[price_col] if price_col else '暂无'}（{row[change_col] if change_col else '暂无'}%）" for _, row in targets.iterrows()]
                if lines:
                    return "（东财实时）\n" + "\n".join(lines)
    except Exception: pass

    try:
        df = ak.index_us_stock_sina()
        if df is not None and not df.empty:
            df = df.sort_values("date", ascending=False)
            latest = df.iloc[0]
            close = latest.get("close", "暂无")
            if len(df) >= 2:
                prev_close = df.iloc[1].get("close", close)
                change = (close - prev_close) / prev_close * 100 if prev_close else 0
                change_str = f"{change:.2f}%"
            else:
                change_str = "暂无"
            return f"（新浪标普500）\n标普500（{str(latest.get('date', ''))[:10]}）: 收盘 {close}，涨跌幅 {change_str}"
    except Exception: pass

    return "美股指数数据暂不可用"

def get_forecast_data():
    try:
        df = ak.stock_rank_forecast_cninfo(date=datetime.datetime.now().strftime('%Y%m%d'))
        if df is not None and not df.empty:
            return df.head(10).to_string(index=False)
        return "暂无盈利预测数据"
    except Exception as e:
        return f"盈利预测获取失败: {e}"


# ==========================================
# 三、近期大事整理（新增模块）
# ==========================================
def get_fed_calendar():
    """获取美联储近期议息会议日程"""
    try:
        fomc_dates = [
            "2026-10-27/28",
            "2026-12-08/09"
        ]
        today = datetime.datetime.now().date()
        next_meeting_str = fomc_dates[0].split('/')[0]
        next_meeting = datetime.datetime.strptime(next_meeting_str, "%Y-%m-%d").date()
        days_until = (next_meeting - today).days
        
        if days_until >= 0:
            return f"下一次美联储FOMC议息会议：{next_meeting_str}，距今 {days_until} 天。"
        else:
            return "近期美联储议息会议已过，请关注会议纪要发布。"
    except Exception as e:
        return f"获取美联储日程失败: {e}"

def get_earnings_calendar(days=7):
    """获取未来N天A股重点公司财报预约披露情况"""
    try:
        month = datetime.datetime.now().month
        if month in [1, 2, 3, 4]:
            report_date = "20260331"
        elif month in [5, 6, 7, 8]:
            report_date = "20260630"
        elif month in [9, 10]:
            report_date = "20260930"
        else:
            report_date = "20261231"
            
        df = ak.stock_yysj_em(date=report_date)
        if df is None or df.empty:
            return "近期暂无A股财报预约披露数据。"
        
        df['预约披露时间'] = pd.to_datetime(df['预约披露时间'])
        today = pd.Timestamp.now().normalize()
        future_date = today + pd.Timedelta(days=days)
        
        upcoming = df[(df['预约披露时间'] >= today) & (df['预约披露时间'] <= future_date)]
        
        if upcoming.empty:
            return f"未来{days}天内无重要A股财报预约披露。"
        
        lines = [f"未来{days}天内的A股重点财报披露（部分）："]
        for _, row in upcoming.head(10).iterrows():
            lines.append(f"  - {row.get('股票简称', '')} ({row.get('股票代码', '')})：{row.get('预约披露时间', '').strftime('%Y-%m-%d')}")
        return "\n".join(lines)
    except Exception as e:
        return f"获取A股财报日历失败: {e}"

def get_key_economic_events():
    """获取近期关键宏观数据发布日程"""
    events = [
        "每月10-15日：美国CPI / PPI 通胀数据发布期，关注对美联储降息预期的扰动。",
        "每月首个周五（北京时间20:30/21:30）：美国非农就业数据（NFP），影响全球风险资产定价。",
        "国内每月9-15日：中国CPI/PPI、社融及M2数据密集发布期，关注国内经济复苏成色。",
        "国内每月底/月初：中国官方制造业PMI及财新PMI发布，观察荣枯线得失。"
    ]
    return "宏观关键节点提醒：\n" + "\n".join([f"  - {e}" for e in events])


# ==========================================
# 四、AI 综合分析
# ==========================================
def summarize_with_ai(news_list, market_index, market_fund, sector_fund, margin, lhb,
                      zt_stats, macro, commodity, forecast,
                      asia_pacific, us_index, fed_calendar, earnings_calendar, key_events, api_key):
    prompt = f"""你是一名专业A股策略分析师。以下是今日多维度市场数据，请整理成一份简洁的早报。

【近期关键大事预警】
美联储动态：{fed_calendar}
A股财报披露：{earnings_calendar}
宏观数据节点：{key_events}

【大盘指数】
{market_index}

【资金面】
大盘资金流向: {market_fund}
行业板块资金流向: {sector_fund}
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
<p>结合大盘资金流向、行业板块资金流向、两融、涨跌停数据，判断资金是流入还是流出，市场情绪是贪婪还是恐慌，并指出资金重点流入/流出的板块</p>

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
3. 大盘资金流向、板块资金流向与涨跌停家数反映的A股内部情绪<br>
注意：历史上A股与外围存在"非对称联动"——外围大跌时A股跟随概率高，外围大涨时A股未必同步走强。请据此给出审慎判断。如果某项数据缺失，请明确标注"数据缺失"并说明该缺失对判断的影响，不要强行给出结论。</p>

<h3>七、⚠️ 近期大事预警（必看）</h3>
<p>根据【近期关键大事预警】数据，提取未来3-7天内最需要关注的1-3件核心大事（如美联储议息、重磅财报、CPI发布等），并简要提示其对A股的可能影响。</p>

<h3>八、⚠️ 今日风险提示</h3>
<p>内容</p>

要求：
1. 语言精炼，每个板块不超过3条
2. 重要内容用 <strong>加粗</strong>
3. 建议仓位和走势预测要给出明确结论，不要模棱两可
4. 直接输出HTML，不要用代码块包裹，不要有任何额外说明文字
"""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
    resp = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data)
    result = resp.json()
    if "choices" not in result:
        raise ValueError(f"DeepSeek 返回异常: {result}")
    content = result["choices"][0]["message"]["content"]
    content = content.replace("**", "").replace("```html", "").replace("```", "")
    return content


# ==========================================
# 五、HTML 渲染与推送
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

def send_to_wechat(token, title, content, topic=None):
    url = "http://www.pushplus.plus/send"
    data = {"token": token, "title": title, "content": content, "template": "html"}
    if topic:
        data["topic"] = topic
    response = requests.post(url, json=data)
    print("推送结果:", response.text)


# ==========================================
# 六、主程序入口
# ==========================================
if __name__ == "__main__":
    # 1. 拦截非交易日
    if not is_trading_day():
        print(f"今天 ({datetime.datetime.now().strftime('%Y-%m-%d')}) 不是 A 股交易日，系统自动跳过推送。")
        sys.exit(0)

    # 2. 正常交易日执行流程
    try:
        print("=== 开始获取多维度数据 ===")

        print("正在获取新闻...")
        news_list = get_finance_news()

        print("正在获取大盘指数...")
        market_index = get_market_index()

        print("正在获取大盘资金流向...")
        market_fund = safe_fetch("大盘资金流向", get_market_fund_flow)

        print("正在获取行业板块资金流向...")
        sector_fund = safe_fetch("行业板块资金流向", get_sector_fund_flow)

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

        print("正在获取近期大事预警...")
        fed_calendar = safe_fetch("美联储日程", get_fed_calendar)
        earnings_calendar = safe_fetch("A股财报日历", get_earnings_calendar)
        key_events = safe_fetch("宏观关键节点", get_key_economic_events)

        print("正在获取机构预期...")
        forecast = safe_fetch("机构预期", get_forecast_data)

        print("正在调用AI综合分析...")
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("未找到 DEEPSEEK_API_KEY")
        
        # 传入新增的三个数据参数
        summary = summarize_with_ai(news_list, market_index, market_fund, sector_fund,
                                    margin, lhb, zt_stats, macro, commodity, forecast,
                                    asia_pacific, us_index, fed_calendar, earnings_calendar, key_events, api_key)

        print("正在生成报告...")
        title = "今日财经内参"
        content = build_html_report(summary)

        token = os.environ.get("PUSHPLUS_TOKEN")
        if not token:
            raise ValueError("未找到 PUSHPLUS_TOKEN")

        topic = os.environ.get("PUSHPLUS_TOPIC")
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
