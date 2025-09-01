#!/bin/bash

# Setup script for Clean Architecture SaaS template

echo "🚀 Setting up Clean Architecture SaaS Template..."

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ Please update .env with your configuration"
fi

# Install Go dependencies
echo "📦 Installing Go dependencies..."
go mod download
go mod tidy

# Verify the setup
echo "🔍 Verifying setup..."
go mod verify

# Check if we can build the application
echo "🔨 Testing build..."
go build -o tmp/server ./cmd/server

# Verify build result
if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
    rm -f tmp/server
else
    echo "❌ Build failed!"
    exit 1
fi

# Run tests
echo "🧪 Running tests..."
go test ./...

echo ""
echo "🎉 Setup complete! Next steps:"
echo "1. Update your .env file with proper configuration"
echo "2. Start the development environment:"
echo "   docker-compose up -d"
echo "3. Or run locally:"
echo "   go run ./cmd/server"
echo ""
echo "📚 Check the README.md for detailed documentation"
