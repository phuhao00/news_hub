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

# Start MongoDB container
function Start-MongoContainer {
    Write-Host "Checking MongoDB container status..." -ForegroundColor Yellow
    
    $containerExists = docker ps -a --filter "name=newshub-mongodb" --format "{{.Names}}" | Select-String "newshub-mongodb"
    
    if ($containerExists) {
        Write-Host "MongoDB container already exists, starting..." -ForegroundColor Blue
        docker start newshub-mongodb
    } else {
        Write-Host "Creating and starting MongoDB container..." -ForegroundColor Blue
        docker run -d --name newshub-mongodb -p 27017:27017 -v "${PWD}/init-mongo.js:/docker-entrypoint-initdb.d/init-mongo.js" mongo:latest
    }
    
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
        # Execute initialization script
        docker exec newshub-mongodb mongosh newshub /docker-entrypoint-initdb.d/init-mongo.js
        
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
        
        # Copy to container and execute
        docker cp $tempFile newshub-mongodb:/tmp/init-sample-data.js
        docker exec newshub-mongodb mongosh newshub /tmp/init-sample-data.js
        
        # Clean up temporary files
        Remove-Item $tempFile -Force
        docker exec newshub-mongodb rm /tmp/init-sample-data.js
        
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
        # Display database information
        Write-Host "Database list:" -ForegroundColor Yellow
        docker exec newshub-mongodb mongosh --eval "show dbs"
        
        Write-Host "\nCollection list:" -ForegroundColor Yellow
        docker exec newshub-mongodb mongosh newshub --eval "show collections"
        
        Write-Host "\nCreator data:" -ForegroundColor Yellow
        docker exec newshub-mongodb mongosh newshub --eval "db.creators.find().pretty()"
        
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
        Write-Host "MongoDB connection address: mongodb://localhost:27017" -ForegroundColor Cyan
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