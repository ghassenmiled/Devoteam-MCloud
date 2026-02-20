#!/bin/bash

set -e

echo "🧹 Cleaning previous package..."
rm -f ../infra/functions.zip

echo "📦 Packaging Azure Functions (Python V2)..."

cd ../functions

# Important : zip depuis la racine du dossier functions
zip -r ../infra/functions.zip . > /dev/null

cd ..

echo "✅ Package created at infra/functions.zip"
