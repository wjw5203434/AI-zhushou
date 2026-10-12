import os
import akshare as ak
import pandas as pd
import requests

# ==========================================
# 第一步：获取行情数据
# ==========================================
def get_finance_news():
    news_list = []
    keywords = ["美联储", "加息", "英伟达", "美光", "半导体", "AI", "算力", "政策", "国务院", "央行", "降准", "降息"]

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
def summarize_with_ai(news_list, api_key):
    prompt = f"""你是一名专业A股策略分析师。以下是我筛选出的今日关键新闻，请整理成一份简洁的早报，包含：
1. 宏观环境（美联储、国内政策等）
2. 科技巨头动态（英伟达、美光等）
3. 对A股可能的影响（利好/利空哪些板块）
4. 今日风险提示

新闻列表：
{chr(10).join(news_list)}

请用中文输出，每个板块不超过3条，语言精炼。"""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5
    }
    resp = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data)
    return resp.json()["choices"][0]["message"]["content"]
def build_html_report(news_list):
    today = pd.Timestamp.now().strftime('%Y-%m-%d')
    html_items = "".join(f"<li style='margin-bottom:10px;'>{item}</li>" for item in news_list)
    html_content = f"""
    <h3>📰 {today} 关键信息链</h3>
    <ul style='line-height:1.8;'>{html_items}</ul>
    <p style='color:gray;font-size:12px;'>此消息由AI助手自动生成，仅供参考。</p>
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
# ==========================================
# 主程序入口：按顺序执行
# ==========================================
if __name__ == "__main__":
    try:
        # 1. 获取新闻数据
        print("正在获取宏观与科技新闻...")
        news_list = get_finance_news()

        # 2. 调用 AI 整理
        print("正在调用AI整理...")
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("错误：未找到 DEEPSEEK_API_KEY 环境变量！")
        summary = summarize_with_ai(news_list, api_key)

        # 3. 组装报告（注意这里传的是 [summary]）
        print("正在生成报告...")
        title = "今日财经内参"
        content = build_html_report([summary])

        # 4. 从环境变量中读取 Token
        token = os.environ.get("PUSHPLUS_TOKEN")
        if not token:
            raise ValueError("错误：未找到 PUSHPLUS_TOKEN 环境变量！")

        print("正在推送到微信...")
        send_to_wechat(token, title, content)
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
