"""
OpenShift S2I entry point.
This file sits at the project root so S2I can find it.
It simply imports the FastAPI app from the backend package.
"""
from backend.main import app  # noqa: F401
