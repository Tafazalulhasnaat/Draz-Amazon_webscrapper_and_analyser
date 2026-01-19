import os
import subprocess
import sys

def main():
    print("🚀 Initializing Price Tracker System...")
    
    # Get the path to the dashboard file
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.py")
    
    if not os.path.exists(dashboard_path):
        print("Error: dashboard.py not found!")
        return

    print("✅ Launching Dashboard...")
    print("👉 If the browser doesn't open, check the console for the URL.")
    
    # Run streamlit as a subprocess
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", dashboard_path])
    except KeyboardInterrupt:
        print("\n🛑 System stopped.")

if __name__ == "__main__":
    main()