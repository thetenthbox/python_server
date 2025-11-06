# Dashboard API

## Overview

The `/api/dashboard` endpoint provides comprehensive real-time system statistics including job states, queue information, node utilization, and health metrics.

## Endpoint

```
GET /api/dashboard
```

**Authorization Required:** Yes (Bearer token)

## Access Control

- **Regular Users:** See only their own jobs and statistics
- **Admin Users:** See all jobs and system-wide statistics

## Response Structure

```json
{
  "timestamp": "2025-11-06T18:30:45.123456",
  "user_id": "alice",
  "is_admin": false,
  "job_statistics": { ... },
  "user_statistics": { ... },
  "node_statistics": [ ... ],
  "queue_information": [ ... ],
  "active_jobs": [ ... ],
  "recent_jobs": [ ... ],
  "health_metrics": { ... }
}
```

## Response Fields

### Job Statistics
```json
"job_statistics": {
  "total": 150,
  "pending": 5,
  "running": 3,
  "completed": 135,
  "failed": 5,
  "cancelled": 2
}
```

### User Statistics (Admin Only)
```json
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
}
```

### Node Statistics
```json
"node_statistics": [
  {
    "node_id": 0,
    "is_busy": true,
    "total_queue_time": 450
  },
  {
    "node_id": 1,
    "is_busy": false,
    "total_queue_time": 120
  }
  // ... nodes 2-7
]
```

### Queue Information
```json
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
  // ... nodes 2-7
]
```

### Active Jobs
Currently running or pending jobs:

```json
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
    "node_id": 0,
    "expected_time": 180,
    "created_at": "2025-11-06T18:26:00",
    "started_at": null,
    "queue_position": 1
  }
]
```

### Recent Jobs
Last 10 jobs (completed, failed, or cancelled):

```json
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
  // ... 9 more recent jobs
]
```

### Health Metrics
System-wide health indicators:

```json
"health_metrics": {
  "node_utilization_percent": 37.5,
  "average_queue_time_seconds": 225.5,
  "total_active_jobs": 8,
  "success_rate_percent": 94.5,
  "jobs_last_24h": 150
}
```

## Usage Examples

### Regular User Dashboard

```python
import requests

BASE_URL = "http://localhost:8001"
TOKEN = "alice_token"

headers = {'Authorization': f'Bearer {TOKEN}'}
response = requests.get(f"{BASE_URL}/api/dashboard", headers=headers)

dashboard = response.json()

print(f"Your Jobs:")
print(f"  Total: {dashboard['job_statistics']['total']}")
print(f"  Running: {dashboard['job_statistics']['running']}")
print(f"  Pending: {dashboard['job_statistics']['pending']}")
print(f"  Completed: {dashboard['job_statistics']['completed']}")

print(f"\nActive Jobs:")
for job in dashboard['active_jobs']:
    status = job['status']
    competition = job['competition_id']
    if status == 'running':
        print(f"  Running: {competition} on node {job['node_id']}")
    else:
        print(f"  Pending: {competition} (position {job['queue_position']})")
```

### Admin System Monitoring

```python
import requests

BASE_URL = "http://localhost:8001"
ADMIN_TOKEN = "admin_token"

headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
response = requests.get(f"{BASE_URL}/api/dashboard", headers=headers)

dashboard = response.json()

# System health
health = dashboard['health_metrics']
print(f"System Health:")
print(f"  Node Utilization: {health['node_utilization_percent']}%")
print(f"  Active Jobs: {health['total_active_jobs']}")
print(f"  Success Rate: {health['success_rate_percent']}%")
print(f"  Jobs (24h): {health['jobs_last_24h']}")

# Per-user statistics
print(f"\nUser Activity:")
for user_id, stats in dashboard['user_statistics'].items():
    print(f"  {user_id}: {stats['running']} running, {stats['pending']} pending")

# Node status
print(f"\nNode Status:")
for queue in dashboard['queue_information']:
    node = queue['node_id']
    status = "BUSY" if queue['is_busy'] else "FREE"
    queue_size = queue['queue_size']
    print(f"  Node {node}: {status} ({queue_size} in queue)")
    
    if queue['current_job']:
        job = queue['current_job']
        print(f"    Current: {job['user_id']} - {job['competition_id']}")
```

### Live Monitoring Loop

```python
import requests
import time
from datetime import datetime

BASE_URL = "http://localhost:8001"
TOKEN = "admin_token"
headers = {'Authorization': f'Bearer {TOKEN}'}

while True:
    response = requests.get(f"{BASE_URL}/api/dashboard", headers=headers)
    dashboard = response.json()
    
    # Clear screen (Unix/Mac)
    print("\033[2J\033[H")
    
    # Header
    print("="*60)
    print(f"GPU Job Queue Dashboard - {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)
    
    # System health
    health = dashboard['health_metrics']
    print(f"\n📊 System Health:")
    print(f"  Utilization:  {health['node_utilization_percent']}%")
    print(f"  Active Jobs:  {health['total_active_jobs']}")
    print(f"  Success Rate: {health['success_rate_percent']}%")
    
    # Nodes
    print(f"\n🖥️  GPU Nodes:")
    for queue in dashboard['queue_information']:
        node = queue['node_id']
        status = "🟢 FREE" if not queue['is_busy'] else "🔴 BUSY"
        queue_size = queue['queue_size']
        print(f"  Node {node}: {status}  Queue: {queue_size}")
        
        if queue['current_job']:
            job = queue['current_job']
            print(f"           Running: {job['competition_id']} ({job['user_id']})")
    
    # Active jobs
    print(f"\n⚡ Active Jobs ({len(dashboard['active_jobs'])}):")
    for job in dashboard['active_jobs'][:5]:  # Show top 5
        status_icon = "▶️" if job['status'] == 'running' else "⏸️"
        print(f"  {status_icon} {job['competition_id'][:20]:<20} {job['user_id']:<10} Node {job['node_id']}")
    
    # Refresh every 5 seconds
    time.sleep(5)
```

### Web Dashboard Data Fetching

```javascript
// JavaScript for web dashboard
async function fetchDashboard() {
    const response = await fetch('/api/dashboard', {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
    });
    
    const dashboard = await response.json();
    
    // Update UI
    document.getElementById('total-jobs').textContent = dashboard.job_statistics.total;
    document.getElementById('running-jobs').textContent = dashboard.job_statistics.running;
    document.getElementById('utilization').textContent = 
        dashboard.health_metrics.node_utilization_percent + '%';
    
    // Update node grid
    updateNodeGrid(dashboard.queue_information);
    
    // Update active jobs table
    updateActiveJobsTable(dashboard.active_jobs);
}

// Refresh every 3 seconds
setInterval(fetchDashboard, 3000);
```

## Use Cases

### 1. User Monitoring
**Goal:** Check your job status and queue position

```python
dashboard = get_dashboard(user_token)

# Find your pending jobs
for job in dashboard['active_jobs']:
    if job['status'] == 'pending':
        print(f"Job {job['job_id']} in position {job['queue_position']}")
```

### 2. Admin System Overview
**Goal:** Monitor system health and user activity

```python
dashboard = get_dashboard(admin_token)

# Check if system is overloaded
if dashboard['health_metrics']['node_utilization_percent'] > 80:
    print("⚠️  High utilization!")

# Find power users
user_stats = dashboard['user_statistics']
top_users = sorted(user_stats.items(), 
                   key=lambda x: x[1]['total'], 
                   reverse=True)[:3]

print("Top 3 users:", [u[0] for u in top_users])
```

### 3. Queue Management
**Goal:** Find least busy node for manual scheduling

```python
dashboard = get_dashboard(admin_token)

# Find node with shortest queue
best_node = min(dashboard['queue_information'], 
                key=lambda q: q['queue_time_seconds'])

print(f"Least busy: Node {best_node['node_id']}")
```

### 4. Performance Analysis
**Goal:** Calculate average job duration

```python
dashboard = get_dashboard(admin_token)

# Get average duration from recent jobs
durations = [
    j['duration_seconds'] 
    for j in dashboard['recent_jobs'] 
    if j['duration_seconds']
]

avg_duration = sum(durations) / len(durations)
print(f"Average job duration: {avg_duration:.1f}s")
```

### 5. Alert System
**Goal:** Detect and alert on issues

```python
dashboard = get_dashboard(admin_token)

# Check for issues
health = dashboard['health_metrics']

if health['success_rate_percent'] < 90:
    send_alert("Low success rate!")

if health['total_active_jobs'] > 50:
    send_alert("Too many active jobs!")

if health['node_utilization_percent'] < 20:
    send_alert("Low utilization - nodes idle")
```

## Response Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | Success | Dashboard data returned |
| 401 | Unauthorized | Missing or invalid token |
| 500 | Server Error | Internal error fetching data |

## Rate Limiting

Dashboard endpoint has relaxed rate limits:
- **Regular users:** 60 requests/minute
- **Admin users:** 120 requests/minute

Suitable for live monitoring applications.

## Performance

**Response Time:** ~50-200ms depending on database size

**Optimizations:**
- Query optimization with indexes
- Cached node statistics
- Limited result sets (last 10/100 jobs)

## Best Practices

### For Regular Users
1. Poll every 5-10 seconds for live monitoring
2. Focus on `active_jobs` for your current work
3. Use `health_metrics.total_active_jobs` to gauge system load

### For Admins
1. Monitor `health_metrics` for system health
2. Check `user_statistics` for usage patterns
3. Watch `node_utilization_percent` for capacity planning
4. Use `queue_information` for load balancing

### For Developers
1. Cache dashboard data client-side (3-5 sec)
2. Use WebSockets for real-time updates (future enhancement)
3. Implement exponential backoff on errors
4. Show loading states during fetch

## Limitations

- Shows last 10 recent jobs only
- Success rate based on last 100 completed jobs
- No historical trends (add time-series later)
- No filtering options (all or nothing)

## Future Enhancements

- [ ] Time-series data for graphs
- [ ] Customizable time ranges
- [ ] Export to CSV/JSON
- [ ] WebSocket support for real-time updates
- [ ] Filtering and sorting options
- [ ] Aggregated statistics (hourly/daily)
- [ ] Performance benchmarks

## Related Endpoints

- `/api/jobs` - List jobs with filters
- `/api/nodes` - Detailed node statistics
- `/api/status/{job_id}` - Individual job status

## Support

For issues or questions about the dashboard:
1. Check that your token is valid
2. Verify you have appropriate permissions
3. Review server logs for errors
4. Check database connectivity

---

**Version:** 1.0  
**Last Updated:** 2025-11-06

