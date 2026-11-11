"""Optional preview adapter; normal users can run: streamlit run app.py."""
import argparse, subprocess, sys
p=argparse.ArgumentParser()
p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',default='8501');p.add_argument('--strictPort',action='store_true')
a=p.parse_args()
subprocess.run([sys.executable,'-m','streamlit','run','app.py','--server.address',a.host,'--server.port',a.port],check=True)
