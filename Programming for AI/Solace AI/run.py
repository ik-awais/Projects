#!/usr/bin/env python3
"""
SOLACE — Quick start script
Run this to start the backend on port 5000.
"""
import os, sys

# Make sure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Start the app
from app import app, db
with app.app_context():
    db.create_all()
    print("✓ Database initialised")

print("\n" + "═"*52)
print("   🌙  SOLACE — Emotionally Intelligent Companion")
print("═"*52)
print("   Backend  →  http://localhost:5000")
print("   Open the above URL in your browser")
print("═"*52 + "\n")

app.run(host="0.0.0.0", port=5000, debug=False)
