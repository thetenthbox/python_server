# Authorization & Admin Features Implementation

## Overview
Implemented comprehensive authorization controls to ensure users can only access their own jobs, plus admin role with elevated privileges.

## Features Implemented

### 1. User Isolation
**Users can only view their own jobs:**
- `/api/status/{job_id}` - Returns 403 if user tries to view another user's job
- `/api/results/{job_id}` - Returns 403 if user tries to view another user's results
- `/api/cancel/{job_id}` - Returns 403 if user tries to cancel another user's job
- `/api/jobs` - Automatically filters to show only the authenticated user's jobs

### 2. Admin Role
**Admin tokens have elevated privileges:**
- Can view any user's job status and results
- Can cancel any user's job
- Can list all jobs from all users (no automatic filtering)
- Created by adding `--admin` flag when creating token

### 3. Token Management Updates
**Enhanced token system:**
- Added `is_admin` field to Token model
- Token validation now returns `(user_id, is_admin)` tuple
- `create_token()` accepts `is_admin` parameter
- Token manager CLI supports `--admin` flag

## Database Schema Changes

### Token Table
```sql
ALTER TABLE tokens ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;
```

## API Changes

### Authentication
All protected endpoints now check both:
1. Token validity
2. Job ownership (user_id match) OR admin status

### Endpoints Updated

#### `/api/status/{job_id}` (GET)
- **Authorization Required**: Yes (via `Authorization: Bearer <token>` header)
- **Access Control**:
  - Users: Can only view their own jobs
  - Admins: Can view any job

#### `/api/results/{job_id}` (GET)
- **Authorization Required**: Yes (via `Authorization: Bearer <token>` header)
- **Access Control**:
  - Users: Can only view their own job results
  - Admins: Can view any job results

#### `/api/cancel/{job_id}` (POST)
- **Authorization Required**: Yes (via `Authorization: Bearer <token>` header)
- **Access Control**:
  - Users: Can only cancel their own jobs
  - Admins: Can cancel any job

#### `/api/jobs` (GET)
- **Authorization Required**: Yes (via `Authorization: Bearer <token>` header)
- **Access Control**:
  - Users: Automatically filtered to show only their jobs
  - Admins: Can see all jobs (respects `user_id` filter if provided)

## Token Manager CLI

### Creating Regular User Token
```bash
python3 token_manager.py create <user_id> <token_string> [--days <days>]
```

### Creating Admin Token
```bash
python3 token_manager.py create <user_id> <token_string> --admin [--days <days>]
```

### Listing Tokens
```bash
python3 token_manager.py list
```

Output includes admin status:
```
User ID                        Admin      Active     Expires At                    
------------------------------------------------------------------------------------------
sarang                         No         Yes        2025-12-06 17:21:24           
admin                          Yes        Yes        2025-12-06 17:21:31           
bob                            No         Yes        2025-12-06 17:21:41
```

## Testing

### Test Coverage
All authorization features are tested in `tests/test_authorization.py`:

1. **test_user_can_only_see_own_jobs**
   - Users cannot view other users' job status
   - Users can view their own job status

2. **test_admin_can_view_all_jobs**
   - Admin can view any user's job status
   - Admin can view any user's job results

3. **test_admin_can_cancel_any_job**
   - Regular users cannot cancel other users' jobs
   - Admin can cancel any user's job

4. **test_list_jobs_filtered**
   - Users only see their own jobs in list
   - Admin sees all jobs from all users

### Running Tests
```bash
cd tests
python3 test_authorization.py
```

## Implementation Details

### Code Files Modified

1. **models.py**
   - Added `is_admin` column to Token model

2. **auth.py**
   - Updated `validate_token()` to return `(user_id, is_admin)` tuple
   - Updated `create_token()` to accept `is_admin` parameter

3. **api.py**
   - Updated all protected endpoints to check authorization
   - Added logic to check `is_admin` flag
   - Modified `/api/jobs` to filter by user for non-admins

4. **token_manager.py**
   - Added `--admin` flag to create command
   - Updated list command to display admin status

5. **tests/test_authorization.py**
   - New comprehensive test suite for authorization features

## Security Benefits

1. **Data Privacy**: Users cannot access other users' jobs or results
2. **Job Control**: Users cannot interfere with other users' jobs
3. **Admin Oversight**: Admins can monitor and manage all system activity
4. **Audit Trail**: All authorization checks are logged

## Error Responses

### 401 Unauthorized
- Missing or invalid `Authorization` header
- Expired token
- Revoked token

### 403 Forbidden
- User attempting to access another user's job
- User attempting to cancel another user's job
- Token does not belong to specified user_id in job submission

### 404 Not Found
- Job ID does not exist

## Example Usage

### Regular User
```python
import requests

headers = {'Authorization': 'Bearer test_token_regular'}

# View own job
response = requests.get(
    'http://localhost:8001/api/status/my-job-id',
    headers=headers
)
# Success: 200

# Try to view other user's job
response = requests.get(
    'http://localhost:8001/api/status/other-users-job-id',
    headers=headers
)
# Denied: 403
```

### Admin User
```python
import requests

headers = {'Authorization': 'Bearer test_token_admin'}

# View any user's job
response = requests.get(
    'http://localhost:8001/api/status/any-job-id',
    headers=headers
)
# Success: 200

# List all jobs
response = requests.get(
    'http://localhost:8001/api/jobs',
    headers=headers
)
# Returns all jobs from all users
```

## Migration Notes

### For Existing Deployments
1. Stop the server
2. Delete old database: `rm database.db`
3. Start server (will recreate database with new schema)
4. Recreate all tokens using token_manager

### For Fresh Deployments
No migration needed - schema includes `is_admin` field by default.

## Future Enhancements

Potential additions:
- Multiple admin levels (super admin, moderator, etc.)
- Role-based access control (RBAC) with custom permissions
- Admin audit log for all administrative actions
- User groups with shared job access
- API endpoint to manage user permissions

