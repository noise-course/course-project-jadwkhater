import os
import sys
import time
import random
import pickle
import subprocess
from pathlib import Path
from scapy.all import sniff
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
INTERFACE = "en0"          
CAPTURE_DURATION = 15      
OUTPUT_DIR = Path("final_dataset/soundcloud_low") # <--- SAVES TO low FOLDER
SAMPLES_TO_COLLECT = 1   
PLAYLISTS = [
    "https://soundcloud.com/carles-piles/sets/the-nutcracker-suite",
    "https://soundcloud.com/user-886126588/sets/swan-lake-tchaikovsky",
    "https://soundcloud.com/hanangobran/sets/classic",
    "https://soundcloud.com/saratology-2/sets/tchaikovsky-mozart-haydn-bach"
]

def ensure_sudo():
    if os.geteuid() != 0:
        print("🔒 Need root privileges. Relaunching with sudo...")
        subprocess.check_call(['sudo', sys.executable] + sys.argv)
        sys.exit()

class SoundCloudCapture:
    def __init__(self):
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.packets = []
        self.song_pool = [] 
        
        print("🔧 Configuring Chrome...")
        opts = Options()
        opts.add_argument("--disk-cache-size=1") 
        opts.add_argument("--media-cache-size=1")
        opts.add_argument("--disable-blink-features=AutomationControlled") 
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        self.driver.set_window_size(1280, 800) 

    def login_and_scrape(self):
        print("\n🔐 LOGIN STEP")
        self.driver.get(PLAYLISTS[0])
        
        print("="*60)
        print("   ⚠️  ACTION REQUIRED FOR low QUALITY:")
        print("   1. Log in.")
        print("   2. ACCEPT COOKIES.")
        print("   3. Click the 3 dots (...) or Settings -> Streaming Quality.")
        print("   4. SELECT 'low Quality (AAC 256kbps)'.")
        print("="*60)
        
        print("   ⏳ Waiting 60 seconds for you...")
        for i in range(60, 0, -1):
            if i % 10 == 0: print(f"   ⏳ {i}s...", end='\r')
            time.sleep(1)
            
        print("\n🔎 SCRAPING SONGS from playlists...")
        
        for pl_url in PLAYLISTS:
            try:
                self.driver.get(pl_url)
                time.sleep(3)
                self.driver.execute_script("window.scrollTo(0, 500);")
                time.sleep(1)
                
                # SoundCloud selector for track links
                elements = self.driver.find_elements(By.CSS_SELECTOR, 'a.trackItem__trackTitle')
                
                found_here = 0
                for elem in elements:
                    url = elem.get_attribute('href')
                    if url and "soundcloud.com" in url and url not in self.song_pool:
                        self.song_pool.append(url)
                        found_here += 1
                print(f"   found {found_here} songs...")
            except:
                pass

        self.song_pool = list(set(self.song_pool))
        random.shuffle(self.song_pool)
        print(f"✅ Total Song Pool: {len(self.song_pool)} songs!")

    def surgical_clear_cache(self):
        try:
            self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
            print("   ✨ Cache cleared!")
        except:
            pass

    def attempt_play_click(self):
        try:
            # Check if playing
            bottom_play = self.driver.find_element(By.CSS_SELECTOR, ".playControl")
            if "playing" in bottom_play.get_attribute("class"):
                return
            
            # Try Hero Button
            hero_btn = self.driver.find_element(By.CSS_SELECTOR, ".sc-button-play")
            hero_btn.click()
            print("   ▶️  Clicked Hero Play")
        except:
            try:
                # Try Bottom Bar
                bottom_play = self.driver.find_element(By.CSS_SELECTOR, ".playControl")
                bottom_play.click()
                print("   ▶️  Clicked Bottom Bar Play")
            except:
                pass

    def packet_callback(self, packet):
        if packet.haslayer('IP'):
            if packet.haslayer('TCP') or packet.haslayer('UDP'):
                if len(packet) > 60:
                    self.packets.append({'ts': float(packet.time), 'len': len(packet)})

    def capture_loop(self):
        count = 0
        
        while count < SAMPLES_TO_COLLECT:
            self.surgical_clear_cache()
            
            if not self.song_pool: break
            song_url = random.choice(self.song_pool)
            
            print(f"\n[SoundCloud low {count+1}/{SAMPLES_TO_COLLECT}]")
            
            self.driver.get(song_url)
            time.sleep(5)
            self.attempt_play_click()
            time.sleep(5)
            
            print(f"   🔴 Sniffing {CAPTURE_DURATION}s (TCP+UDP)...")
            self.packets = []
            try:
                sniff(iface=INTERFACE, timeout=CAPTURE_DURATION, prn=self.packet_callback, store=0)
            except Exception as e:
                continue

            pkt_count = len(self.packets)
            print(f"   ✅ Captured {pkt_count} packets. Saving...")
            
            with open(self.output_dir / f"sc_low_{int(time.time())}.pkl", "wb") as f:
                pickle.dump(self.packets, f)
            count += 1
            
        self.driver.quit()

if __name__ == "__main__":
    ensure_sudo()
    bot = SoundCloudCapture()
    bot.login_and_scrape()
    bot.capture_loop()