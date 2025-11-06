#!/usr/bin/env python3
"""
Dashboard Example - Live system monitoring
Demonstrates the /api/dashboard endpoint
"""

import requests
import time
import sys
from datetime import datetime

BASE_URL = "http://localhost:8001"

def clear_screen():
    """Clear terminal screen"""
    print("\033[2J\033[H", end='')

def print_header():
    """Print dashboard header"""
    print("=" * 70)
    print(f"  GPU JOB QUEUE DASHBOARD - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

def print_user_dashboard(dashboard):
    """Display dashboard for regular user"""
    stats = dashboard['job_statistics']
    
    print(f"\n📊 Your Jobs:")
    print(f"  Total:     {stats['total']:>4}")
    print(f"  Running:   {stats['running']:>4}")
    print(f"  Pending:   {stats['pending']:>4}")
    print(f"  Completed: {stats['completed']:>4}")
    print(f"  Failed:    {stats['failed']:>4}")
    
    # Active jobs
    active = dashboard['active_jobs']
    if active:
        print(f"\n⚡ Active Jobs ({len(active)}):")
        for job in active:
            status_icon = "▶️" if job['status'] == 'running' else "⏸️"
            comp = job['competition_id'][:25]
            node = f"Node {job['node_id']}" if job['node_id'] is not None else "Queued"
            pos = f" (pos {job['queue_position']})" if job['queue_position'] else ""
            print(f"  {status_icon} {comp:<25} {node:<8} {pos}")
    else:
        print(f"\n⚡ No active jobs")
    
    # Recent jobs
    recent = dashboard['recent_jobs'][:5]
    if recent:
        print(f"\n📋 Recent Jobs:")
        for job in recent:
            status_icon = {
                'completed': '✅',
                'failed': '❌',
                'cancelled': '🚫'
            }.get(job['status'], '❓')
            
            comp = job['competition_id'][:25]
            duration = f"{job['duration_seconds']:.0f}s" if job['duration_seconds'] else "N/A"
            print(f"  {status_icon} {comp:<25} {duration:>6}")

def print_admin_dashboard(dashboard):
    """Display dashboard for admin"""
    health = dashboard['health_metrics']
    
    # System health
    print(f"\n📊 System Health:")
    util = health['node_utilization_percent']
    util_bar = "█" * int(util / 10) + "░" * (10 - int(util / 10))
    print(f"  Utilization:  [{util_bar}] {util}%")
    print(f"  Active Jobs:  {health['total_active_jobs']}")
    print(f"  Success Rate: {health['success_rate_percent']}%")
    print(f"  Jobs (24h):   {health['jobs_last_24h']}")
    
    # Node status
    print(f"\n🖥️  GPU Nodes:")
    queues = dashboard['queue_information']
    for queue in queues:
        node = queue['node_id']
        status = "🔴 BUSY" if queue['is_busy'] else "🟢 FREE"
        queue_size = queue['queue_size']
        queue_time = queue['queue_time_seconds']
        
        print(f"  Node {node}: {status}  Queue: {queue_size:>2}  Time: {queue_time:>4}s")
        
        if queue['current_job']:
            job = queue['current_job']
            user = job['user_id'][:10]
            comp = job['competition_id'][:20]
            print(f"           ▶️  {comp:<20} ({user})")
    
    # User statistics
    user_stats = dashboard.get('user_statistics', {})
    if user_stats:
        print(f"\n👥 User Activity:")
        for user_id, stats in list(user_stats.items())[:5]:  # Show top 5
            total = stats['total']
            running = stats['running']
            pending = stats['pending']
            print(f"  {user_id:<15} Total: {total:>3}  Running: {running:>2}  Pending: {pending:>2}")
    
    # Active jobs
    active = dashboard['active_jobs'][:8]  # Show top 8
    if active:
        print(f"\n⚡ Active Jobs ({len(dashboard['active_jobs'])} total, showing {len(active)}):")
        for job in active:
            status_icon = "▶️" if job['status'] == 'running' else "⏸️"
            comp = job['competition_id'][:20]
            user = job['user_id'][:10]
            node = f"N{job['node_id']}" if job['node_id'] is not None else "Q"
            print(f"  {status_icon} {comp:<20} {user:<10} {node:>2}")

def fetch_dashboard(token):
    """Fetch dashboard data"""
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(f"{BASE_URL}/api/dashboard", headers=headers, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching dashboard: {e}")
        return None

def live_monitor(token, refresh_seconds=5):
    """Live monitoring loop"""
    try:
        while True:
            dashboard = fetch_dashboard(token)
            
            if not dashboard:
                time.sleep(refresh_seconds)
                continue
            
            clear_screen()
            print_header()
            
            is_admin = dashboard.get('is_admin', False)
            
            if is_admin:
                print_admin_dashboard(dashboard)
            else:
                print_user_dashboard(dashboard)
            
            print(f"\n🔄 Refreshing in {refresh_seconds}s... (Ctrl+C to exit)")
            time.sleep(refresh_seconds)
            
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard closed")
        sys.exit(0)

def single_fetch(token):
    """Single dashboard fetch"""
    dashboard = fetch_dashboard(token)
    
    if not dashboard:
        sys.exit(1)
    
    print_header()
    
    is_admin = dashboard.get('is_admin', False)
    
    if is_admin:
        print_admin_dashboard(dashboard)
    else:
        print_user_dashboard(dashboard)
    
    print()  # Blank line at end

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="GPU Job Queue Dashboard")
    parser.add_argument('token', help='Authentication token')
    parser.add_argument('--refresh', type=int, default=5, 
                       help='Refresh interval in seconds (0 for single fetch)')
    parser.add_argument('--url', default=BASE_URL, 
                       help=f'Server URL (default: {BASE_URL})')
    
    args = parser.parse_args()
    
    global BASE_URL
    BASE_URL = args.url
    
    if args.refresh > 0:
        print(f"Starting live monitor (refresh every {args.refresh}s)...")
        time.sleep(1)
        live_monitor(args.token, args.refresh)
    else:
        single_fetch(args.token)

if __name__ == "__main__":
    main()

