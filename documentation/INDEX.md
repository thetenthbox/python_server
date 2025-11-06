# GPU Job Queue Server - Documentation Index

## Getting Started

### 1. [Quick Start Guide](QUICK_START.md)
Fast track to getting the server running in minutes.
- Prerequisites
- Installation
- First job submission
- Basic usage

### 2. [Setup Guide](SETUP.md)
Detailed setup instructions for production deployment.
- Server configuration
- SSH key setup
- Database initialization
- Token management

### 3. [README](README.md)
Project overview and architecture.
- System architecture
- Key features
- Components overview

## Core Documentation

### 4. [API Documentation](API_DOCUMENTATION.md)
Complete API reference for all endpoints.
- Submit jobs
- Check status
- Retrieve results
- Cancel jobs
- List jobs
- Node statistics

### 5. [Access Control & User Privileges](ACCESS_CONTROL.md) ⭐ NEW
Understanding user roles and permissions.
- Regular users vs Admin users
- Permission matrix
- Authorization flow
- Best practices
- Common use cases
- Error handling

## Security & Management

### 6. [Token Management](TOKEN_IMPLEMENTATION_SUMMARY.md)
Token creation, validation, and lifecycle.
- Token-user binding
- Expiration policies (30 days max)
- One token per user
- CLI commands

### 7. [Authorization Implementation](AUTHORIZATION_SUMMARY.md)
Technical details of authorization system.
- User isolation
- Admin role
- Database schema
- Implementation details

### 8. [Token Management Analysis](TOKEN_MANAGEMENT_ANALYSIS.md)
Deep dive into token security considerations.
- Consequences
- Risks
- Solutions implemented

## Testing & Issues

### 9. [Testing Plan](TESTING_PLAN.md)
Comprehensive testing strategy.
- Unit tests
- Integration tests
- Security tests
- Performance tests
- Test execution plan

### 10. [Potential Issues](POTENTIAL_ISSUES.md)
Known edge cases and considerations.
- Connection management
- Job lifecycle
- Resource management
- Error handling
- Authorization edge cases

## Quick Reference

### Most Common Tasks

| Task | Documentation |
|------|---------------|
| Start using the API | [Quick Start](QUICK_START.md) |
| Understand user permissions | [Access Control](ACCESS_CONTROL.md) |
| Submit a job | [API Docs - Submit](API_DOCUMENTATION.md#post-apisubmit) |
| Create a token | [Token Management](TOKEN_IMPLEMENTATION_SUMMARY.md) |
| Create admin token | [Access Control - Admin](ACCESS_CONTROL.md#admin-user) |
| Check job status | [API Docs - Status](API_DOCUMENTATION.md#get-apistatusjob_id) |
| Cancel a job | [API Docs - Cancel](API_DOCUMENTATION.md#post-apicanceljob_id) |
| Run tests | [Testing Plan](TESTING_PLAN.md) |
| Troubleshoot errors | [Potential Issues](POTENTIAL_ISSUES.md) |

### User Type Quick Links

**Regular User:**
- [Quick Start](QUICK_START.md) - Get started quickly
- [API Documentation](API_DOCUMENTATION.md) - Learn the API
- [Access Control - Regular User](ACCESS_CONTROL.md#regular-user) - Your permissions

**Admin User:**
- [Access Control - Admin User](ACCESS_CONTROL.md#admin-user) - Admin capabilities
- [Token Management](TOKEN_IMPLEMENTATION_SUMMARY.md) - Create admin tokens
- [Testing Plan](TESTING_PLAN.md) - Verify system health

**Developer:**
- [README](README.md) - Architecture overview
- [Setup Guide](SETUP.md) - Development setup
- [API Documentation](API_DOCUMENTATION.md) - Complete API reference
- [Authorization Implementation](AUTHORIZATION_SUMMARY.md) - Technical details

### Security Quick Links

| Topic | Documentation |
|-------|---------------|
| User permissions | [Access Control](ACCESS_CONTROL.md) |
| Token security | [Token Management](TOKEN_IMPLEMENTATION_SUMMARY.md) |
| Rate limiting | [API Docs - Security](API_DOCUMENTATION.md#security-features) |
| Authorization flow | [Access Control - Auth Flow](ACCESS_CONTROL.md#authorization-flow) |
| Security testing | [Testing Plan - Security](TESTING_PLAN.md#5-security-testing) |

## Documentation Structure

```
documentation/
├── INDEX.md (this file)               # Start here
│
├── Getting Started
│   ├── QUICK_START.md                 # 5-minute setup
│   ├── SETUP.md                       # Detailed setup
│   └── README.md                      # Project overview
│
├── API & Usage
│   ├── API_DOCUMENTATION.md           # Complete API reference
│   └── ACCESS_CONTROL.md              # User roles & permissions ⭐
│
├── Security
│   ├── TOKEN_IMPLEMENTATION_SUMMARY.md # Token management
│   ├── AUTHORIZATION_SUMMARY.md        # Auth implementation
│   └── TOKEN_MANAGEMENT_ANALYSIS.md    # Security analysis
│
└── Testing & Issues
    ├── TESTING_PLAN.md                # Test strategy
    └── POTENTIAL_ISSUES.md            # Known issues
```

## Update Log

### Latest Updates (2025-11-06)

**Access Control Implementation:**
- ✅ Added user isolation (users can only access their own jobs)
- ✅ Added admin role with elevated privileges
- ✅ Authorization checks on all protected endpoints
- ✅ Comprehensive [ACCESS_CONTROL.md](ACCESS_CONTROL.md) documentation
- ✅ New authorization test suite

**Token Management:**
- ✅ 30-day maximum token expiry
- ✅ One active token per user
- ✅ Token-user binding strengthened
- ✅ Admin token support via `--admin` flag

## Contributing to Documentation

When adding new features:
1. Update relevant documentation files
2. Add entry to this INDEX.md
3. Update the Quick Reference section
4. Add to appropriate category

## Need Help?

1. **Can't find what you need?** Check the [INDEX.md](INDEX.md) (this file)
2. **Getting started?** Read [QUICK_START.md](QUICK_START.md)
3. **API questions?** See [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
4. **Permission issues?** Check [ACCESS_CONTROL.md](ACCESS_CONTROL.md)
5. **Security concerns?** Review [Token Management](TOKEN_IMPLEMENTATION_SUMMARY.md)

## Version

Documentation Version: 2.0  
Server Version: 2.0 (with access control)  
Last Updated: 2025-11-06

