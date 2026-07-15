#!/bin/bash
# OpenShift S2I run script for the backend
exec uvicorn backend.main:app --host 0.0.0.0 --port 8080
