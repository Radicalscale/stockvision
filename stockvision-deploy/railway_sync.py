"""
Railway Data Sync Script
Uploads local CSV data directly to Railway using the Railway CLI.
Run this ONCE to do the initial full data upload.
After that, run_all_updates.ps1 auto-syncs on every pipeline run.
"""
import subprocess, sys, os

DEPLOY = os.path.dirname(os.path.abspath(__file__))

def run(cmd):
    print(f"  > {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout: print(result.stdout.strip())
    if result.stderr: print(result.stderr.strip(), file=sys.stderr)
    return result.returncode

print("=" * 60)
print("  Railway Volume Data Sync")
print("=" * 60)

# Check railway CLI is installed
if run("railway --version") != 0:
    print("\n❌ Railway CLI not found!")
    print("Install it: npm install -g @railway/cli")
    print("Then login:  railway login")
    sys.exit(1)

print("\nUploading processed CSVs to Railway volume...")
code = run(f'railway volume cp "{DEPLOY}\\data\\processed" /app/data/processed --recursive')
if code != 0:
    print("❌ Upload failed. Make sure you are linked to your Railway project.")
    print("   Run: railway link")
    sys.exit(1)

print("\nUploading raw CSVs to Railway volume...")
run(f'railway volume cp "{DEPLOY}\\data\\raw" /app/data/raw --recursive')

print("\n✅ Data sync complete! Railway will serve fresh data.")
