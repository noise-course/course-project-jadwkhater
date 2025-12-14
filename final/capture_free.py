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
OUTPUT_DIR = Path("final_dataset/free_playlist")
SAMPLES_TO_COLLECT = 50    
PLAYLIST_URL = "https://open.spotify.com/playlist/2AIyLES2xJfPa6EOxmKySl?si=x73MEKZxREaqoFDePMhCjQ"

def ensure_sudo():
    if os.geteuid() != 0:
        print("🔒 Need root privileges. Relaunching with sudo...")
        subprocess.check_call(['sudo', sys.executable] + sys.argv)
        sys.exit()

class PlaylistCapture:
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
        self.driver.get(PLAYLIST_URL)
        print("   ⚠️  PLEASE LOG IN MANUALLY WITHIN 60 SECONDS...")
        
        for i in range(60, 0, -1):
            if i % 10 == 0: print(f"   ⏳ {i}s...", end='\r')
            time.sleep(1)
            
        print("\n🔎 SCRAPING SONGS...")
        for _ in range(3):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
        elements = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/track/"]')
        for elem in elements:
            url = elem.get_attribute('href')
            if url and url not in self.song_pool:
                self.song_pool.append(url)
                
        self.song_pool = list(set(self.song_pool))
        random.shuffle(self.song_pool)
        print(f"✅ Found {len(self.song_pool)} songs!")

    def surgical_clear_cache(self):
        try:
            self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
            print("   ✨ Cache cleared!")
        except:
            pass

    def packet_callback(self, packet):
        # Capture TCP and UDP
        if packet.haslayer('IP'):
            if packet.haslayer('TCP') or packet.haslayer('UDP'):
                if len(packet) > 60:
                    self.packets.append({'ts': float(packet.time), 'len': len(packet)})

    def capture_loop(self):
        count = 0
        
        while count < SAMPLES_TO_COLLECT:
            # 1. Clear Cache
            self.surgical_clear_cache()
            
            if not self.song_pool: break
            song_url = random.choice(self.song_pool)
            
            print(f"\n[Session {count+1}/{SAMPLES_TO_COLLECT}]")
            
            # 2. Single Load (No clicks, no double-tap)
            self.driver.get(song_url)
            
            # 3. Wait for UI and Buffer (9 seconds total)
            time.sleep(9)
            
            # 4. Capture
            print(f"   🔴 Sniffing {CAPTURE_DURATION}s (TCP+UDP)...")
            self.packets = []
            try:
                sniff(iface=INTERFACE, timeout=CAPTURE_DURATION, prn=self.packet_callback, store=0)
            except Exception as e:
                continue

            # 5. Save Everything (No filtering)
            pkt_count = len(self.packets)
            print(f"   ✅ Captured {pkt_count} packets. Saving...")
            with open(self.output_dir / f"free_{int(time.time())}.pkl", "wb") as f:
                pickle.dump(self.packets, f)
            count += 1
            
        self.driver.quit()

if __name__ == "__main__":
    ensure_sudo()
    bot = PlaylistCapture()
    bot.login_and_scrape()
    bot.capture_loop()