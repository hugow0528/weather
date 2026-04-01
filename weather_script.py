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
    now = datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] {msg}")

def safe_get_json(url, name):
    try:
        log(f"正在獲取 {name}...")
        res = requests.get(url, timeout=20)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        log(f"警告: {name} 獲取失敗 ({e})")
        return None

def get_weather_data():
    curr_data = safe_get_json("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc", "即時天氣")
    fore_data = safe_get_json("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc", "九天預測")
    aqhi_data = safe_get_json("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=aqhi&lang=tc", "空氣質素")
    
    # 預設數值
    result = {
        "location": DEFAULT_LOCATION,
        "temp": "N/A", "humidity": "N/A", "warning": "暫無資料",
        "uv": "無資料", "aqhi": "未知", "future": "暫無預測資料",
        "timestamp": datetime.datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S (%A)')
    }

    # 解析即時天氣
    if curr_data:
        temp_list = curr_data.get('temperature', {}).get('data', [])
        result["temp"] = next((item['value'] for item in temp_list if item['place'] == DEFAULT_LOCATION), "N/A")
        result["humidity"] = curr_data.get('humidity', {}).get('data', [{}])[0].get('value', "N/A")
        result["warning"] = " ".join(curr_data.get('warningMessage', [])) or "暫無警告"
        uv_data = curr_data.get('uvindex', {}).get('data', [])
        if uv_data: result["uv"] = uv_data[0].get('value', "無資料")

    # 解析空氣質素 (AQHI)
    if aqhi_data:
        for item in aqhi_data.get('aqhi', []):
            if "元朗" in item['station']:
                result["aqhi"] = item['aqhi']

    # 解析未來預測
    if fore_data:
        forecast_list = []
        forecasts = fore_data.get('weatherForecast', [])
        for i in range(1, min(4, len(forecasts))): 
            f = forecasts[i]
            date_str = f.get('forecastDate', '00000000')
            formatted_date = f"{date_str[4:6]}/{date_str[6:8]}({f.get('week', '')})"
            t_range = f"{f.get('forecastMintemp',{}).get('value')}-{f.get('forecastMaxtemp',{}).get('value')}°C"
            psr = f.get('PSR', '未知')
            desc = f.get('forecastWeather', f.get('forecastForecast', '無描述'))
            forecast_list.append(f"• <b>{formatted_date}</b>: {t_range} | 🌧️ {psr}\n  <i>{desc}</i>")
        result["future"] = "\n".join(forecast_list)

    return result

def ask_ai(weather):
    log("請求 AI 綜合決策建議...")
    prompt = f"""
    你係香港男仔生活助手。請用地道廣東話回覆。唔好用 Markdown 符號（禁止 * ）。
    地點：{weather['location']}
    現在氣溫：{weather['temp']}度, 濕度：{weather['humidity']}%, 警告：{weather['warning']}
    紫外線：{weather['uv']}, AQHI：{weather['aqhi']}
    未來三日預測：
    {weather['future']}
    
    指令：
    1. 穿衣決策：(限用:恤衫長/短袖,長褲,毛衣背心,長袖毛衣,PE風褸,校褸,底衣/褲)。20度以上唔好叫我著校褸。要果斷決策，唔好畀選擇。
    2. 生活貼士：(要唔要帶遮、要唔要防曬、適唔適合戶外運動、曬唔曬得衫)。
    """
    
    for model in ["gemini-fast", "openai-fast"]:
        try:
            res = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你係果斷嘅香港生活顧問，回覆只使用 HTML 標籤 <b>, <i>。唔好開場白。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.4
                },
                timeout=20
            )
            return res.json()['choices'][0]['message']['content'].strip()
        except:
            continue
    return "AI 暫時未能提供建議。"

def send_telegram(text):
    log("發送 Telegram...")
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        log(f"TG 失敗: {r.text}")

if __name__ == "__main__":
    try:
        data = get_weather_data()
        advice = ask_ai(data)
        
        # 建立最終訊息
        msg = f"🗓️ <b>報告時間: {data['timestamp']}</b>\n"
        msg += f"📍 <b>{data['location']} 實用資訊</b>\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"🌡️ 現在: <b>{data['temp']}°C</b> | 💧 <b>{data['humidity']}%</b>\n"
        msg += f"☀️ UV: <b>{data['uv']}</b> | 😷 AQHI: <b>{data['aqhi']}</b>\n"
        msg += f"⚠️ {data['warning']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>🔮 未來三日 (降雨概率):</b>\n{data['future']}\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"<b>💡 AI 綜合決策建議:</b>\n{advice}"
        
        send_telegram(msg)
        log("腳本執行完成！")
    except Exception as e:
        log(f"嚴重錯誤: {e}")
