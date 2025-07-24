#!/bin/bash
# NewsHub One-Click Startup Script (Linux/macOS)
# Start frontend, backend and crawler services

echo "=== NewsHub One-Click Startup Script ==="
echo "Starting all NewsHub application services..."

# Check if in correct directory
if [ ! -f "package.json" ]; then
    echo "Error: Please run this script in the NewsHub project root directory"
    exit 1
fi

# Function: Check if port is occupied
check_port() {
    local port=$1
    if command -v nc >/dev/null 2>&1; then
        nc -z localhost $port >/dev/null 2>&1
    elif command -v telnet >/dev/null 2>&1; then
        timeout 1 telnet localhost $port >/dev/null 2>&1
    else
        # Use lsof as fallback
        lsof -i :$port >/dev/null 2>&1
    fi
}

# Function: Wait for service to start
wait_for_service() {
    local port=$1
    local service_name=$2
    local timeout=${3:-30}
    
    echo "Waiting for $service_name to start (port $port)..."
    local elapsed=0
    
    while [ $elapsed -lt $timeout ]; do
        if check_port $port; then
            echo "✓ $service_name started"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    
    echo "✗ $service_name startup timeout"
    return 1
}

# Cleanup function
cleanup() {
    echo "\nStopping all services..."
    jobs -p | xargs -r kill
    echo "All services stopped"
    exit 0
}

# Set signal handling
trap cleanup SIGINT SIGTERM

# Check and install frontend dependencies
echo "\n1. Checking frontend dependencies..."
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
    if [ $? -ne 0 ]; then
        echo "Frontend dependencies installation failed"
        exit 1
    fi
fi

# Check and install crawler service dependencies
echo "\n2. Checking crawler service dependencies..."
cd crawler-service
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment and install dependencies
source .venv/bin/activate
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Crawler service dependencies installation failed"
    exit 1
fi
cd ..

# Check Go environment and backend dependencies
echo "\n3. Checking backend service..."
cd server
go mod tidy
if [ $? -ne 0 ]; then
    echo "Backend dependencies check failed"
    exit 1
fi
cd ..

# Start services
echo "\n4. Starting services..."

# Start backend service (port 8082)
echo "Starting backend service..."
cd server
go run main.go &
BACKEND_PID=$!
cd ..

# Wait for backend service to start
if ! wait_for_service 8082 "Backend Service"; then
    echo "Backend service startup failed, stopping all services"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# Start crawler service (port 8001)
echo "Starting crawler service..."
cd crawler-service
source .venv/bin/activate
python main.py &
CRAWLER_PID=$!
cd ..

# Wait for crawler service to start
if ! wait_for_service 8001 "Crawler Service"; then
    echo "Crawler service startup failed, stopping all services"
    kill $BACKEND_PID $CRAWLER_PID 2>/dev/null
    exit 1
fi

# Start frontend service (port 3001)
echo "Starting frontend service..."
npm run dev &
FRONTEND_PID=$!

# Wait for frontend service to start
if ! wait_for_service 3001 "Frontend Service"; then
    echo "Frontend service startup failed, stopping all services"
    kill $BACKEND_PID $CRAWLER_PID $FRONTEND_PID 2>/dev/null
    exit 1
fi

echo "\n=== All services started successfully! ==="
echo "Frontend service: http://localhost:3001"
echo "Backend service: http://localhost:8082"
echo "Crawler service: http://localhost:8001"
echo "\nPress Ctrl+C to stop all services"

# Wait for user interruption
wait