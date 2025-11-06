# Token Management - Detailed Analysis

## Context
This is an internal company API, not public-facing consumer API. Used by data scientists/engineers within the organization to submit ML solutions for grading on GPU cluster.

---

## Issue 1: Token expiry during job execution - user can't cancel or check status

**Consequence:**
- User submits a long-running job (30+ minutes)
- Token expires while job is running
- User tries to cancel or check status → 401 Unauthorized
- Job continues running but user has lost control
- User must wait for job to complete or contact admin
- Wasted GPU time if job needs to be cancelled

**Risk:** 
- **Likelihood:** Medium (if tokens expire in hours/days and jobs run 30-60 min)
- **Severity:** Medium 
- **Impact:** User frustration, wasted GPU resources if bad job can't be stopped
- **Internal context:** Less critical - users can reach out to admin/team lead

**Potential Fix:**
1. **Token refresh mechanism**: Issue refresh tokens that extend validity
2. **Job ownership by user_id**: Allow status/cancel using any valid token for that user_id
3. **Long token expiry**: Set token expiry to weeks/months for internal use (30-90 days)
4. **Grace period**: Allow read operations (status, results) with expired tokens for X hours
5. **Session tokens**: Separate short-lived session tokens from long-lived API tokens

**Recommended:** #3 (long expiry) + #2 (user_id ownership) for internal use case

---

## Issue 2: Token gets stolen or leaked - unauthorized job submissions

**Consequence:**
- Token accidentally committed to git repo
- Token shared in Slack message
- Token in screenshot/screen share
- Malicious insider gets token
- Attacker can submit jobs as that user
- Attacker consumes that user's GPU quota
- Potentially exfiltrate competition data
- Attribution is wrong (jobs attributed to victim user)

**Risk:**
- **Likelihood:** Medium-High (human error is common)
- **Severity:** Medium (internal network, limited damage)
- **Impact:** Resource abuse, data leakage, wrong attribution
- **Internal context:** Trust-but-verify; internal networks are somewhat protected

**Potential Fix:**
1. **Token rotation**: Force periodic token regeneration (every 30-90 days)
2. **IP whitelisting**: Restrict tokens to specific IP ranges/VPN
3. **Audit logging**: Log all token usage with IP/timestamp
4. **Rate limiting**: Limit damage from stolen token (already implemented)
5. **Anomaly detection**: Alert on unusual usage patterns (new IP, spike in submissions)
6. **Token scopes**: Limit tokens to specific competitions/projects
7. **Revocation endpoint**: Allow users to instantly revoke compromised tokens
8. **Alert on new device**: Notify user when token used from new IP

**Recommended:** #1 (rotation) + #3 (audit logging) + #7 (revocation) for baseline security

---

## Issue 3: Multiple users sharing same token - can't track who submitted what

**Consequence:**
- Team lead shares their token with team members
- All jobs appear to be from team lead's user_id
- Can't identify who actually submitted each job
- Can't attribute resource usage correctly
- Can't debug user-specific issues
- Accountability is lost
- Metrics are wrong (one user appears super active)

**Risk:**
- **Likelihood:** High (convenient shortcut in companies)
- **Severity:** Medium
- **Impact:** Loss of attribution, harder to debug issues, unfair resource allocation
- **Internal context:** Common pattern in internal tools, often accepted

**Potential Fix:**
1. **Enforce one-token-per-user**: Technical controls prevent sharing
2. **Easy token generation**: Make it trivial for each user to get their own token
3. **Self-service portal**: Users can create/manage their own tokens via web UI
4. **SSO integration**: Auto-generate tokens from company SSO (Google/Okta/etc)
5. **Job metadata field**: Optional "submitted_by" field for team attribution
6. **Device fingerprinting**: Detect when same token used from multiple machines
7. **Token usage alerts**: Notify user when token used from unusual location
8. **Education**: Simply document why token sharing is bad

**Recommended:** #2 (easy generation) + #3 (self-service) + #8 (education). Accept that sharing will happen, make individual tokens easier.

---

## Issue 4: Token database corruption - all users locked out

**Consequence:**
- SQLite database file gets corrupted
- All token validation queries fail
- No user can submit jobs
- Complete system outage
- Must restore from backup or regenerate all tokens
- All in-progress work blocked

**Risk:**
- **Likelihood:** Low (SQLite is robust)
- **Severity:** Critical (total outage)
- **Impact:** Complete work stoppage until recovery
- **Internal context:** High impact but low likelihood; fixable by admin

**Potential Fix:**
1. **Database backups**: Automated daily backups with retention
2. **WAL mode**: Use SQLite WAL mode for better corruption resistance
3. **Separate token DB**: Keep tokens in separate database from jobs
4. **Fallback auth**: Emergency admin override token hard-coded in config
5. **Database integrity checks**: Run `PRAGMA integrity_check` periodically
6. **Replication**: Mirror token DB to secondary instance
7. **Postgres/MySQL**: Use more robust RDBMS instead of SQLite
8. **Health checks**: Monitor DB health, alert before corruption

**Recommended:** #1 (backups) + #2 (WAL mode) + #4 (emergency override) for resilience

---

## Issue 5: Token never expires - security risk over time

**Consequence:**
- Tokens created years ago still valid
- Former employees' tokens still work
- Compromised tokens remain valid indefinitely
- No forcing of security hygiene
- Old tokens accumulate in database
- Harder to audit current active users

**Risk:**
- **Likelihood:** High (default if no expiry)
- **Severity:** Medium (internal network has some protection)
- **Impact:** Former employee access, accumulated security debt
- **Internal context:** Depends on HR offboarding process

**Potential Fix:**
1. **Set reasonable expiry**: 90 days for internal use
2. **Auto-renewal**: Extend expiry on each use (rolling window)
3. **Expiry warnings**: Email user 7 days before expiry
4. **Offboarding integration**: Revoke tokens when employee leaves (HR system hook)
5. **Periodic audit**: Manually review and revoke old tokens quarterly
6. **Inactive timeout**: Expire tokens not used in 30 days
7. **Maximum lifetime**: Hard limit of 1 year regardless of activity
8. **Refresh tokens**: Issue short-lived tokens (24h) with refresh mechanism

**Recommended:** #2 (auto-renewal) + #6 (inactive timeout) + #4 (offboarding hook) for balance of convenience and security

---

## Issue 6: User deletes account but token still valid

**Consequence:**
- User leaves company
- HR marks them as terminated in system
- Their GPU cluster token still works
- They could submit jobs from home/personal machine
- Resource theft
- Data exfiltration risk
- Continued access despite termination

**Risk:**
- **Likelihood:** High (if not integrated with HR systems)
- **Severity:** High (unauthorized access post-termination)
- **Impact:** Security breach, resource theft, potential IP theft
- **Internal context:** Critical for companies with IP concerns

**Potential Fix:**
1. **HR system integration**: Auto-revoke on termination date
2. **LDAP/AD sync**: Link tokens to active directory status
3. **Manual revocation checklist**: Include in offboarding checklist
4. **Periodic user validation**: Quarterly check that token owners are still employees
5. **SSO integration**: Tokens die when SSO access revoked
6. **Network access**: Rely on VPN/network access being revoked (defense in depth)
7. **IP whitelist**: Tokens only work from company network
8. **Admin dashboard**: Easy way for IT to see and revoke all tokens for a user

**Recommended:** #5 (SSO integration) + #7 (IP whitelist) + #8 (admin dashboard) for comprehensive offboarding

---

## Issue 7: Token collision (same hash for different users)

**Consequence:**
- Two different tokens hash to same value (SHA256 collision)
- User B can authenticate as User A
- Wrong user attribution
- Security bypass
- Data/results go to wrong user

**Risk:**
- **Likelihood:** Extremely Low (SHA256 collision is cryptographically infeasible)
- **Severity:** Critical (if it happened)
- **Impact:** Authentication bypass
- **Internal context:** Not a real concern with proper crypto

**Potential Fix:**
1. **Use SHA256**: Already cryptographically secure (2^256 space)
2. **Salt tokens**: Add user-specific salt before hashing (overkill but safe)
3. **Unique constraint**: Database enforces token_hash uniqueness
4. **Check on creation**: Verify hash doesn't exist before issuing token
5. **Use UUIDs**: Store full token UUID instead of hashing

**Recommended:** #1 is sufficient. #3 (unique constraint) as extra safety. Not a real problem in practice.

---

## Issue 8: Brute force token guessing attempts

**Consequence:**
- Attacker tries millions of random tokens
- Could eventually guess valid token
- Rate limiting on auth checks needed
- Could DoS the auth system with requests
- If token space is small, could succeed

**Risk:**
- **Likelihood:** Low (internal network, tokens are UUIDs)
- **Severity:** Medium (if successful)
- **Impact:** Unauthorized access if successful; service disruption from attempts
- **Internal context:** Internal network makes external brute force harder

**Potential Fix:**
1. **Large token space**: Use UUID4 (128 bits) or longer
2. **Rate limit auth attempts**: Already implemented (100/min per IP)
3. **Account lockout**: Lock user account after N failed auth attempts
4. **CAPTCHA**: Require CAPTCHA after several failures (overkill for API)
5. **IP blocking**: Block IPs with repeated failures
6. **Monitoring**: Alert on unusual auth failure patterns
7. **Network security**: Only accessible from company VPN/network
8. **Token format**: Use unguessable format (not sequential numbers)

**Recommended:** #1 (UUID4) + #2 (rate limiting - already done) + #6 (monitoring). Current implementation is probably sufficient.

---

## Issue 9: Token database grows unbounded over time

**Consequence:**
- New token created for every user request
- Old expired tokens never deleted
- Database grows to millions of rows
- Auth queries slow down
- Database file size explodes
- Backup/restore takes forever
- Eventually hits disk space limits

**Risk:**
- **Likelihood:** High (without cleanup)
- **Severity:** Low (performance degrades gradually)
- **Impact:** Slower auth, larger backups, eventual disk space issues
- **Internal context:** Easy to fix with periodic cleanup

**Potential Fix:**
1. **Periodic cleanup**: Cron job deletes tokens expired > 30 days ago
2. **Token reuse**: Update existing token instead of creating new
3. **One token per user**: Enforce single active token per user
4. **Expiry on read**: Delete expired tokens when encountered
5. **Database partitioning**: Separate active/expired tables
6. **Archival**: Move old tokens to cold storage
7. **Retention policy**: Delete tokens > 1 year old
8. **Monitor growth**: Alert when token table exceeds size threshold

**Recommended:** #1 (periodic cleanup) + #3 (one per user) + #7 (retention policy) for simple maintenance

---

## Summary & Priority

### Critical Issues (Fix immediately):
1. **Token expiry during job execution** - Implement long expiry (90 days) + user_id-based operations
2. **User deletes account but token still valid** - Add SSO integration + IP whitelist
3. **Database corruption** - Implement backups + WAL mode + emergency override

### High Priority (Fix soon):
4. **Token stolen/leaked** - Add audit logging + revocation endpoint + rotation policy
5. **Token never expires** - Implement auto-renewal + inactive timeout
6. **DB grows unbounded** - Add cleanup job + retention policy

### Medium Priority (Monitor and fix if occurs):
7. **Multiple users sharing token** - Make token generation easy + educate users
8. **Brute force attempts** - Add monitoring (rate limiting already exists)

### Low Priority (Accept the risk):
9. **Token collision** - Already using SHA256, no action needed

### Non-Issues:
- Token collision is cryptographically infeasible with SHA256

---

## Recommended Implementation Order

1. **Week 1**: Database backups + WAL mode + emergency admin token
2. **Week 2**: Token expiry (90 days) + auto-renewal on use + inactive timeout (30 days)
3. **Week 3**: Audit logging (all token usage) + token revocation endpoint
4. **Week 4**: Cleanup job for expired tokens + retention policy
5. **Month 2**: SSO integration OR IP whitelisting (if needed)
6. **Month 3**: Admin dashboard for token management
7. **Ongoing**: Monitor metrics, adjust policies based on usage patterns

For an internal tool, the above strikes a balance between security and usability.

