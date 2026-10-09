import os
import akshare as ak
import pandas as pd
import requests

# ==========================================
# 第一步：获取行情数据
# ==========================================
def get_market_data():
    try:
        # 优先尝试东方财富接口
        print("尝试使用东方财富接口获取数据...")
        df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
    except Exception as e:
        # 失败则切换新浪财经接口
        print(f"东方财富接口失败: {e}")
        print("正在切换为新浪财经接口...")
        df = ak.stock_zh_index_spot_sina()
    
    # 筛选需要的列
    df = df[["代码", "名称", "最新价", "涨跌幅"]]
    
    # ⭐ 关键修改：只保留几个核心指数（防止内容过长被PushPlus拒收）
    # 这里筛选你想要的指数代码，比如上证指数(000001)、深证成指(399001)、创业板指(399006)等
    # 注意：不同接口的代码前缀可能不同，用"包含"匹配最稳妥
    target_names = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300"]
    df = df[df["名称"].isin(target_names)] 
    
    # 如果过滤后没数据（可能名称对不上），就只取前5行兜底
    if df.empty:
        df = df.head(5)

    return df
def build_html_report(df):
    # 提取日期
    today = pd.Timestamp.now().strftime('%Y-%m-%d')
    
    # 把DataFrame转换成HTML表格，并加上简单的红绿颜色样式
    html_table = df.to_html(index=False, border=0, justify='center')
    
    # 给涨跌幅加上颜色（简单粗暴的字符串替换法，也可用更复杂的CSS）
    # 因为PushPlus的HTML模板支持内联样式
    html_content = f"""
    <h3>📊 {today} 股市早报</h3>
    <p>以下是今日主要指数行情：</p>
    {html_table}
    <br>
    <p style="color:gray;font-size:12px;">此消息由AI助手自动生成，仅供参考。</p>
    """
    return html_content

# ==========================================
# 第三步：调用PushPlus推送
# ==========================================
def send_to_wechat(token, title, content):
    url = "http://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": title,
        "content": content,
        "template": "html"  # 注意这里是html，不能用txt
    }
    response = requests.post(url, json=data)
    print("推送结果:", response.text)

# ==========================================
# 主程序入口：按顺序执行
# ==========================================
if __name__ == "__main__":
    # 1. 获取数据
    print("正在获取数据...")
    df = get_market_data()
    
    # 2. 组装报告
    print("正在生成报告...")
    title = "今日股市早报"
    content = build_html_report(df)
    
    # 3. 从环境变量中读取 Token（千万不要写死在代码里）
    # 这里对应你在 GitHub Secrets 里设置的 PUSHPLUS_TOKEN
    token = os.environ.get("PUSHPLUS_TOKEN") 
    
    if not token:
        print("错误：未找到 PUSHPLUS_TOKEN 环境变量！")
    else:
        print("正在推送到微信...")
        send_to_wechat(token, title, content)
        print("执行完毕！")
