@echo off
REM Setup script for Clean Architecture SaaS template (Windows)

echo 🚀 Setting up Clean Architecture SaaS Template...

REM Create .env file if it doesn't exist
if not exist .env (
    echo 📝 Creating .env file from template...
    copy .env.example .env
    echo ✅ Please update .env with your configuration
)

REM Install Go dependencies
echo 📦 Installing Go dependencies...
go mod download
go mod tidy

REM Verify the setup
echo 🔍 Verifying setup...
go mod verify

REM Check if we can build the application
echo 🔨 Testing build...
if not exist tmp mkdir tmp
go build -o tmp\server.exe .\cmd\server

if %ERRORLEVEL% equ 0 (
    echo ✅ Build successful!
    del tmp\server.exe
) else (
    echo ❌ Build failed!
    exit /b 1
)

REM Run tests
echo 🧪 Running tests...
go test .\...

echo.
echo 🎉 Setup complete! Next steps:
echo 1. Update your .env file with proper configuration
echo 2. Start the development environment:
echo    docker-compose up -d
echo 3. Or run locally:
echo    go run .\cmd\server
echo.
echo 📚 Check the README.md for detailed documentation
