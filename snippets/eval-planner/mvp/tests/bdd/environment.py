import sys
import os

def before_all(context):
    # Add backend source to path so we can import validation module
    # Assuming run from mvp/tests/bdd/
    backend_path = os.path.abspath(os.path.join(os.getcwd(), "../../source/backend"))
    sys.path.append(backend_path)
