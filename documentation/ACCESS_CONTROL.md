# Access Control & User Privileges

## Overview

The GPU Job Queue Server implements role-based access control with two user types:
- **Regular Users**: Can only access their own jobs and resources
- **Admin Users**: Have elevated privileges to manage all system resources

## User Types

### Regular User

Regular users have restricted access limited to their own resources.

**Capabilities:**
- ✅ Submit jobs for execution
- ✅ View status of their own jobs
- ✅ View results of their own jobs
- ✅ Cancel their own jobs (pending or running)
- ✅ List their own jobs

**Restrictions:**
- ❌ Cannot view other users' jobs
- ❌ Cannot access other users' results
- ❌ Cannot cancel other users' jobs
- ❌ Cannot list all system jobs

**Token Creation:**
```bash
python3 token_manager.py create <user_id> <token_string>
```

### Admin User

Admin users have full system access and can manage all resources.

**Capabilities:**
- ✅ Submit jobs for execution
- ✅ View status of ANY job (all users)
- ✅ View results of ANY job (all users)
- ✅ Cancel ANY job (all users)
- ✅ List ALL jobs from all users
- ✅ Monitor entire system state

**Token Creation:**
```bash
python3 token_manager.py create <admin_id> <token_string> --admin
```

## API Endpoint Access Control

### Submit Job: `POST /api/submit`

**Regular User:**
- ✅ Can submit jobs with their own user_id
- ❌ Cannot submit jobs on behalf of other users
- Token must match the user_id in job configuration

**Admin User:**
- ✅ Can submit jobs with their own user_id
- ❌ Cannot submit jobs on behalf of other users (same as regular users)
- Token must match the user_id in job configuration

**Example:**
```python
# Regular user submitting job
files = {
    'code': ('solution.py', code_content, 'text/x-python'),
    'config_file': ('config.json', json.dumps({
        'competition_id': 'comp-001',
        'project_id': 'proj-001',
        'user_id': 'alice',  # Must match token owner
        'expected_time': 60,
        'token': 'alice_token'
    }), 'application/json')
}
response = requests.post('http://localhost:8001/api/submit', files=files)
```

### Job Status: `GET /api/status/{job_id}`

**Regular User:**
- ✅ Can view their own job status
- ❌ Returns 403 Forbidden for other users' jobs

**Admin User:**
- ✅ Can view ANY job status
- ✅ No restrictions on job_id

**Headers Required:**
```
Authorization: Bearer <token>
```

**Response Codes:**
- `200 OK` - Successfully retrieved status
- `401 Unauthorized` - Missing/invalid token
- `403 Forbidden` - User attempting to view another user's job
- `404 Not Found` - Job doesn't exist

**Example:**
```python
# Regular user viewing own job
headers = {'Authorization': 'Bearer alice_token'}
response = requests.get(
    'http://localhost:8001/api/status/alice-job-123',
    headers=headers
)
# Success: 200

# Regular user trying to view Bob's job
response = requests.get(
    'http://localhost:8001/api/status/bob-job-456',
    headers=headers
)
# Denied: 403

# Admin viewing any job
headers = {'Authorization': 'Bearer admin_token'}
response = requests.get(
    'http://localhost:8001/api/status/bob-job-456',
    headers=headers
)
# Success: 200
```

### Job Results: `GET /api/results/{job_id}`

**Regular User:**
- ✅ Can retrieve their own job results
- ❌ Returns 403 Forbidden for other users' results

**Admin User:**
- ✅ Can retrieve ANY job results
- ✅ No restrictions on job_id

**Headers Required:**
```
Authorization: Bearer <token>
```

**Response Codes:**
- `200 OK` - Successfully retrieved results
- `401 Unauthorized` - Missing/invalid token
- `403 Forbidden` - User attempting to view another user's results
- `404 Not Found` - Job doesn't exist

**Example:**
```python
# Admin retrieving any user's results
headers = {'Authorization': 'Bearer admin_token'}
response = requests.get(
    'http://localhost:8001/api/results/alice-job-123',
    headers=headers
)
# Success: 200
print(response.json()['stdout'])  # Contains results.jsonl
```

### Cancel Job: `POST /api/cancel/{job_id}`

**Regular User:**
- ✅ Can cancel their own pending/running jobs
- ❌ Returns 403 Forbidden when cancelling other users' jobs

**Admin User:**
- ✅ Can cancel ANY pending/running job
- ✅ No restrictions on job_id

**Headers Required:**
```
Authorization: Bearer <token>
```

**Response Codes:**
- `200 OK` - Successfully cancelled
- `400 Bad Request` - Job already completed/failed/cancelled
- `401 Unauthorized` - Missing/invalid token
- `403 Forbidden` - User attempting to cancel another user's job
- `404 Not Found` - Job doesn't exist

**Example:**
```python
# Regular user cancelling own job
headers = {'Authorization': 'Bearer alice_token'}
response = requests.post(
    'http://localhost:8001/api/cancel/alice-job-123',
    headers=headers
)
# Success: 200

# Regular user trying to cancel Bob's job
response = requests.post(
    'http://localhost:8001/api/cancel/bob-job-456',
    headers=headers
)
# Denied: 403

# Admin cancelling any job
headers = {'Authorization': 'Bearer admin_token'}
response = requests.post(
    'http://localhost:8001/api/cancel/bob-job-456',
    headers=headers
)
# Success: 200
```

### List Jobs: `GET /api/jobs`

**Regular User:**
- ✅ Automatically filtered to show only their jobs
- ✅ Cannot override filter to see other users' jobs
- User_id filter parameter is ignored (forced to token owner)

**Admin User:**
- ✅ Can see ALL jobs from ALL users
- ✅ Can optionally filter by user_id
- ✅ Can optionally filter by status

**Headers Required:**
```
Authorization: Bearer <token>
```

**Query Parameters:**
- `user_id` (optional for admin, ignored for regular users)
- `status` (optional) - Filter by job status
- `limit` (optional, default: 50) - Maximum results

**Example:**
```python
# Regular user listing jobs
headers = {'Authorization': 'Bearer alice_token'}
response = requests.get(
    'http://localhost:8001/api/jobs',
    headers=headers
)
# Returns only Alice's jobs

# Regular user trying to filter to Bob's jobs (ignored)
response = requests.get(
    'http://localhost:8001/api/jobs?user_id=bob',
    headers=headers
)
# Still returns only Alice's jobs (filter overridden)

# Admin listing all jobs
headers = {'Authorization': 'Bearer admin_token'}
response = requests.get(
    'http://localhost:8001/api/jobs',
    headers=headers
)
# Returns all jobs from all users

# Admin filtering to specific user
response = requests.get(
    'http://localhost:8001/api/jobs?user_id=alice',
    headers=headers
)
# Returns only Alice's jobs

# Admin filtering by status
response = requests.get(
    'http://localhost:8001/api/jobs?status=running',
    headers=headers
)
# Returns all running jobs from all users
```

### Node Stats: `GET /api/nodes`

**Regular User:**
- ✅ Can view node statistics
- Public endpoint (no authorization required)

**Admin User:**
- ✅ Can view node statistics
- Same access as regular users

**Example:**
```python
response = requests.get('http://localhost:8001/api/nodes')
print(response.json())
# {'nodes': [{'node_id': 0, 'is_busy': True, ...}, ...]}
```

## Authorization Flow

### Request Flow Diagram

```
┌─────────────────┐
│  Client Request │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Extract Token   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Validate Token  │
│ Get (user_id,   │
│      is_admin)  │
└────────┬────────┘
         │
         ├─── Invalid ──> 401 Unauthorized
         │
         ▼ Valid
┌─────────────────┐
│ Get Job from DB │
└────────┬────────┘
         │
         ├─── Not Found ──> 404 Not Found
         │
         ▼ Found
┌─────────────────┐
│ Check Ownership │
│ job.user_id ==  │
│ token.user_id?  │
└────────┬────────┘
         │
         ├─── No ──┬──> is_admin? ──┬─── Yes ──> Allow
         │         │                 │
         │         └─────────────────┴─── No ──> 403 Forbidden
         │
         ▼ Yes
    Allow Access
```

## Security Features

### 1. Token-User Binding
- Each token is permanently bound to a user_id
- Token cannot be used to access other users' resources
- Verified on every request

### 2. Explicit Authorization Checks
- Every protected endpoint checks authorization
- Ownership validated against database records
- Admin status checked for elevated privileges

### 3. Automatic Filtering
- Regular users' job lists are automatically filtered
- Cannot bypass filter to see other users' data
- Prevents information leakage

### 4. Rate Limiting (applies to all users)
- Maximum 5 job submissions per minute per user
- Maximum 1 active job per user at a time
- Prevents system abuse

### 5. Token Expiration
- All tokens expire after maximum 30 days
- Expired tokens return 401 Unauthorized
- Regular token renewal required

## Common Use Cases

### Use Case 1: Regular User Workflow

```python
import requests
import json

BASE_URL = "http://localhost:8001"
USER_TOKEN = "alice_secret_token"
headers = {'Authorization': f'Bearer {USER_TOKEN}'}

# 1. Submit job
code = "print('Hello World')"
config = {
    'competition_id': 'comp-001',
    'project_id': 'proj-001',
    'user_id': 'alice',
    'expected_time': 30,
    'token': USER_TOKEN
}
files = {
    'code': ('solution.py', code, 'text/x-python'),
    'config_file': ('config.json', json.dumps(config), 'application/json')
}
response = requests.post(f"{BASE_URL}/api/submit", files=files)
job_id = response.json()['job_id']

# 2. Check status
response = requests.get(f"{BASE_URL}/api/status/{job_id}", headers=headers)
print(f"Status: {response.json()['status']}")

# 3. Get results
response = requests.get(f"{BASE_URL}/api/results/{job_id}", headers=headers)
print(f"Output: {response.json()['stdout']}")

# 4. List my jobs
response = requests.get(f"{BASE_URL}/api/jobs", headers=headers)
print(f"My jobs: {len(response.json()['jobs'])}")
```

### Use Case 2: Admin Monitoring

```python
import requests

BASE_URL = "http://localhost:8001"
ADMIN_TOKEN = "admin_secret_token"
headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}

# 1. View all system jobs
response = requests.get(f"{BASE_URL}/api/jobs", headers=headers)
all_jobs = response.json()['jobs']
print(f"Total jobs in system: {len(all_jobs)}")

# 2. Monitor specific user
response = requests.get(f"{BASE_URL}/api/jobs?user_id=alice", headers=headers)
alice_jobs = response.json()['jobs']
print(f"Alice's jobs: {len(alice_jobs)}")

# 3. Check all running jobs
response = requests.get(f"{BASE_URL}/api/jobs?status=running", headers=headers)
running = response.json()['jobs']
print(f"Currently running: {len(running)}")

# 4. Cancel problematic job
problematic_job_id = "some-job-id"
response = requests.post(
    f"{BASE_URL}/api/cancel/{problematic_job_id}",
    headers=headers
)
print(f"Cancelled: {response.status_code == 200}")

# 5. Inspect any user's results
any_job_id = "another-users-job-id"
response = requests.get(f"{BASE_URL}/api/results/{any_job_id}", headers=headers)
print(f"Results: {response.json()['stdout'][:100]}...")
```

### Use Case 3: Preventing Unauthorized Access

```python
import requests

BASE_URL = "http://localhost:8001"
ALICE_TOKEN = "alice_token"
BOB_JOB_ID = "bob-job-123"

headers = {'Authorization': f'Bearer {ALICE_TOKEN}'}

# Alice tries to view Bob's job (will fail)
response = requests.get(
    f"{BASE_URL}/api/status/{BOB_JOB_ID}",
    headers=headers
)

if response.status_code == 403:
    print("✓ Access correctly denied")
    print(f"Error: {response.json()['detail']}")
    # Output: "Not authorized to view this job"
```

## Token Management

### Creating Tokens

```bash
# Create regular user token
python3 token_manager.py create alice alice_secret_token

# Create admin token
python3 token_manager.py create admin_user admin_secret_token --admin

# Create token with custom expiry (max 30 days)
python3 token_manager.py create bob bob_token --days 15
```

### Listing Tokens

```bash
python3 token_manager.py list
```

Output shows admin status:
```
Tokens:
------------------------------------------------------------------------------------------
User ID                        Admin      Active     Expires At                    
------------------------------------------------------------------------------------------
alice                          No         Yes        2025-12-06 17:21:24           
admin_user                     Yes        Yes        2025-12-06 17:21:31           
bob                            No         Yes        2025-12-21 17:21:41
```

### Revoking Tokens

```bash
python3 token_manager.py revoke <token_string>
```

## Best Practices

### For Regular Users
1. **Keep tokens secure** - Never share or commit tokens to version control
2. **Monitor your jobs** - Regularly check status of submitted jobs
3. **Cancel unnecessary jobs** - Free up resources by cancelling jobs you don't need
4. **Use appropriate expected_time** - Helps with queue scheduling

### For Admins
1. **Monitor system load** - Check `/api/nodes` and `/api/jobs` regularly
2. **Investigate long-running jobs** - Cancel jobs that are stuck or taking too long
3. **Review user activity** - Check for unusual patterns or abuse
4. **Rotate admin tokens** - Regularly update admin credentials
5. **Use admin sparingly** - Only use admin privileges when necessary

### For Developers
1. **Always include Authorization header** - Required for all protected endpoints
2. **Handle 403 errors gracefully** - User-friendly messages for access denied
3. **Implement token refresh** - Tokens expire after 30 days
4. **Test with regular users** - Don't develop only with admin access
5. **Log authorization failures** - For security auditing

## Error Handling

### Common Error Responses

```python
# 401 Unauthorized - Invalid/missing token
{
    "detail": "Invalid or expired token"
}

# 403 Forbidden - No permission
{
    "detail": "Not authorized to view this job"
}

# 403 Forbidden - Token mismatch
{
    "detail": "Token does not belong to specified user_id"
}

# 404 Not Found
{
    "detail": "Job not found"
}

# 429 Too Many Requests
{
    "detail": "Rate limit exceeded. Maximum 5 requests per 60s. Retry after 45s."
}
```

### Handling in Code

```python
import requests

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        print("Token expired or invalid - please re-authenticate")
    elif e.response.status_code == 403:
        print("Access denied - you don't have permission")
    elif e.response.status_code == 404:
        print("Job not found")
    elif e.response.status_code == 429:
        print("Rate limited - please slow down")
    else:
        print(f"Error: {e}")
```

## Testing Authorization

Run the authorization test suite:

```bash
cd tests
python3 test_authorization.py
```

Tests verify:
- ✅ Users can only see their own jobs
- ✅ Admin can view all jobs
- ✅ Admin can cancel any job
- ✅ Job list filtering works correctly

## Migration Notes

### From Previous Versions

If upgrading from a version without admin support:

1. **Stop the server**
   ```bash
   killall python3
   ```

2. **Backup database**
   ```bash
   cp database.db database.db.backup
   ```

3. **Delete old database** (schema changed)
   ```bash
   rm database.db
   ```

4. **Start server** (recreates database with new schema)
   ```bash
   python3 main.py
   ```

5. **Recreate all tokens**
   ```bash
   python3 token_manager.py create alice alice_token
   python3 token_manager.py create admin admin_token --admin
   ```

## Summary

| Feature | Regular User | Admin User |
|---------|-------------|------------|
| Submit jobs | ✅ Own jobs only | ✅ Own jobs only |
| View job status | ✅ Own jobs only | ✅ All jobs |
| View job results | ✅ Own jobs only | ✅ All jobs |
| Cancel jobs | ✅ Own jobs only | ✅ All jobs |
| List jobs | ✅ Own jobs only | ✅ All jobs |
| View node stats | ✅ Yes | ✅ Yes |
| Rate limiting | ✅ Applied | ✅ Applied |
| Token expiry | ✅ 30 days max | ✅ 30 days max |

**Key Difference**: Admin users bypass ownership checks for viewing and managing jobs, but follow same submission rules as regular users.

