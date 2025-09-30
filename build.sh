#!/usr/bin/env bash
# Build script for Render
# This script is executed during the build process

# Install dependencies
pip install -r requirements.txt

# Note: Database initialization moved to app startup since persistent disk is only available at runtime