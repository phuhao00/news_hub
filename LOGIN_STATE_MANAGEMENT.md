# Login State Management System

## Overview

The Login State Management System is a comprehensive solution for managing user login sessions across multiple social media platforms. It provides automated browser instance management, session persistence, and real-time login state detection.

## Features

### 🔐 Session Management
- Create and manage login sessions for multiple platforms
- Automatic session validation and expiration handling
- Persistent session storage with MongoDB and Redis caching
- Real-time login status detection and updates

### 🌐 Browser Instance Management
- Automated browser instance creation and management
- Platform-specific browser configurations
- Headless and non-headless browser support
- User data directory management for session persistence

### 📱 Supported Platforms
- 微博 (Weibo)
- 小红书 (Xiaohongshu)
- 抖音 (Douyin)
- 哔哩哔哩 (Bilibili)
- 知乎 (Zhihu)

### 🔄 Auto-Refresh & Real-time Updates
- Automatic login state detection every 30 seconds
- Real-time notifications for login status changes
- Smart refresh strategy to avoid unnecessary API calls
- Visual feedback for status changes

## Architecture

### Backend Components

#### Session Manager (`session_manager.py`)
- Handles session creation, validation, and lifecycle management
- Implements Redis caching for performance
- Manages session encryption and security

#### Browser Instance Manager (`browser_manager.py`)
- Creates and manages Playwright browser instances
- Implements platform-specific login detection
- Handles browser navigation and page interactions

#### Cookie Store (`cookie_store.py`)
- Manages cookie persistence across sessions
- Implements secure cookie storage and retrieval
- Handles cookie synchronization between browser instances

#### API Layer (`api.py`)
- RESTful API endpoints for session and browser management
- Request/response models with Pydantic validation
- Error handling and logging

### Frontend Components

#### Login State Management Page (`page.tsx`)
- React-based user interface for session management
- Real-time status updates and notifications
- Interactive browser instance controls
- Manual crawling task management

## API Endpoints

### Session Management

#### Create Session
```http
POST /api/login-state/sessions
Content-Type: application/json

{
  "user_id": "demo-user",
  "platform": "weibo",
  "browser_config": {
    "headless": false,
    "viewport": {"width": 1920, "height": 1080}
  },
  "session_timeout_hours": 24
}
```

#### Get Session
```http
GET /api/login-state/sessions/{session_id}
```

#### Update Session
```http
PUT /api/login-state/sessions/{session_id}
Content-Type: application/json

{
  "is_logged_in": true,
  "login_user": "username",
  "extend_hours": 12
}
```

#### List User Sessions
```http
GET /api/login-state/sessions?user_id=demo-user&platform=weibo
```

#### Delete Session
```http
DELETE /api/login-state/sessions/{session_id}
```

### Browser Instance Management

#### Create Browser Instance
```http
POST /api/login-state/browser-instances
Content-Type: application/json

{
  "session_id": "sess_abc123",
  "headless": false,
  "custom_config": {
    "viewport": {"width": 1920, "height": 1080}
  }
}
```

#### Navigate Browser
```http
POST /api/login-state/browser-instances/{instance_id}/navigate
Content-Type: application/json

{
  "url": "https://weibo.com/login"
}
```

#### Get Browser Instance
```http
GET /api/login-state/browser-instances/{instance_id}
```

#### Close Browser Instance
```http
DELETE /api/login-state/browser-instances/{instance_id}
```

### Manual Crawling

#### Create Crawl Task
```http
POST /api/login-state/crawl/create
Content-Type: application/json

{
  "url": "https://weibo.com/u/1234567890",
  "session_id": "sess_abc123",
  "extract_options": {
    "extract_images": true,
    "extract_links": true,
    "max_posts": 10
  },
  "save_to_db": true
}
```

#### Execute Crawl Task
```http
POST /api/login-state/crawl/{task_id}/execute
```

### Statistics

#### System Statistics
```http
GET /api/login-state/stats/system
```

Response:
```json
{
  "session_stats": {
    "active": 5,
    "total": 10
  },
  "browser_stats": {
    "running": 3,
    "total": 8
  },
  "crawl_stats": {
    "total_tasks": 25,
    "completed": 20,
    "failed": 2
  },
  "system_stats": {
    "total_cookies": 150
  }
}
```

## Setup Instructions

### Prerequisites

1. **Python 3.8+** with required packages:
   ```bash
   pip install -r crawler-service/requirements.txt
   ```

2. **Node.js 18+** for the frontend:
   ```bash
   npm install
   ```

3. **MongoDB** for session persistence
4. **Redis** for caching (optional but recommended)
5. **Playwright** browsers:
   ```bash
   playwright install
   ```

### Configuration

1. **Environment Variables**:
   ```bash
   # MongoDB
   MONGODB_URL=mongodb://localhost:27017
   MONGODB_DB=newshub
   
   # Redis (optional)
   REDIS_URL=redis://localhost:6379
   
   # API Configuration
   API_HOST=localhost
   API_PORT=8001
   ```

2. **Database Setup**:
   ```bash
   # Initialize MongoDB collections
   ./init-database.ps1
   ```

### Running the System

1. **Start All Services**:
   ```bash
   ./start-all.ps1
   ```

2. **Or Start Individual Services**:
   
   **Backend API**:
   ```bash
   cd crawler-service
   python main.py
   ```
   
   **Frontend**:
   ```bash
   npm run dev
   ```

3. **Access the Interface**:
   - Frontend: http://localhost:3000/login-state
   - API Documentation: http://localhost:8001/docs

## Usage Examples

### Basic Session Workflow

1. **Create a Session**:
   - Select a platform (e.g., Weibo)
   - Click "Create Session"
   - Session will be created with a unique ID

2. **Open Browser Instance**:
   - Click "Open Browser" for the created session
   - A browser window will open with the platform's login page

3. **Manual Login**:
   - Perform manual login in the browser window
   - The system will automatically detect login status
   - Session status will update to "Logged In"

4. **Verify Login Status**:
   - Click "Validate Status" to manually check login state
   - System provides real-time feedback

5. **Create Crawl Tasks**:
   - Use the logged-in session for manual crawling
   - Specify URLs and extraction options
   - Execute tasks with authenticated access

### Programmatic Usage

```python
import requests

# Create session
response = requests.post('http://localhost:8001/api/login-state/sessions', json={
    'user_id': 'demo-user',
    'platform': 'weibo',
    'browser_config': {'headless': False}
})
session = response.json()
session_id = session['session_id']

# Create browser instance
response = requests.post('http://localhost:8001/api/login-state/browser-instances', json={
    'session_id': session_id,
    'headless': False
})
browser = response.json()
instance_id = browser['instance_id']

# Navigate to login page
requests.post(f'http://localhost:8001/api/login-state/browser-instances/{instance_id}/navigate', json={
    'url': 'https://weibo.com/login'
})

# Check login status
response = requests.get(f'http://localhost:8001/api/login-state/sessions/{session_id}')
status = response.json()
print(f"Login status: {status['is_logged_in']}")
```

## Security Features

- **Session Encryption**: All session data is encrypted using Fernet encryption
- **Secure Cookie Storage**: Cookies are stored securely with encryption
- **Session Expiration**: Automatic session cleanup and expiration
- **User Isolation**: Sessions are isolated by user ID
- **Input Validation**: All API inputs are validated using Pydantic models

## Monitoring and Logging

- **Comprehensive Logging**: All operations are logged with appropriate levels
- **Error Tracking**: Detailed error messages and stack traces
- **Performance Metrics**: Session and browser instance statistics
- **Real-time Status**: Live status updates in the frontend interface

## Troubleshooting

### Common Issues

1. **Browser Instance Creation Fails**:
   - Ensure Playwright browsers are installed
   - Check system resources and permissions
   - Verify browser configuration parameters

2. **Login Detection Not Working**:
   - Check platform-specific detection rules
   - Verify browser instance is active
   - Ensure proper page navigation

3. **Session Persistence Issues**:
   - Verify MongoDB connection
   - Check Redis connectivity (if used)
   - Ensure proper database permissions

4. **API Connection Errors**:
   - Verify backend service is running on port 8001
   - Check firewall and network settings
   - Ensure proper CORS configuration

### Debug Mode

Enable debug logging by setting:
```bash
LOG_LEVEL=DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue in the GitHub repository
- Check the troubleshooting section above
- Review the API documentation at http://localhost:8001/docs