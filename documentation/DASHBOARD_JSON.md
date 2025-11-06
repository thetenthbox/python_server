# Dashboard JSON Data Structure

## Endpoint

```
GET /api/dashboard
Authorization: Bearer {token}
```

Returns comprehensive JSON with all system data for web frontend consumption.

## Complete JSON Response

```json
{
  "timestamp": "2025-11-06T18:30:45.123456",
  "user_id": "alice",
  "is_admin": true,
  
  "job_statistics": {
    "total": 150,
    "pending": 5,
    "running": 3,
    "completed": 135,
    "failed": 5,
    "cancelled": 2
  },
  
  "user_statistics": {
    "alice": {
      "total": 50,
      "pending": 2,
      "running": 1,
      "completed": 45,
      "failed": 2
    },
    "bob": {
      "total": 30,
      "pending": 1,
      "running": 1,
      "completed": 28,
      "failed": 0
    }
  },
  
  "node_statistics": [
    {
      "node_id": 0,
      "is_busy": true,
      "total_queue_time": 450
    },
    {
      "node_id": 1,
      "is_busy": false,
      "total_queue_time": 0
    }
  ],
  
  "queue_information": [
    {
      "node_id": 0,
      "queue_size": 3,
      "queue_time_seconds": 450,
      "is_busy": true,
      "current_job": {
        "job_id": "abc-123",
        "user_id": "alice",
        "competition_id": "comp-001",
        "started_at": "2025-11-06T18:25:00"
      }
    },
    {
      "node_id": 1,
      "queue_size": 0,
      "queue_time_seconds": 0,
      "is_busy": false,
      "current_job": null
    }
  ],
  
  "active_jobs": [
    {
      "job_id": "abc-123",
      "user_id": "alice",
      "competition_id": "comp-001",
      "status": "running",
      "node_id": 0,
      "expected_time": 300,
      "created_at": "2025-11-06T18:20:00",
      "started_at": "2025-11-06T18:25:00",
      "queue_position": null
    },
    {
      "job_id": "def-456",
      "user_id": "bob",
      "competition_id": "comp-002",
      "status": "pending",
      "node_id": 2,
      "expected_time": 180,
      "created_at": "2025-11-06T18:26:00",
      "started_at": null,
      "queue_position": 1
    }
  ],
  
  "recent_jobs": [
    {
      "job_id": "xyz-789",
      "user_id": "alice",
      "competition_id": "comp-001",
      "status": "completed",
      "node_id": 2,
      "created_at": "2025-11-06T18:10:00",
      "started_at": "2025-11-06T18:12:00",
      "completed_at": "2025-11-06T18:17:00",
      "duration_seconds": 300
    }
  ],
  
  "health_metrics": {
    "node_utilization_percent": 37.5,
    "average_queue_time_seconds": 225.5,
    "total_active_jobs": 8,
    "success_rate_percent": 94.5,
    "jobs_last_24h": 150
  }
}
```

## Data Fields Explanation

### Root Level
- `timestamp` - Current server time (ISO format)
- `user_id` - Authenticated user ID
- `is_admin` - Boolean, true if user has admin privileges

### job_statistics
Counts of all jobs (filtered by user if not admin):
- `total` - All jobs ever
- `pending` - Jobs waiting in queue
- `running` - Currently executing jobs
- `completed` - Successfully finished jobs
- `failed` - Jobs that failed
- `cancelled` - User-cancelled jobs

### user_statistics (Admin only)
Per-user job counts. Empty object `{}` for regular users.

### node_statistics
Array of 8 GPU nodes:
- `node_id` - Node identifier (0-7)
- `is_busy` - Boolean, true if node is running a job
- `total_queue_time` - Total seconds of jobs queued for this node

### queue_information
Detailed queue state per node:
- `node_id` - Node identifier (0-7)
- `queue_size` - Number of jobs waiting in queue
- `queue_time_seconds` - Total wait time for queued jobs
- `is_busy` - Boolean, node currently executing
- `current_job` - Job currently running (null if none)
  - `job_id` - Job identifier
  - `user_id` - Who submitted it
  - `competition_id` - Which competition
  - `started_at` - When it started (ISO format)

### active_jobs
All pending or running jobs:
- `job_id` - Unique identifier
- `user_id` - Job owner
- `competition_id` - Competition this job is for
- `status` - "pending" or "running"
- `node_id` - Assigned GPU node
- `expected_time` - Expected duration in seconds
- `created_at` - When submitted (ISO format)
- `started_at` - When started executing (null if pending)
- `queue_position` - Position in queue (null if running)

### recent_jobs
Last 10 completed/failed/cancelled jobs:
- `job_id` - Unique identifier
- `user_id` - Job owner
- `competition_id` - Competition
- `status` - "completed", "failed", or "cancelled"
- `node_id` - Which node ran it
- `created_at` - Submission time
- `started_at` - Start time
- `completed_at` - End time
- `duration_seconds` - How long it took (null if not completed)

### health_metrics
System-wide statistics:
- `node_utilization_percent` - % of nodes currently busy (0-100)
- `average_queue_time_seconds` - Avg wait time across all queues
- `total_active_jobs` - Count of pending + running jobs
- `success_rate_percent` - % of last 100 jobs that completed successfully
- `jobs_last_24h` - Jobs submitted in last 24 hours

## Usage Examples

### Fetch Dashboard Data

```bash
curl -H "Authorization: Bearer your_token" \
     http://localhost:8001/api/dashboard
```

### Python

```python
import requests

response = requests.get(
    'http://localhost:8001/api/dashboard',
    headers={'Authorization': 'Bearer your_token'}
)

data = response.json()

# What's running?
running = [j for j in data['active_jobs'] if j['status'] == 'running']
print(f"Running: {len(running)} jobs")

# What's in queue?
queued = [j for j in data['active_jobs'] if j['status'] == 'pending']
print(f"Queued: {len(queued)} jobs")

# Who's in queue?
users_in_queue = {j['user_id'] for j in queued}
print(f"Users: {users_in_queue}")
```

### JavaScript

```javascript
fetch('/api/dashboard', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
.then(res => res.json())
.then(data => {
  // Display on web dashboard
  console.log('Active jobs:', data.active_jobs);
  console.log('Node utilization:', data.health_metrics.node_utilization_percent);
  
  // Update UI
  document.getElementById('running-count').textContent = 
    data.job_statistics.running;
  document.getElementById('queued-count').textContent = 
    data.job_statistics.pending;
});
```

## For Web Dashboard Frontend

### Recommended Polling
```javascript
// Fetch every 3-5 seconds
setInterval(() => {
  fetchDashboard();
}, 3000);
```

### Key Data Points to Display

**System Overview:**
- Node utilization bar chart
- Active jobs count
- Success rate gauge

**Queue Status:**
- Per-node queue sizes
- Who's running what
- Queue positions

**Job Lists:**
- Running jobs table
- Queued jobs table
- Recent completions

**User Stats (Admin):**
- Per-user activity
- Top users by job count

## Response Size

Typical response: 5-50KB depending on:
- Number of active jobs
- Number of users (admin view)
- Recent job history

## Notes

- All timestamps in ISO 8601 format (UTC)
- All durations in seconds
- Empty arrays `[]` if no data
- `null` for optional fields with no value
- Regular users see filtered data (own jobs only)
- Admins see all system data
