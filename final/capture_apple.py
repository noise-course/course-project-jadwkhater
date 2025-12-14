import os
import sys
import time
import subprocess
import pickle
from pathlib import Path
from scapy.all import sniff

# --- CONFIGURATION ---
INTERFACE = "en0"          
CAPTURE_DURATION = 15      
OUTPUT_DIR = Path("final_dataset/apple_desktop_low") # <--- SAVES TO LOW
SAMPLES_TO_COLLECT = 20    

def ensure_sudo():
    if os.geteuid() != 0:
        print("🔒 Need root privileges. Relaunching with sudo...")
        subprocess.check_call(['sudo', sys.executable] + sys.argv)
        sys.exit()

class AppleMusicDesktopCapture:
    def __init__(self):
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.packets = []

    def applescript_command(self, cmd):
        """Sends a command to the Music app via AppleScript"""
        full_cmd = f'tell application "Music" to {cmd}'
        subprocess.run(["osascript", "-e", full_cmd], capture_output=True)

    def packet_callback(self, packet):
        # Capture TCP/UDP on the interface
        if packet.haslayer('IP'):
            if packet.haslayer('TCP') or packet.haslayer('UDP'):
                if len(packet) > 60:
                    self.packets.append({'ts': float(packet.time), 'len': len(packet)})

    def capture_loop(self):
        print(f"\n🎧 Connected to Apple Music Desktop App (LOW QUALITY).")
        print(f"📂 Saving to: {self.output_dir}")
        print("   (Make sure your Playlist is queued in the Music App!)\n")

        count = 0
        while count < SAMPLES_TO_COLLECT:
            
            print(f"\n[Session {count+1}/{SAMPLES_TO_COLLECT}]")
            
            # --- 1. PAUSE FOR CACHE CLEARING ---
            # Stop music first so cache doesn't fill up while you wait
            self.applescript_command("pause")
            
            print("="*50)
            print("   ⚠️  PAUSED FOR MANUAL CACHE CLEAR")
            print("   1. Go to Finder/Terminal and clear your cache.")
            print("   2. Ensure Music App is still Open.")
            input("   ⌨️  Press ENTER when ready to capture...")
            print("="*50)

            # --- 2. START NEXT TRACK ---
            print("   ⏭️  Skipping to next track...")
            self.applescript_command("play next track")
            
            # Wait for buffering (Low quality buffers fast, but let's give it 3s)
            time.sleep(3)
            
            # --- 3. CAPTURE ---
            print(f"   🔴 Sniffing {CAPTURE_DURATION}s...")
            self.packets = []
            try:
                sniff(iface=INTERFACE, timeout=CAPTURE_DURATION, prn=self.packet_callback, store=0)
            except Exception as e:
                print(f"Error: {e}")
                continue
            
            # --- 4. SAVE ---
            pkt_count = len(self.packets)
            print(f"   ✅ Captured {pkt_count} packets. Saving...")
            
            with open(self.output_dir / f"apple_low_{int(time.time())}.pkl", "wb") as f:
                pickle.dump(self.packets, f)
            
            count += 1
            
        self.applescript_command("pause")
        print("\n🎉 Done! Music paused.")

if __name__ == "__main__":
    ensure_sudo()
    bot = AppleMusicDesktopCapture()
    bot.capture_loop()