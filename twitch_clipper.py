import os
import time
import json
import requests
import subprocess
import openai
from selenium import webdriver
from selenium.webdriver.common.by import By
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import websocket
import pandas as pd
import streamlit as st
from datetime import datetime
from threading import Thread
from dotenv import load_dotenv

# ===== CONFIGURATION =====
load_dotenv()
TWITCH_CLIENT_ID = os.getenv("xmwoztxm7o1l70jsv71qgd6sath1a0")
TWITCH_OAUTH_TOKEN = os.getenv("w855tu8wgfa0hj6knng8du7utw5vix")
OPENAI_API_KEY = os.getenv("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")
CHROME_DRIVER_PATH = os.getenv("C:\Users\Philip\Downloads\twitch-clipper\chromedriver.exe")
TARGET_STREAMER = "Thetylilshow"  # Change to your target streamer

# ===== DASHBOARD SETUP =====
def performance_dashboard():
    """Streamlit dashboard to track clip performance"""
    st.set_page_config(page_title="Twitch Clip Analytics")
    st.title("📈 Twitch Clip Performance Dashboard")
    
    if os.path.exists("performance.csv"):
        df = pd.read_csv("performance.csv")
        st.dataframe(df)
        
        # Show metrics
        col1, col2 = st.columns(2)
        col1.metric("Total Clips", len(df))
        col2.metric("Avg Views", f"{df['Views'].mean():.0f}")
        
        # Show chart
        st.line_chart(df.set_index("Date")["Views"])
    else:
        st.warning("No clips uploaded yet!")

# ===== REAL-TIME TWITCH CHAT =====
class TwitchChatMonitor:
    def __init__(self):
        self.ws = websocket.WebSocketApp(
            "wss://irc-ws.chat.twitch.tv:443",
            on_message=self.on_message,
            on_open=self.on_open
        )
        
    def on_open(self, ws):
        """Authenticate with Twitch chat"""
        ws.send(f"PASS oauth:{TWITCH_OAUTH_TOKEN}")
        ws.send(f"NICK justinfan12345")  # Anonymous username
        ws.send(f"JOIN #{TARGET_STREAMER.lower()}")
        print(f"👂 Listening to {TARGET_STREAMER}'s chat...")

    def on_message(self, ws, message):
        """Process chat messages"""
        try:
            if "PRIVMSG" in message:
                username = message.split("!")[0][1:]
                content = message.split(f"#{TARGET_STREAMER} :")[1].strip()
                
                if self.is_hype_moment(content):
                    print(f"🔥 Hype detected! Clipping...")
                    self.create_and_upload_clip()

        except Exception as e:
            print(f"Chat error: {e}")

    def is_hype_moment(self, message):
        """Hybrid detection: Keywords + GPT-4"""
        hype_keywords = ["POG", "OMG", "CLUTCH", "LET'S GO", "HOLY"]
        if any(word in message.upper() for word in hype_keywords):
            return True
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{
                    "role": "user",
                    "content": f"Is this Twitch chat message hype? Reply YES/NO: '{message}'"
                }],
                api_key=OPENAI_API_KEY
            )
            return "YES" in response.choices[0].message.content
        except:
            return False

# ===== CORE FUNCTIONALITY =====
def create_and_upload_clip():
    """Full clipping workflow"""
    try:
        # 1. Get stream info
        stream_data = requests.get(
            f"https://api.twitch.tv/helix/streams?user_login={TARGET_STREAMER}",
            headers={
                "Client-ID": TWITCH_CLIENT_ID,
                "Authorization": f"Bearer {TWITCH_OAUTH_TOKEN}"
            }
        ).json()
        
        if not stream_data["data"]:
            print("Streamer is offline")
            return

        # 2. Create clip
        clip_id = requests.post(
            "https://api.twitch.tv/helix/clips",
            headers={
                "Client-ID": TWITCH_CLIENT_ID,
                "Authorization": f"Bearer {TWITCH_OAUTH_TOKEN}"
            },
            params={"broadcaster_id": stream_data["data"][0]["user_id"]}
        ).json()["data"][0]["id"]

        # 3. Download clip
        clip_url = get_clip_url(clip_id)
        subprocess.run([
            "ffmpeg", "-i", clip_url, "-c", "copy", "raw_clip.mp4"
        ], check=True)

        # 4. Edit clip
        edited_file = edit_clip("raw_clip.mp4")

        # 5. Upload to TikTok
        if upload_to_tiktok(edited_file):
            log_performance(edited_file)

    except Exception as e:
        print(f"Error in workflow: {e}")

def edit_clip(input_path):
    """Add captions and effects"""
    output_path = f"edited_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
    video = VideoFileClip(input_path)
    txt = TextClip("HYPE MOMENT!", fontsize=50, color='white', 
                  font='Arial-Bold', stroke_color='black', stroke_width=2)
    txt = txt.set_position(('center', 'bottom')).set_duration(video.duration)
    CompositeVideoClip([video, txt]).write_videofile(output_path)
    return output_path

def upload_to_tiktok(video_path):
    """Selenium-based uploader"""
    try:
        driver = webdriver.Chrome(CHROME_DRIVER_PATH)
        driver.get("https://www.tiktok.com/upload")
        time.sleep(5)
        
        driver.find_element(By.XPATH, "//input[@type='file']").send_keys(
            os.path.abspath(video_path)
        )
        time.sleep(10)
        
        caption = f"🔥 {TARGET_STREAMER} HYPE! #twitch #gaming"
        driver.find_element(By.XPATH, "//div[@role='textbox']").send_keys(caption)
        driver.find_element(By.XPATH, "//button[contains(text(),'Post')]").click()
        time.sleep(15)
        return True
    except Exception as e:
        print(f"Upload failed: {e}")
        return False

# ===== UTILITIES =====
def log_performance(clip_path):
    """Record to CSV"""
    new_entry = pd.DataFrame([{
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Clip": clip_path,
        "Views": 0,  # Update manually or via API later
        "Likes": 0
    }])
    
    if os.path.exists("performance.csv"):
        new_entry.to_csv("performance.csv", mode='a', header=False, index=False)
    else:
        new_entry.to_csv("performance.csv", index=False)

def get_clip_url(clip_id):
    """Fetch clip URL from Twitch"""
    response = requests.get(
        f"https://api.twitch.tv/helix/clips?id={clip_id}",
        headers={
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {TWITCH_OAUTH_TOKEN}"
        }
    )
    return response.json()["data"][0]["thumbnail_url"].replace("-preview-480x272.jpg", ".mp4")

# ===== MAIN EXECUTION =====
if __name__ == "__main__":
    # Start dashboard in separate thread
    Thread(target=performance_dashboard).start()
    
    # Start chat monitor
    monitor = TwitchChatMonitor()
    monitor.ws.run_forever()