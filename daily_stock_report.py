import os
import time
import datetime
import akshare as ak
import pandas as pd
import requests

# ==========================================
# 工具函数：带重试的安全获取
# ==========================================
def safe_fetch(name, func, default="暂无数据", retries=3, delay=5):
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
# 资金面数据（东方财富免费API直调）
# ==========================================
def get_market_fund_flow():
    """大盘资金流向（东方财富免费API直调，取最近3个交易日）"""
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": "1.000001",  # 上证指数
        "secid2": "0.399001", # 深证成指
        "klt": "101",         # 日线
        "lmt": "0",           # 不限条数
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        klines = data.get("data", {}).get("klines", [])
        if not klines:
            return "大盘主力资金数据暂不可用"

        lines = []
        for k in klines[-3:]:
            parts = k.split(",")
            date = parts[0]
            # 主力净流入（元）转亿元
            main_net = float(parts[1]) / 100000000
            direction = "流入" if main_net > 0 else "流出"
            lines.append(f"{date}：主力净{direction} {abs(main_net):.0f}亿")
        return "大盘主力资金流向（近3日）：\n" + "\n".join(lines)
    except Exception as e:
        print(f"东方财富大盘资金流API调用失败: {e}")
        return "大盘主力资金数据暂不可用"


def get_sector_fund_flow():
    """行业板块资金流向排名（东方财富免费API直调，取前5流入/流出）"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",  # 获取100条数据用于排序
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f62",  # 按主力净流入排序
        "fs": "m:90+t:2",  # 行业板块
        "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87"
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("diff", [])
        if not items:
            return "板块资金流向数据暂不可用"

        df = pd.DataFrame(items)
        # 按主力净流入净额排序
        df_sorted = df.sort_values("f62", ascending=False)
        top_in = df_sorted.head(5)
        top_out = df_sorted.tail(5)

        lines = ["【资金流入前5板块】"]
        for _, row in top_in.iterrows():
            name = row.get("f14", "")
            net = row.get("f62", 0) / 100000000
            lines.append(f"  {name}：{net:.1f}亿")
        lines.append("【资金流出前5板块】")
        for _, row in top_out.iterrows():
            name = row.get("f14", "")
            net = row.get("f62", 0) / 100000000
            lines.append(f"  {name}：{net:.1f}亿")
        return "\n".join(lines)
    except Exception as e:
        print(f"东方财富板块资金流API调用失败: {e}")
        return "板块资金流向数据暂不可用"


# ... (其他函数保持不变，如 get_margin_data, get_lhb_data, get_zt_pool, 等) ...


# ==========================================
# 主程序入口（需确认调用方式）
# ==========================================
if __name__ == "__main__":
    try:
        # ... 前面的代码 ...

        print("正在获取大盘资金流向...")
        market_fund = safe_fetch("大盘资金流向", get_market_fund_flow)

        print("正在获取行业板块资金流向...")
        sector_fund = safe_fetch("行业板块资金流向", get_sector_fund_flow)

        # ... 后面的代码 ...

    except Exception as e:
        # ... 错误处理 ...
