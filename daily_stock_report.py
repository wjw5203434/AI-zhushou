import os
import akshare as ak
import pandas as pd
import requests

# ==========================================
# 第一步：获取行情数据
# ==========================================
def get_finance_news():
    """获取宏观政策与科技巨头相关新闻"""
    news_list = []
    
    try:
        # 1. 百度经济新闻（宏观政策方向）
        print("正在获取百度经济新闻...")
        df_econ = ak.news_economic_baidu()
        for _, row in df_econ.head(8).iterrows():
            news_list.append(f"【宏观】{row.get('标题', '')} — {row.get('摘要', '')[:80]}")
    except Exception as e:
        print(f"百度经济新闻获取失败: {e}")
    
    try:
        # 2. 央视新闻（国内政策方向）
        print("正在获取央视新闻...")
        df_cctv = ak.news_cctv()
        for _, row in df_cctv.head(5).iterrows():
            news_list.append(f"【政策】{row.get('title', '')} — {row.get('content', '')[:80]}")
    except Exception as e:
        print(f"央视新闻获取失败: {e}")
    
    # 兜底：如果两个源都失败，给一条提示
    if not news_list:
        news_list.append("今日新闻源暂时不可用，请检查数据接口。")
    
    return news_list
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
        # 1. 获取新闻数据（注意这里改成了 get_finance_news）
        print("正在获取宏观与科技新闻...")
        news_list = get_finance_news()
        
        # 2. 组装报告
        print("正在生成报告...")
        title = "今日关键信息链"
        content = build_html_report(news_list)
        
        # 3. 从环境变量中读取 Token
        token = os.environ.get("PUSHPLUS_TOKEN") 
        
        if not token:
            raise ValueError("错误：未找到 PUSHPLUS_TOKEN 环境变量！")
            
        print("正在推送到微信...")
        send_to_wechat(token, title, content)
        print("执行完毕！")
        
    except Exception as e:
        # 如果出错，把错误信息也推送到微信
        import traceback
        error_msg = traceback.format_exc()
        print(error_msg)
        
        token = os.environ.get("PUSHPLUS_TOKEN")
        if token:
            send_to_wechat(token, "⚠️ 脚本运行报错", f"<pre>{error_msg}</pre>")
        else:
            print("连 token 都没取到，无法推送报错信息")
