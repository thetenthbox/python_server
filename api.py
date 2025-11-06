"""
FastAPI endpoints for GPU Job Queue Server
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, Header, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from typing import Optional, List
import uuid
import os
import yaml
import asyncio
from datetime import datetime

import config
import models
import auth
from queue_manager import queue_manager
from ssh_executor import SSHExecutor
from rate_limiter import rate_limiter, endpoint_protection
from code_scanner import scan_code


app = FastAPI(title="GPU Job Queue Server")


def get_db():
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/api/submit")
async def submit_job(
    request: Request,
    code: UploadFile = File(...),
    config_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Submit a new job and wait for completion
    Files:
        - code: .py file with Python code
        - config_file: .yaml file with job configuration
    
    Returns results directly after job completes
    
    Rate limits: 5 submissions per minute per user
    Queue limit: 1 job per user at a time
    """
    try:
        # General endpoint protection (100 requests/min per IP)
        client_ip = request.client.host if request.client else "unknown"
        allowed, msg = endpoint_protection.check_endpoint_limit(client_ip, max_requests=100, window_seconds=60)
        if not allowed:
            raise HTTPException(status_code=429, detail=msg)
        
        # Read YAML config
        yaml_content = await config_file.read()
        job_config = yaml.safe_load(yaml_content)
        
        # Validate required fields
        required_fields = ['competition_id', 'project_id', 'user_id', 'expected_time', 'token']
        for field in required_fields:
            if field not in job_config:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate token
        token_result = auth.validate_token(job_config['token'], db)
        if not token_result:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        user_id, is_admin = token_result
        
        # SECURITY: Verify user_id matches token owner (strengthened binding)
        if user_id != job_config['user_id']:
            raise HTTPException(status_code=403, detail="Token does not belong to specified user_id")
        
        # SECURITY: Scan code for malicious content and ML relevance
        code_content = (await code.read()).decode('utf-8')
        
        if config.CODE_SCANNER_ENABLED:
            scan_result = scan_code(
                code_content, 
                job_config['competition_id'], 
                quick=config.CODE_SCANNER_QUICK_MODE
            )
            
            if not scan_result['safe']:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Code security check failed: {', '.join(scan_result['issues'])}"
                )
            
            if not scan_result['relevant']:
                raise HTTPException(
                    status_code=400,
                    detail=f"Code does not appear relevant to ML competition: {scan_result['explanation']}"
                )
        
        # Reset file pointer after reading
        await code.seek(0)
        
        # Rate limiting: Max 5 submissions per minute per user
        allowed, msg = rate_limiter.check_rate_limit(user_id, max_requests=5, window_seconds=60)
        if not allowed:
            raise HTTPException(status_code=429, detail=msg)
        
        # Queue limit: Check if user already has a job in queue or running
        existing_jobs = db.query(models.Job).filter(
            models.Job.user_id == user_id,
            models.Job.status.in_(['pending', 'running'])
        ).count()
        
        if existing_jobs >= 1:
            raise HTTPException(
                status_code=429, 
                detail=f"Queue limit exceeded. You already have {existing_jobs} job(s) in progress. Maximum 1 job per user allowed."
            )
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create job directory
        job_dir = os.path.join(config.JOBS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        # Save code file
        code_path = os.path.join(job_dir, "script.py")
        code_content = await code.read()
        with open(code_path, "wb") as f:
            f.write(code_content)
        
        # Save YAML file
        yaml_path = os.path.join(job_dir, "config.yaml")
        with open(yaml_path, "wb") as f:
            f.write(yaml_content)
        
        # Create job in database
        new_job = models.Job(
            job_id=job_id,
            competition_id=job_config['competition_id'],
            project_id=job_config['project_id'],
            user_id=job_config['user_id'],
            expected_time=int(job_config['expected_time']),
            token_hash=auth.hash_token(job_config['token']),
            status="pending",
            code_path=code_path,
            yaml_path=yaml_path
        )
        
        db.add(new_job)
        db.commit()
        
        # Assign to queue
        node_id = queue_manager.assign_job(job_id, new_job.expected_time)
        
        # Update job with node assignment
        new_job.node_id = node_id
        db.commit()
        
        # Wait for job completion (max 5 minutes)
        timeout = 300
        start_time = asyncio.get_event_loop().time()
        
        while True:
            db.refresh(new_job)
            
            if new_job.status in ["completed", "failed", "cancelled"]:
                return {
                    "job_id": job_id,
                    "node_id": node_id,
                    "status": new_job.status,
                    "stdout": new_job.stdout,
                    "stderr": new_job.stderr,
                    "exit_code": new_job.exit_code,
                    "started_at": new_job.started_at,
                    "completed_at": new_job.completed_at
                }
            
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                return {
                    "job_id": job_id,
                    "node_id": node_id,
                    "status": new_job.status,
                    "message": f"Timeout after {timeout}s. Job still {new_job.status}. Use /api/results/{job_id} to check later."
                }
            
            # Wait before next check
            await asyncio.sleep(0.5)
        
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML format: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting job: {str(e)}")


@app.get("/api/status/{job_id}")
async def get_job_status(
    request: Request, 
    job_id: str, 
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get status of a job
    Authorization: Users can only view their own jobs, admins can view any job
    """
    # Endpoint protection
    client_ip = request.client.host if request.client else "unknown"
    allowed, msg = endpoint_protection.check_endpoint_limit(client_ip, max_requests=200, window_seconds=60)
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)
    
    # Get job
    job = db.query(models.Job).filter(models.Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Authorization check
    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            token_result = auth.validate_token(token, db)
            
            if token_result:
                user_id, is_admin = token_result
                # Admin can view any job, regular users only their own
                if not is_admin and job.user_id != user_id:
                    raise HTTPException(status_code=403, detail="Not authorized to view this job")
            else:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
        else:
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
    else:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    queue_position = None
    if job.status == "pending" and job.node_id is not None:
        queue_position = queue_manager.get_queue_position(job_id, job.node_id)
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "node_id": job.node_id,
        "queue_position": queue_position,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "exit_code": job.exit_code
    }


@app.get("/api/results/{job_id}")
async def get_job_results(
    request: Request, 
    job_id: str,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get results of a completed job
    Authorization: Users can only view their own jobs, admins can view any job
    """
    # Endpoint protection
    client_ip = request.client.host if request.client else "unknown"
    allowed, msg = endpoint_protection.check_endpoint_limit(client_ip, max_requests=200, window_seconds=60)
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)
    
    # Get job
    job = db.query(models.Job).filter(models.Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Authorization check
    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            token_result = auth.validate_token(token, db)
            
            if token_result:
                user_id, is_admin = token_result
                # Admin can view any job, regular users only their own
                if not is_admin and job.user_id != user_id:
                    raise HTTPException(status_code=403, detail="Not authorized to view this job")
            else:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
        else:
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
    else:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "stdout": job.stdout,
        "stderr": job.stderr,
        "exit_code": job.exit_code,
        "started_at": job.started_at,
        "completed_at": job.completed_at
    }


@app.post("/api/cancel/{job_id}")
async def cancel_job(
    job_id: str,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Cancel a pending or running job
    Authorization: Users can only cancel their own jobs, admins can cancel any job
    """
    # Extract token from header (format: "Bearer <token>")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.split(" ")[1]
    
    # Validate token
    token_result = auth.validate_token(token, db)
    if not token_result:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id, is_admin = token_result
    
    # Get job
    job = db.query(models.Job).filter(models.Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Verify user owns this job OR is admin
    if not is_admin and job.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this job")
    
    # Check if job can be cancelled
    if job.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Job already {job.status}")
    
    if job.status == "pending":
        # Remove from queue
        if queue_manager.remove_job(job_id, job.node_id, job.expected_time):
            job.status = "cancelled"
            job.completed_at = datetime.utcnow()
            db.commit()
            return {"message": "Job cancelled successfully", "status": "cancelled"}
        else:
            # Job might have just started
            job.status = "cancelled"
            db.commit()
            return {"message": "Job marked for cancellation", "status": "cancelled"}
    
    elif job.status == "running":
        # Mark as cancelled - worker will kill the process
        job.status = "cancelled"
        db.commit()
        
        # Try to kill immediately if we have PID
        if job.remote_pid and job.node_id is not None:
            try:
                executor = SSHExecutor(job.node_id)
                if executor.connect():
                    executor.kill_process(job.remote_pid)
                    executor.cleanup_job_files(job_id)
                    executor.disconnect()
            except Exception as e:
                print(f"Error killing process: {e}")
        
        return {"message": "Job cancelled successfully", "status": "cancelled"}


@app.get("/api/nodes")
async def get_node_stats():
    """Get statistics for all GPU nodes"""
    stats = queue_manager.get_node_stats()
    return {"nodes": stats}


@app.get("/api/jobs")
async def list_jobs(
    request: Request,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    List jobs with optional filtering
    Authorization: Users see only their own jobs, admins can see all jobs
    """
    # Authorization check
    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            token_result = auth.validate_token(token, db)
            
            if token_result:
                authenticated_user_id, is_admin = token_result
                
                # Regular users can only see their own jobs
                if not is_admin:
                    user_id = authenticated_user_id  # Force filter to authenticated user
            else:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
        else:
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
    else:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    query = db.query(models.Job)
    
    if user_id:
        query = query.filter(models.Job.user_id == user_id)
    
    if status:
        query = query.filter(models.Job.status == status)
    
    jobs = query.order_by(models.Job.created_at.desc()).limit(limit).all()
    
    return {
        "jobs": [
            {
                "job_id": job.job_id,
                "user_id": job.user_id,
                "status": job.status,
                "node_id": job.node_id,
                "created_at": job.created_at,
                "completed_at": job.completed_at
            }
            for job in jobs
        ]
    }


@app.get("/api/dashboard")
async def get_dashboard(
    request: Request,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard data with live system stats
    
    Authorization: Users see only their data, admins see everything
    
    Returns:
        - Job statistics (by status, by user)
        - Queue states (per node)
        - Node utilization
        - Recent activity
        - System health metrics
    """
    # Check authorization
    is_admin = False
    user_id = None
    
    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            token_result = auth.validate_token(token, db)
            
            if token_result:
                user_id, is_admin = token_result
            else:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
        else:
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
    else:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    # Get all jobs (filtered by user if not admin)
    jobs_query = db.query(models.Job)
    if not is_admin:
        jobs_query = jobs_query.filter(models.Job.user_id == user_id)
    
    all_jobs = jobs_query.all()
    
    # Job statistics by status
    job_stats = {
        'total': len(all_jobs),
        'pending': len([j for j in all_jobs if j.status == 'pending']),
        'running': len([j for j in all_jobs if j.status == 'running']),
        'completed': len([j for j in all_jobs if j.status == 'completed']),
        'failed': len([j for j in all_jobs if j.status == 'failed']),
        'cancelled': len([j for j in all_jobs if j.status == 'cancelled'])
    }
    
    # User statistics (admin only)
    user_stats = {}
    if is_admin:
        users = db.query(models.Job.user_id).distinct().all()
        for (uid,) in users:
            user_jobs = [j for j in all_jobs if j.user_id == uid]
            user_stats[uid] = {
                'total': len(user_jobs),
                'pending': len([j for j in user_jobs if j.status == 'pending']),
                'running': len([j for j in user_jobs if j.status == 'running']),
                'completed': len([j for j in user_jobs if j.status == 'completed']),
                'failed': len([j for j in user_jobs if j.status == 'failed'])
            }
    
    # Node statistics
    node_stats = queue_manager.get_node_stats()
    
    # Queue information
    queue_info = []
    for node_id in range(8):
        queue_size = queue_manager.get_queue_size(node_id)
        queue_time = queue_manager.get_total_queue_time(node_id)
        current_job = None
        
        # Find current job on this node
        for job in all_jobs:
            if job.node_id == node_id and job.status == 'running':
                current_job = {
                    'job_id': job.job_id,
                    'user_id': job.user_id,
                    'competition_id': job.competition_id,
                    'started_at': job.started_at.isoformat() if job.started_at else None
                }
                break
        
        # Check if node is busy (has running job)
        is_busy = current_job is not None
        
        queue_info.append({
            'node_id': node_id,
            'queue_size': queue_size,
            'queue_time_seconds': queue_time,
            'is_busy': is_busy,
            'current_job': current_job
        })
    
    # Recent jobs (last 10)
    recent_query = db.query(models.Job)
    if not is_admin:
        recent_query = recent_query.filter(models.Job.user_id == user_id)
    
    recent_jobs = recent_query.order_by(models.Job.created_at.desc()).limit(10).all()
    recent_jobs_data = [{
        'job_id': j.job_id,
        'user_id': j.user_id,
        'competition_id': j.competition_id,
        'status': j.status,
        'node_id': j.node_id,
        'created_at': j.created_at.isoformat() if j.created_at else None,
        'started_at': j.started_at.isoformat() if j.started_at else None,
        'completed_at': j.completed_at.isoformat() if j.completed_at else None,
        'duration_seconds': (
            (j.completed_at - j.started_at).total_seconds()
            if j.started_at and j.completed_at
            else None
        )
    } for j in recent_jobs]
    
    # Active jobs (running or pending)
    active_query = db.query(models.Job).filter(
        models.Job.status.in_(['pending', 'running'])
    )
    if not is_admin:
        active_query = active_query.filter(models.Job.user_id == user_id)
    
    active_jobs = active_query.order_by(models.Job.created_at.desc()).all()
    active_jobs_data = [{
        'job_id': j.job_id,
        'user_id': j.user_id,
        'competition_id': j.competition_id,
        'status': j.status,
        'node_id': j.node_id,
        'expected_time': j.expected_time,
        'created_at': j.created_at.isoformat() if j.created_at else None,
        'started_at': j.started_at.isoformat() if j.started_at else None,
        'queue_position': queue_manager.get_queue_position(j.job_id, j.node_id) if j.status == 'pending' else None
    } for j in active_jobs]
    
    # System health metrics
    total_nodes = 8
    busy_nodes = sum(1 for q in queue_info if q['is_busy'])
    utilization = (busy_nodes / total_nodes) * 100
    
    # Average queue time across all nodes
    avg_queue_time = sum(q['queue_time_seconds'] for q in queue_info) / len(queue_info) if queue_info else 0
    
    # Success rate (last 100 jobs)
    recent_completed = db.query(models.Job).filter(
        models.Job.status.in_(['completed', 'failed'])
    ).order_by(models.Job.completed_at.desc()).limit(100).all()
    
    success_count = len([j for j in recent_completed if j.status == 'completed'])
    success_rate = (success_count / len(recent_completed) * 100) if recent_completed else 0
    
    health_metrics = {
        'node_utilization_percent': round(utilization, 1),
        'average_queue_time_seconds': round(avg_queue_time, 1),
        'total_active_jobs': len(active_jobs),
        'success_rate_percent': round(success_rate, 1),
        'jobs_last_24h': len([
            j for j in all_jobs 
            if j.created_at and (datetime.utcnow() - j.created_at).total_seconds() < 86400
        ])
    }
    
    return {
        'timestamp': datetime.utcnow().isoformat(),
        'user_id': user_id,
        'is_admin': is_admin,
        'job_statistics': job_stats,
        'user_statistics': user_stats if is_admin else {},
        'node_statistics': node_stats,
        'queue_information': queue_info,
        'active_jobs': active_jobs_data,
        'recent_jobs': recent_jobs_data,
        'health_metrics': health_metrics
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "GPU Job Queue Server",
        "version": "1.0",
        "endpoints": {
            "submit": "POST /api/submit",
            "status": "GET /api/status/{job_id}",
            "results": "GET /api/results/{job_id}",
            "cancel": "POST /api/cancel/{job_id}",
            "nodes": "GET /api/nodes",
            "jobs": "GET /api/jobs"
        }
    }

