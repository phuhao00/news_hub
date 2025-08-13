# NewsHub Database Initialization Script
# Used to initialize MongoDB database and insert sample data

# Check if Docker is installed
function Test-Docker {
    try {
        docker --version | Out-Null
        return $true
    }
    catch {
        Write-Host "Error: Docker not found, please install Docker Desktop first" -ForegroundColor Red
        return $false
    }
}

# Check if MongoDB is already running on any port
function Test-MongoDBRunning {
    try {
        # Check if any MongoDB container is running
        $runningMongo = docker ps --filter "ancestor=mongo:7" --format "{{.Names}} {{.Ports}}" | Where-Object { $_ -ne "" }
        
        if ($runningMongo) {
            Write-Host "Found running MongoDB container(s):" -ForegroundColor Green
            $runningMongo | ForEach-Object { Write-Host "  $_" -ForegroundColor Cyan }
            
            # Extract port numbers from running containers
            $runningPorts = @()
            $runningMongo | ForEach-Object {
                if ($_ -match "0\.0\.0\.0:(\d+)->27017") {
                    $runningPorts += [int]$matches[1]
                }
            }
            
            # Test each running port
            foreach ($port in $runningPorts) {
                try {
                    Write-Host "Testing connection to MongoDB on port $port..." -ForegroundColor Yellow
                    $testConnection = docker run --rm mongo:7 mongosh "mongodb://host.docker.internal:$port" --eval "db.adminCommand('ping')" --quiet 2>$null
                    if ($testConnection -match "ok.*1" -or $testConnection -match '"ok"\s*:\s*1') {
                        Write-Host "Successfully connected to MongoDB on port $port" -ForegroundColor Green
                        return $port
                    }
                } catch {
                    Write-Host "Failed to connect to port $port" -ForegroundColor Gray
                }
            }
        }
        return $false
    }
    catch {
        return $false
    }
}

# Start MongoDB container
function Start-MongoContainer {
    Write-Host "Checking MongoDB status..." -ForegroundColor Yellow
    
    # First check if MongoDB is already running
    $runningPort = Test-MongoDBRunning
    if ($runningPort) {
        Write-Host "MongoDB is already running on port $runningPort, using existing instance" -ForegroundColor Green
        $script:mongoPort = $runningPort
        return $true
    }
    
    Write-Host "No running MongoDB found, checking container status..." -ForegroundColor Yellow
    $containerExists = docker ps -a --filter "name=newshub-mongodb" --format "{{.Names}}" | Select-String "newshub-mongodb"
    
    if ($containerExists) {
        Write-Host "MongoDB container already exists, starting..." -ForegroundColor Blue
        docker start newshub-mongodb
    } else {
        Write-Host "Creating and starting MongoDB container..." -ForegroundColor Blue
        docker run -d --name newshub-mongodb -p 27015:27017 -v "${PWD}/init-mongo.js:/docker-entrypoint-initdb.d/init-mongo.js" mongo:7
    }
    
    $script:mongoPort = 27015
    
    # Wait for MongoDB to start
    Write-Host "Waiting for MongoDB to start..." -ForegroundColor Yellow
    $maxAttempts = 30
    $attempt = 0
    
    do {
        Start-Sleep -Seconds 2
        $attempt++
        $isReady = docker exec newshub-mongodb mongosh --eval "db.adminCommand('ping')" 2>$null
        if ($isReady) {
            Write-Host "MongoDB is ready!" -ForegroundColor Green
            return $true
        }
        Write-Host "Waiting... ($attempt/$maxAttempts)" -ForegroundColor Gray
    } while ($attempt -lt $maxAttempts)
    
    Write-Host "MongoDB startup timeout" -ForegroundColor Red
    return $false
}

# Execute database initialization
function Initialize-Database {
    Write-Host "Executing database initialization..." -ForegroundColor Yellow
    
    try {
        # Check if we're using an existing MongoDB instance
        if ($script:mongoPort -ne 27015) {
            Write-Host "Using existing MongoDB instance on port $($script:mongoPort), skipping container-based initialization" -ForegroundColor Yellow
            
            # Connect to existing MongoDB and initialize
            $initScript = Get-Content "init-mongo.js" -Raw
            $tempInitFile = "temp-init.js"
            $initScript | Out-File -FilePath $tempInitFile -Encoding UTF8
            
            docker run --rm -v "${PWD}/${tempInitFile}:/tmp/init.js" mongo:7 mongosh "mongodb://host.docker.internal:$($script:mongoPort)/newshub" /tmp/init.js
            Remove-Item $tempInitFile -Force
        } else {
            # Execute initialization script for our own container
            docker exec newshub-mongodb mongosh newshub /docker-entrypoint-initdb.d/init-mongo.js
        }
        
        # Insert sample data
        Write-Host "Inserting sample data..." -ForegroundColor Blue
        
        # Create sample data script file
        $sampleScript = @'
db = db.getSiblingDB("newshub");

db.creators.insertMany([
    {
        username: "tech_blogger",
        platform: "weibo",
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        username: "news_reporter", 
        platform: "douyin",
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        username: "lifestyle_vlogger",
        platform: "xiaohongshu",
        created_at: new Date(),
        updated_at: new Date()
    }
]);

print("Sample data inserted successfully!");
'@
        
        $tempFile = "init-sample-data.js"
        $sampleScript | Out-File -FilePath $tempFile -Encoding UTF8
        
        if ($script:mongoPort -ne 27015) {
            # Use external MongoDB instance
            docker run --rm -v "${PWD}/${tempFile}:/tmp/sample.js" mongo:7 mongosh "mongodb://host.docker.internal:$($script:mongoPort)/newshub" /tmp/sample.js
        } else {
            # Copy to container and execute
            docker cp $tempFile newshub-mongodb:/tmp/init-sample-data.js
            docker exec newshub-mongodb mongosh newshub /tmp/init-sample-data.js
            docker exec newshub-mongodb rm /tmp/init-sample-data.js
        }
        
        # Clean up temporary files
        Remove-Item $tempFile -Force
        
        Write-Host "Database initialization completed!" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "Database initialization failed: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Display database status
function Show-DatabaseStatus {
    Write-Host "\n=== Database Status ===" -ForegroundColor Cyan
    
    try {
        if ($script:mongoPort -ne 27015) {
            # Use external MongoDB instance
            Write-Host "Database list:" -ForegroundColor Yellow
            docker run --rm mongo:7 mongosh "mongodb://host.docker.internal:$($script:mongoPort)" --eval "show dbs"
            
            Write-Host "\nCollection list:" -ForegroundColor Yellow
            docker run --rm mongo:7 mongosh "mongodb://host.docker.internal:$($script:mongoPort)/newshub" --eval "show collections"
            
            Write-Host "\nCreator data:" -ForegroundColor Yellow
            docker run --rm mongo:7 mongosh "mongodb://host.docker.internal:$($script:mongoPort)/newshub" --eval "db.creators.find().pretty()"
        } else {
            # Display database information from our container
            Write-Host "Database list:" -ForegroundColor Yellow
            docker exec newshub-mongodb mongosh --eval "show dbs"
            
            Write-Host "\nCollection list:" -ForegroundColor Yellow
            docker exec newshub-mongodb mongosh newshub --eval "show collections"
            
            Write-Host "\nCreator data:" -ForegroundColor Yellow
            docker exec newshub-mongodb mongosh newshub --eval "db.creators.find().pretty()"
        }
        
    }
    catch {
        Write-Host "Unable to get database status: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Main function
function Main {
    Write-Host "=== NewsHub Database Initialization ===" -ForegroundColor Cyan
    
    # Check Docker
    if (-not (Test-Docker)) {
        exit 1
    }
    
    # Start MongoDB container
    if (-not (Start-MongoContainer)) {
        Write-Host "MongoDB container startup failed" -ForegroundColor Red
        exit 1
    }
    
    # Initialize database
    if (Initialize-Database) {
        Show-DatabaseStatus
        Write-Host "\nDatabase initialization completed successfully!" -ForegroundColor Green
        Write-Host "MongoDB connection address: mongodb://localhost:$($script:mongoPort)" -ForegroundColor Cyan
        Write-Host "Database name: newshub" -ForegroundColor Cyan
    } else {
        Write-Host "Database initialization failed" -ForegroundColor Red
        exit 1
    }
}

# Error handling
try {
    Main
}
catch {
    Write-Host "Script execution error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}