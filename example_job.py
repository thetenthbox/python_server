#!/usr/bin/env python3
"""
Example GPU job script
This demonstrates what your submitted Python code might look like
"""

import time

print("Starting GPU job...")

# Simulate some work
for i in range(5):
    print(f"Processing step {i + 1}/5")
    time.sleep(1)

print("Job completed successfully!")
print("Output: 42")

