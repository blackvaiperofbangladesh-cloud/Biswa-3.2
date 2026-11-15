#!/usr/bin/env bash
# Optional manual static build. Native Vercel Django builds collect static assets automatically.
# It generates the staticfiles/ directory so WhiteNoise can serve them at runtime.

set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Build complete."
