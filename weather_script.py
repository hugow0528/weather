import requests
import json
import datetime
import pytz

# ================= 配置區 =================
TG_TOKEN = "8780856101:AAHmuoXdAi50LjceLhzdTfXh-Ju2DGlM4E4"
TG_CHAT_ID = "7706163480" 
AI_API_KEY = "sk_FvxLKDYP4nNlPdKvXju8wL753iMB3u1T"
DEFAULT_LOCATION = "元朗公園"
# ==========================================

def log(msg):
    print(f"[{datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def get_weather_data():
    log("獲取天文台及空氣質素數據...")
    try:
        # 天文台數據
        curr_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc", timeout=20)
        fore_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc", timeout=20)
        
        # 空氣質素 (AQHI) - 攞元朗站
        aqhi_res = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=aqhi&lang=tc", timeout=20)
        
        curr_data = curr_res.json()
        fore_data = fore_res.json()
        aqhi_data = aqhi_res.json()
        
        # 1. 現時天氣
        temp_list = curr_data.get('temperature', {}).get('data', [])
        yl_temp = next((item['value'] for item in temp_list if item['place'] == DEFAULT_LOCATION), "N/A")
        humidity = curr_data.get('humidity', {}).get('data', [{}])[0].get('value', "N/A")
        warning = " ".join(curr_data.get('warningMessage', [])) or "暫無警告"
        uv_index = curr_data.get('uvindex', {}).get('data', [{}])[0].get('value', "無資料")
        
        # 2. 空氣質素 (AQHI)
        yl_aqhi = "未知"
        for item in aqhi_data.get('aqhi', []):
            if "元朗" in item['station']:
                yl_aqhi = item['aqhi']
        
        # 3. 未來三日預測 (含 PSR 降雨概率)
        forecast_list = []
        forecasts = fore_data.get('weatherForecast', [])
        for i in range(1, min(4, len(forecasts))): 
            f = forecasts[i]
            date_str = f.get('forecastDate', '00000000')
            formatted_date = f"{date_str[4:6]}/{date_str[6:8]}({f.get('week', '')})"
            t_range = f"{f['forecastMintemp']['value']}-{f['forecastMaxtemp']['value']}°C"
            psr = f.get('PSR', '未知') # 降雨概率
            desc = f.get('forecastWeather', '無描述')
            forecast_list.append(f"• <b>{formatted_date}</b>: {t_range} | 🌧️ 降雨概率: {psr}\n  <i>{desc}</i>")
        
        return {
            "location": DEFAULT_LOCATION,
            "temp": yl_temp,
            "humidity": humidity,
            "warning": warning,
            "uv": uv_index,
            "aqhi": yl_aqhi,
            "future": "\n".join(forecast_list)
        }
    except Exception as e:
        log(f"數據獲取失敗: {e}")
        raise

def ask_ai(weather):
    log("請求 AI 綜合決策建議...")
    prompt = f"""
    你係香港男仔生活助手。請用地道廣東話回覆。
    【今日數據】
    地點：{weather['location']}
    現在氣溫：{weather['temp']}度, 濕度：{weather['humidity']}%, 警告：{weather['warning']}
    紫外線指數：{weather['uv']}, 空氣質素(AQHI)：{weather['aqhi']}
    
    【未來三日預測】
    {weather['future']}
    
    指令：
    1. 唔好畀選擇題。
    2. 穿衣決策：(恤衫長/短袖, 長褲, 毛衣背心, 長袖毛衣, PE風褸, 校褸, 底衣/褲)。注意校褸20度以上唔著。
    3. 生活貼士：(根據濕度/UV/AQHI/PSR，決定「洗唔洗帶遮」、「要唔要查防曬」、「適唔適合體育堂/戶外跑」、「今日曬唔曬得衫」)。
    4. 禁止使用 * 或 Markdown。回覆要直接、果斷。
    """
    
    for model in ["gemini-fast", "openai-fast"]:
        try:
            res = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是一個果斷、貼心的香港生活顧問。回覆只使用 HTML 標籤（b, i, u）。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.4
                },
                timeout=20
            )
            return res.json()['choices'][0]['message']['content'].strip()
        except:
            continue
    return "AI 忙碌中，請自行決定。"

def send_telegram(text):
    log("發送 Telegram...")
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        log(f"TG 發送失敗: {r.text}")

if __name__ == "__main__":
    try:
        data = get_weather_data()
        advice = ask_ai(data)
        
        # 最終呈現畫面
        msg = f"<b>📍 {data['location']} 實用天氣提醒</b>\n"
        msg += f"🌡️ 現在: <b>{data['temp']}°C</b> | 💧 <b>{data['humidity']}%</b>\n"
        msg += f"☀️ UV: <b>{data['uv']}</b> | 😷 AQHI: <b>{data['aqhi']}</b>\n"
        msg += f"⚠️ {data['warning']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>🔮 未來三日預測 (降雨概率):</b>\n{data['future']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>💡 AI 綜合決策建議:</b>\n{advice}"
        
        send_telegram(msg)
        log("完成！")
    except Exception as e:
        log(f"最後出錯: {e}")
