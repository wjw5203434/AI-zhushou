import os
import akshare as ak
import pandas as pd
import requests

# ==========================================
# 第一步：获取新闻
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

# ==========================================
# 第二步：获取大盘数据
# ==========================================
def get_market_data():
    try:
        df = ak.stock_zh_index_spot_sina()
        df = df[df["名称"].isin(["上证指数", "深证成指", "创业板指"])]
        return df.to_string(index=False)
    except Exception as e:
        return f"大盘数据获取失败: {e}"

# ==========================================
# 第三步：调用 AI 整理
# ==========================================
def summarize_with_ai(news_list, market_data, api_key):
    prompt = f"""你是一名专业A股策略分析师。以下是今日大盘数据和关键新闻，请整理成一份简洁的早报。

【今日大盘】
{market_data}

【关键新闻】
{chr(10).join(news_list)}

请严格按照以下HTML格式输出，不要使用Markdown语法（不要用**、#、-等符号），直接输出HTML标签：

<h3>一、宏观环境</h3>
<p>内容（不超过3条，每条用<br>分隔）</p>

<h3>二、科技巨头动态</h3>
<p>内容</p>

<h3>三、对A股可能的影响</h3>
<p>内容</p>

<h3>四、今日风险提示</h3>
<p>内容</p>

要求：
1. 结合大盘数据给出对市场情绪的判断
2. 语言精炼，每个板块不超过3条
3. 重要内容用 <strong>加粗</strong>
4. 直接输出HTML，不要用代码块包裹，不要有任何额外说明文字
"""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5
    }
    resp = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data)
    result = resp.json()
    if "choices" not in result:
        raise ValueError(f"DeepSeek 返回异常: {result}")

    content = result["choices"][0]["message"]["content"]
    # 清洗可能残留的 Markdown 标记
    content = content.replace("**", "").replace("```html", "").replace("```", "")
    return content

# ==========================================
# 第四步：生成 HTML 报告
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
# 第五步：推送到微信
# ==========================================
def send_to_wechat(token, title, content):
    url = "http://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": title,
        "content": content,
        "template": "html"
    }
    response = requests.post(url, json=data)
    print("推送结果:", response.text)

# ==========================================
# 主程序入口
# ==========================================
if __name__ == "__main__":
    try:
        # 1. 获取新闻
        print("正在获取宏观与科技新闻...")
        news_list = get_finance_news()

        # 2. 获取大盘数据
        print("正在获取大盘数据...")
        market_data = get_market_data()

        # 3. 调用 AI 整理（传入大盘数据）
        print("正在调用AI整理...")
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("错误：未找到 DEEPSEEK_API_KEY 环境变量！")
        summary = summarize_with_ai(news_list, market_data, api_key)

        # 4. 组装报告（直接传 summary 字符串，不要加 []）
        print("正在生成报告...")
        title = "今日财经内参"
        content = build_html_report(summary)

        # 5. 推送
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
