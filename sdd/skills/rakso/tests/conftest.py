import sys
import os

# Add src to the Python path
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
print(f"CONFTEST LOADED, adding to path: {src_path}")
sys.path.insert(0, src_path)
print(f"Current sys.path: {sys.path}")
