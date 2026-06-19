import sys
import os

# Add current directory and api directory to path to ensure modules are found correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.index import app

if __name__ == "__main__":
    app.run()
