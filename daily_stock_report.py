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
        return today_str in df['trade_date'].astype(str).tolist()
    except Exception:
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
        try:
            df = ak.index_zh_a_hist(symbol=codes["em"], period="daily", start_date=start_date, end_date=end_date)
            if df is not None and len(df) >= 2: print(f"[OK] {name} 东财")
        except Exception: df = None
        if df is None:
            try:
                df = ak.stock_zh_index_daily(symbol=codes["sina"])
                if df is not None and len(df) >= 2:
                    df = df.rename(columns={"date": "日期", "close": "收盘", "volume": "成交量"})
                    df["涨跌幅"] = df["收盘"].pct_change() * 100
                    df["成交额"] = df.get("amount", df["成交量"])
            except Exception: df = None
        if df is None:
            try:
                df = ak.stock_zh_index_daily_tx(symbol=codes["tx"])
                if df is not None and len(df) >= 2:
                    df = df.rename(columns={"date": "日期", "close": "收盘", "amount": "成交额"})
                    df["涨跌幅"] = df["收盘"].pct_change() * 100
            except Exception: df = None

        if df is not None and len(df) >= 2:
            last, prev = df.iloc[-1], df.iloc[-2]
            date_str = str(last.get("日期", ""))[:10]
            close, change = last.get("收盘", "暂无"), last.get("涨跌幅", "暂无")
            amount, prev_amount = last.get("成交额", 0), prev.get("成交额", 0)
            if pd.isna(amount): amount = 0
            if pd.isna(prev_amount): prev_amount = 0
            amount_yi, prev_amount_yi = amount / 1e8, prev_amount / 1e8
            diff = amount_yi - prev_amount_yi
            vol = f"放量 {diff:.0f}亿" if diff > 0 else (f"缩量 {abs(diff):.0f}亿" if diff < 0 else "持平")
            result_lines.append(f"{name}（{date_str}）：收盘 {close}（{change:.2f}%），成交额 {amount_yi:.0f}亿，较前日{vol}")
        else:
            result_lines.append(f"{name}：接口均失败")
    return "\n".join(result_lines)

def get_market_fund_flow():
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {"secid": "1.000001", "secid2": "0.399001", "klt": "101", "lmt": "0", "fields1": "f1,f2,f3,f7", "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"}
    try:
        resp = requests.get(url, params=params, timeout=15); resp.raise_for_status()
        klines = resp.json().get("data", {}).get("klines", [])
        if not klines: return "大盘主力资金暂不可用"
        lines = []
        for k in klines[-3:]:
            p = k.split(","); d = p[0]; net = float(p[1]) / 1e8
            lines.append(f"{d}：净{'流入' if net > 0 else '流出'} {abs(net):.0f}亿")
        return "大盘主力资金流向（近3日）：\n" + "\n".join(lines)
    except Exception: return "大盘主力资金暂不可用"

def get_sector_fund_flow():
    try:
        df = ak.stock_fund_flow_industry(symbol="即时")
        if df is not None and not df.empty:
            name_col = "行业" if "行业" in df.columns else df.columns[1]
            net_col = "净额" if "净额" in df.columns else ("_net" if "流入资金" in df.columns else None)
            if net_col == "_net": df["_net"] = df["流入资金"] - df["流出资金"]
            if net_col:
                df_sorted = df.sort_values(net_col, ascending=False)
                lines = ["【资金流入前5板块（同花顺）】"]
                for _, row in df_sorted.head(5).iterrows(): lines.append(f"  {row[name_col]}：{row[net_col]:.1f}亿")
                lines.append("【资金流出前5板块（同花顺）】")
                for _, row in df_sorted.tail(5).iterrows(): lines.append(f"  {row[name_col]}：{row[net_col]:.1f}亿")
                return "\n".join(lines)
    except Exception: pass
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {"pn": "1", "pz": "100", "po": "1", "np": "1", "ut": "bd1d9ddb04089700cf9c27f6f7426281", "fltt": "2", "invt": "2", "fid": "f62", "fs": "m:90+t:3", "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87"}
        items = requests.get(url, params=params, timeout=15).json().get("data", {}).get("diff", [])
        if items:
            df = pd.DataFrame(items).sort_values("f62", ascending=False)
            lines = ["【资金流入前5板块（东财）】"]
            for _, row in df.head(5).iterrows(): lines.append(f"  {row.get('f14','')}：{row.get('f62',0)/1e8:.1f}亿")
            lines.append("【资金流出前5板块（东财）】")
            for _, row in df.tail(5).iterrows(): lines.append(f"  {row.get('f14','')}：{row.get('f62',0)/1e8:.1f}亿")
            return "\n".join(lines)
    except Exception: pass
    return "板块资金流向暂不可用"

def get_margin_data():
    try:
        today = datetime.datetime.now().strftime('%Y%m%d')
        start = (datetime.datetime.now() - datetime.timedelta(days=10)).strftime('%Y%m%d')
        return ak.stock_margin_sse(start_date=start, end_date=today).tail(3).to_string(index=False)
    except Exception as e: return f"两融获取失败: {e}"

def get_lhb_data():
    try:
        today = datetime.datetime.now().strftime('%Y%m%d')
        df = ak.stock_lhb_detail_em(start_date=today, end_date=today)
        return df.head(10).to_string(index=False) if df is not None and not df.empty else "今日暂无龙虎榜"
    except Exception as e: return f"龙虎榜获取失败: {e}"

def get_zt_pool():
    try:
        today = datetime.datetime.now().strftime('%Y%m%d')
        zt = ak.stock_zt_pool_em(date=today); dt = ak.stock_zt_pool_dtgc_em(date=today)
        zt_c = len(zt) if zt is not None and not zt.empty else 0
        dt_c = len(dt) if dt is not None and not dt.empty else 0
        lb_c = len(zt[zt["连板数"] >= 2]) if zt is not None and not zt.empty and "连板数" in zt.columns else 0
        return f"涨停: {zt_c} | 跌停: {dt_c} | 连板: {lb_c}"
    except Exception as e: return f"涨跌停获取失败: {e}"

def get_macro_data():
    res = []
    for name, func in [("PMI", ak.macro_china_pmi), ("CPI", ak.macro_china_cpi), ("M2", ak.macro_china_money_supply)]:
        try:
            d = func(); res.append(f"{name}最新: {d.iloc[0].to_dict() if len(d) > 0 else '暂无'}")
        except: res.append(f"{name}获取失败")
    return "\n".join(res)

def get_commodity_data():
    try:
        df = ak.futures_global_spot_em()
        key = df[df["名称"].str.contains("原油|铜|黄金|白银", na=False)]
        return key.head(5).to_string(index=False) if not key.empty else "大宗暂不可用"
    except Exception as e: return f"大宗获取失败: {e}"

def get_asia_pacific_index():
    try:
        df = ak.index_global_spot_em()
        name_c = next((c for c in ["名称", "指数名称", "name"] if c in df.columns), None)
        if name_c:
            t = df[df[name_c].str.contains("日经|韩国|KOSPI|Nikkei", na=False)]
            if not t.empty:
                p_c = next((c for c in ["最新价", "最新", "close"] if c in t.columns), None)
                c_c = next((c for c in ["涨跌幅", "涨幅"] if c in t.columns), None)
                return "（东财）\n" + "\n".join([f"{r[name_c]}: {r[p_c] if p_c else '—'}（{r[c_c] if c_c else '—'}%）" for _, r in t.iterrows()])
    except Exception: pass
    try:
        import yfinance as yf
        lines = []; tickers = {"日经225": "^N225", "韩国KOSPI": "^KS11"}
        for n, c in tickers.items():
            d = yf.Ticker(c).history(period="2d")
            if not d.empty:
                l, p = d.iloc[-1], d.iloc[-2] if len(d) >= 2 else d.iloc[-1]
                lines.append(f"{n}（{d.index[-1].date()}）: {l['Close']:.2f}（{(l['Close']-p['Close'])/p['Close']*100:.2f}%）")
        if lines: return "（yfinance）\n" + "\n".join(lines)
    except Exception: pass
    return "亚太指数暂不可用"

def get_us_index():
    try:
        import yfinance as yf
        lines = []; tickers = {"道琼斯": "^DJI", "纳斯达克": "^IXIC", "标普500": "^GSPC"}
        for n, c in tickers.items():
            d = yf.Ticker(c).history(period="2d")
            if not d.empty:
                l, p = d.iloc[-1], d.iloc[-2] if len(d) >= 2 else d.iloc[-1]
                lines.append(f"{n}（{d.index[-1].date()}）: {l['Close']:.2f}（{(l['Close']-p['Close'])/p['Close']*100:.2f}%）")
        if lines: return "（yfinance）\n" + "\n".join(lines)
    except Exception: pass
    try:
        df = ak.stock_us_spot_em()
        name_c = next((c for c in ["名称", "name"] if c in df.columns), None)
        if name_c:
            t = df[df[name_c].str.contains("道琼斯|纳斯达克|标普", na=False)]
            if not t.empty:
                p_c = next((c for c in ["最新价", "现价"] if c in t.columns), None)
                c_c = next((c for c in ["涨跌幅", "涨幅"] if c in t.columns), None)
                return "（东财）\n" + "\n".join([f"{r[name_c]}: {r[p_c] if p_c else '—'}（{r[c_c] if c_c else '—'}%）" for _, r in t.iterrows()])
    except Exception: pass
    try:
        df = ak.index_us_stock_sina().sort_values("date", ascending=False); l = df.iloc[0]
        c = l.get("close", "—")
        ch = f"{(c - df.iloc[1].get('close', c)) / df.iloc[1].get('close', c) * 100:.2f}%" if len(df) >= 2 else "—"
        return f"（新浪标普500）\n标普500（{str(l.get('date',''))[:10]}）: {c}（{ch}）"
    except Exception: pass
    return "美股暂不可用"

def get_forecast_data():
    try:
        df = ak.stock_rank_forecast_cninfo(date=datetime.datetime.now().strftime('%Y%m%d'))
        return df.head(10).to_string(index=False) if df is not None and not df.empty else "暂无盈利预测"
    except Exception as e: return f"盈利预测失败: {e}"

def get_fed_calendar():
    try:
        fomc = ["2026-10-27/28", "2026-12-08/09"]
        today = datetime.datetime.now().date()
        nxt = datetime.datetime.strptime(fomc[0].split('/')[0], "%Y-%m-%d").date()
        days = (nxt - today).days
        return f"下次FOMC：{fomc[0]}，距今 {days} 天。" if days >= 0 else "近期FOMC已过。"
    except Exception as e: return f"美联储日程失败: {e}"

def get_earnings_calendar(days=7):
    try:
        month = datetime.datetime.now().month
        rd = "20260331" if month in [1,2,3,4] else ("20260630" if month in [5,6,7,8] else ("20260930" if month in [9,10] else "20261231"))
        df = ak.stock_yysj_em(date=rd)
        if df is None or df.empty: return "近期暂无财报数据"
        df['预约披露时间'] = pd.to_datetime(df['预约披露时间'])
        today = pd.Timestamp.now().normalize(); fut = today + pd.Timedelta(days=days)
        up = df[(df['预约披露时间'] >= today) & (df['预约披露时间'] <= fut)]
        if up.empty: return f"未来{days}天无重要财报"
        return f"未来{days}天重点财报：\n" + "\n".join([f"  - {r.get('股票简称','')}（{r.get('股票代码','')}）：{r.get('预约披露时间','').strftime('%Y-%m-%d')}" for _, r in up.head(10).iterrows()])
    except Exception as e: return f"财报日历失败: {e}"

def get_key_economic_events():
    return "宏观节点：\n  - 每月10-15日：美国CPI/PPI\n  - 每月首个周五：美国非农\n  - 每月9-15日：中国CPI/PPI/社融/M2\n  - 月底/月初：中国官方及财新PMI"

def get_broad_etf_flow():
    """基于量价关系统计宽基ETF趋势（含最新单日异动特征）"""
    etf_list = {
        "510300": "沪深300ETF",
        "510500": "中证500ETF",
        "159915": "创业板ETF",
        "510050": "上证50ETF",
        "588000": "科创50ETF",
        "512100": "中证1000ETF"
    }
    
    res = []
    end = datetime.datetime.now().strftime('%Y%m%d')
    start = (datetime.datetime.now() - datetime.timedelta(days=120)).strftime('%Y%m%d')
    
    for code, name in etf_list.items():
        df = None
        err_msg = ""
        
        # 方案一：优先尝试东方财富接口
        try:
            df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start, end_date=end)
            if df is not None and not df.empty:
                print(f"[OK] {name} 使用东财接口")
            else:
                df = None
        except Exception as e:
            err_msg += f"东财失败:{e}; "
            df = None
            
        # 方案二：降级使用新浪接口
        if df is None:
            try:
                prefix = "sh" if code.startswith("5") else "sz"
                sina_code = f"{prefix}{code}"
                df_sina = ak.fund_etf_hist_sina(symbol=sina_code)
                if df_sina is not None and not df_sina.empty:
                    df = df_sina.rename(columns={"date": "日期", "open": "开盘", "close": "收盘", "high": "最高", "low": "最低", "volume": "成交量"})
                    df["涨跌幅"] = df["收盘"].pct_change() * 100
                    df["成交额"] = df["收盘"] * df["成交量"]
                    print(f"[OK] {name} 使用新浪接口")
                else:
                    df = None
            except Exception as e:
                err_msg += f"新浪失败:{e}"
                df = None

        if df is None or df.empty:
            res.append(f"{name}：数据获取失败({err_msg})")
            continue
            
        df = df.sort_values("日期").tail(120)

        # === 提取最新单日量价特征 ===
        latest = df.iloc[-1]
        prev_5 = df.iloc[-6:-1]
        
        l_chg = latest.get("涨跌幅", 0)
        l_amount = latest.get("成交额", 0) / 1e8
        avg_5_amount = prev_5["成交额"].mean() / 1e8
        
        # 判断单日量能
        if avg_5_amount > 0:
            vol_ratio = l_amount / avg_5_amount
            vol_status = "放量" if vol_ratio > 1.2 else ("缩量" if vol_ratio < 0.8 else "平量")
        else:
            vol_status = "无对比"
            
        # 判断长下影线 (实体大小 vs 下影线长度)
        o = latest.get("开盘", latest.get("收盘"))
        c = latest.get("收盘")
        l = latest.get("最低", c)
        lower_shadow = min(o, c) - l
        body = abs(o - c)
        
        shadow_desc = ""
        # 下影线大于实体1.5倍，且单日没暴跌（>-2%），说明下方有承接
        if lower_shadow > 0 and lower_shadow > body * 1.5 and l_chg > -2:
            shadow_desc = "，带长下影线(探底回升)"

        latest_desc = f"最新日[{l_chg:+.1f}%/{vol_status}({l_amount:.1f}亿){shadow_desc}]"

        # === 计算长周期累计趋势 ===
        def calc_trend(days):
            recent = df.tail(days)
            if recent.empty: return "无数据"
            
            total_chg = recent["涨跌幅"].sum()
            avg_vol = recent["成交额"].mean() / 1e8
            
            if total_chg < -3 and avg_vol > 1:
                status = "放量下跌"
            elif total_chg < -3:
                status = "缩量阴跌"
            elif total_chg > 3 and avg_vol > 1:
                status = "放量上涨"
            elif total_chg > 3:
                status = "缩量上涨"
            else:
                status = "震荡"
            return f"{total_chg:+.1f}%/{avg_vol:.1f}亿({status})"

        res.append(f"{name}：{latest_desc} | 30日[{calc_trend(30)}] | 60日[{calc_trend(60)}]")
            
    return "\n".join(res) if res else "宽基ETF流向暂不可用"

# ==========================================
# 三、AI 综合分析
# ==========================================
def summarize_with_ai(news_list, market_index, market_fund, sector_fund, margin, lhb,
                      zt_stats, macro, commodity, forecast,
                      asia_pacific, us_index, fed_calendar, earnings_calendar, key_events,
                      etf_flow, api_key):
    prompt = f"""你是一名极度厌恶风险的A股资深策略分析师。以下是今日多维度市场数据，请整理成一份简洁的早报。

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

【宽基ETF量价趋势（涨跌幅/日均成交额/资金推断）】
{etf_flow}

【市场情绪】
{zt_stats}

【宏观数据】
{macro}

【大宗商品】
{commodity}

【亚太股市】
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
<p>结合大盘资金流向、行业板块、两融、涨跌停数据，判断资金进出和情绪。</p>

<h3>三、科技巨头与产业动态</h3>
<p>内容</p>

<h3>四、对A股可能的影响</h3>
<p>内容（利好/利空哪些板块）</p>

<h3>五、🏦 宽基ETF量价趋势观察</h3>
<p>根据数据，综合分析“中长期趋势”与“最新单日异动”：<br>
1. 如果长周期（30/60日）是“放量下跌”，但【最新日】出现了“放量且带长下影线”，请重点提示这是“<strong>超跌后的资金抄底/探底回升信号</strong>”。<br>
2. 如果长周期是“缩量阴跌”，最新日继续缩量，则说明底部尚未探明。<br>
3. 简述核心宽基（如沪深300、创业板）当前是处于“寻底”、“企稳”还是“趋势走坏”阶段。</p>

<h3>六、🚨 波段风险雷达扫描</h3>
<p>请严格检查以下 4 项风险信号，并在报告中如实列出触发了哪些项：<br>
1. 【资金背离】指数上涨，但大盘资金或行业板块呈现净流出。<br>
2. 【情绪极值】涨停家数超过80家，或连板家数超过20家（高潮即退潮）。<br>
3. 【主线退潮】前期的热门板块在龙虎榜上出现大额净卖出，或资金流入的板块每天剧烈切换、毫无持续性。<br>
4. 【趋势破坏】大盘指数跌破20日均线（生命线），或放量收出中阴线。</p>

<h3>七、📊 铁血风控仓位建议</h3>
<p>请严格根据【波段风险雷达扫描】的结果，结合以下【绝对风控红线】给出最终仓位：<br>
<span style="color:red;">【绝对风控红线（必须遵守）】</span><br>
- 如果【宽基ETF量价趋势】中，核心宽基（如沪深300、创业板）出现了“放量下跌”，且大盘跌破20日线，<strong>建议仓位强制降至 10%-20% 或空仓</strong>。<br>
- 如果宽基ETF出现“缩量阴跌”，说明抛压减轻，但仍在寻底，<strong>建议仓位不超过 30%</strong>。<br>
- 触发【资金背离】或【主线退潮】任意2项及以上，<strong>建议仓位上限强制降至 20%-30%</strong>。<br>
- 只有在宽基ETF呈现“放量上涨”或“震荡企稳”、情绪健康（非极值）的情况下，才允许给出 50%-70% 的仓位。<br>
请先输出判断逻辑，最后单独一行用加粗标明最终结论。格式：<br><strong>最终建议仓位：XX%-XX%</strong></p>

<h3>八、📈 今日走势预测</h3>
<p>结合隔夜美股、日韩开盘、A股内部情绪，给出走势判断及关键支撑/压力位。若某项数据缺失，明确标注“数据缺失”。</p>

<h3>九、⚠️ 近期大事预警（必看）</h3>
<p>提取未来3-7天内最需关注的1-3件核心大事，并简要提示其对A股的可能影响。</p>

<h3>十、⚠️ 今日风险提示</h3>
<p>内容</p>

要求：
1. 语言精炼，每个板块不超过3条
2. 重要内容用 <strong>加粗</strong>
3. 建议仓位必须严格执行【绝对风控红线】。你要记住，在A股，避开主跌浪比抓住涨停板更重要。
4. 直接输出HTML，不要用代码块包裹
"""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
    resp = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data)
    result = resp.json()
    if "choices" not in result: raise ValueError(f"DeepSeek 异常: {result}")
    content = result["choices"][0]["message"]["content"]
    return content.replace("**", "").replace("```html", "").replace("```", "")


# ==========================================
# 四、HTML 渲染与推送
# ==========================================
def build_html_report(content):
    today = pd.Timestamp.now().strftime('%Y-%m-%d')
    return f"""
    <div style="font-family:'Microsoft YaHei',Arial,sans-serif;max-width:680px;margin:0 auto;padding:16px;background:#f7f8fa;">
        <div style="background:#1a1a2e;color:#fff;padding:14px 18px;border-radius:8px 8px 0 0;">
            <h2 style="margin:0;font-size:18px;">📰 {today} 财经内参</h2>
        </div>
        <div style="background:#fff;padding:18px;border-radius:0 0 8px 8px;line-height:1.8;color:#333;font-size:14px;">
            {content}
        </div>
        <p style="color:#999;font-size:12px;text-align:center;margin-top:12px;">由 AI 自动生成，仅供参考，不构成投资建议</p>
    </div>
    """

def send_to_wechat(token, title, content, topic=None):
    url = "http://www.pushplus.plus/send"
    data = {"token": token, "title": title, "content": content, "template": "html"}
    if topic: data["topic"] = topic
    print("推送结果:", requests.post(url, json=data).text)


# ==========================================
# 五、主程序入口
# ==========================================
if __name__ == "__main__":
#    if not is_trading_day():
#        print(f"今天 ({datetime.datetime.now().strftime('%Y-%m-%d')}) 非交易日，跳过推送。")
#        sys.exit(0)

    try:
        print("=== 开始获取多维度数据 ===")
        news_list = get_finance_news()
        market_index = get_market_index()
        market_fund = safe_fetch("大盘资金流向", get_market_fund_flow)
        sector_fund = safe_fetch("行业板块资金流向", get_sector_fund_flow)
        margin = safe_fetch("两融数据", get_margin_data)
        lhb = safe_fetch("龙虎榜", get_lhb_data)
        zt_stats = safe_fetch("涨跌停统计", get_zt_pool)
        macro = safe_fetch("宏观数据", get_macro_data)
        commodity = safe_fetch("大宗商品", get_commodity_data)
        asia_pacific = safe_fetch("亚太指数", get_asia_pacific_index)
        us_index = safe_fetch("美股指数", get_us_index)
        fed_calendar = safe_fetch("美联储日程", get_fed_calendar)
        earnings_calendar = safe_fetch("A股财报日历", get_earnings_calendar)
        key_events = safe_fetch("宏观关键节点", get_key_economic_events)
        etf_flow = safe_fetch("宽基ETF资金流向", get_broad_etf_flow)
        forecast = safe_fetch("机构预期", get_forecast_data)

        print("正在调用AI综合分析...")
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key: raise ValueError("未找到 DEEPSEEK_API_KEY")
        summary = summarize_with_ai(news_list, market_index, market_fund, sector_fund,
                                    margin, lhb, zt_stats, macro, commodity, forecast,
                                    asia_pacific, us_index, fed_calendar, earnings_calendar, key_events,
                                    etf_flow, api_key)

        print("正在生成报告...")
        title = "今日财经内参"
        content = build_html_report(summary)

        token = os.environ.get("PUSHPLUS_TOKEN")
        if not token: raise ValueError("未找到 PUSHPLUS_TOKEN")
        topic = os.environ.get("PUSHPLUS_TOPIC")
        send_to_wechat(token, title, content, topic)
        print("执行完毕！")
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc(); print(error_msg)
        token = os.environ.get("PUSHPLUS_TOKEN")
        if token: send_to_wechat(token, "⚠️ 脚本运行报错", f"<pre>{error_msg}</pre>")
        else: print("无法推送报错信息")
