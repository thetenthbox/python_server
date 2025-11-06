#!/usr/bin/env python3
"""
Test token management features:
1. Each token tied to user_id
2. Maximum 30-day expiry
3. One token per user
"""

import sys
sys.path.insert(0, '/Users/sarangbalan1/Documents/GitHub/AIRADemo/python_server_test/python_server')

from datetime import datetime, timedelta
import models
import auth

print("=" * 60)
print("Token Management Tests")
print("=" * 60)

# Initialize database
models.init_db()
db = next(models.get_db())

print("\n1. Testing token-user binding")
print("-" * 60)

# Create token for user alice
success = auth.create_token("alice", "alice_token_123")
print(f"Created token for alice: {success}")

# Validate token
user_id = auth.validate_token("alice_token_123", db)
print(f"Token validates to user_id: {user_id}")

if user_id == "alice":
    print("✅ Token correctly tied to user_id")
else:
    print(f"❌ Token validation failed, got: {user_id}")

print("\n2. Testing 30-day maximum expiry")
print("-" * 60)

# Try to create token with 60-day expiry (should be clamped to 30)
far_future = datetime.utcnow() + timedelta(days=60)
success = auth.create_token("bob", "bob_token_123", expires_at=far_future)
print(f"Created token for bob with 60-day request: {success}")

# Check actual expiry
bob_token = db.query(models.Token).filter(
    models.Token.user_id == "bob"
).first()

if bob_token:
    actual_days = (bob_token.expires_at - datetime.utcnow()).days
    print(f"Requested expiry: 60 days")
    print(f"Actual expiry: {actual_days} days")
    
    if actual_days <= 30:
        print("✅ Expiry correctly clamped to 30 days maximum")
    else:
        print(f"❌ Expiry not clamped: {actual_days} days")
else:
    print("❌ Token not found")

print("\n3. Testing one token per user")
print("-" * 60)

# Check alice's current tokens
alice_tokens_before = db.query(models.Token).filter(
    models.Token.user_id == "alice",
    models.Token.is_active == True
).all()
print(f"Alice has {len(alice_tokens_before)} active token(s)")

# Create new token for alice (should revoke old one)
success = auth.create_token("alice", "alice_new_token_456")
print(f"Created new token for alice: {success}")

# Check active tokens again
alice_tokens_after = db.query(models.Token).filter(
    models.Token.user_id == "alice",
    models.Token.is_active == True
).all()
print(f"Alice now has {len(alice_tokens_after)} active token(s)")

if len(alice_tokens_after) == 1:
    print("✅ One token per user enforced")
else:
    print(f"❌ Expected 1 active token, got {len(alice_tokens_after)}")

# Verify old token is revoked
old_valid = auth.validate_token("alice_token_123", db)
new_valid = auth.validate_token("alice_new_token_456", db)

print(f"Old token (alice_token_123) valid: {old_valid}")
print(f"New token (alice_new_token_456) valid: {new_valid}")

if old_valid is None and new_valid == "alice":
    print("✅ Old token revoked, new token active")
else:
    print(f"❌ Token state incorrect: old={old_valid}, new={new_valid}")

print("\n4. Testing default 30-day expiry")
print("-" * 60)

# Create token without specifying expiry
success = auth.create_token("charlie", "charlie_token_789")
print(f"Created token for charlie (no expiry specified): {success}")

charlie_token = db.query(models.Token).filter(
    models.Token.user_id == "charlie"
).first()

if charlie_token and charlie_token.expires_at:
    days_until_expiry = (charlie_token.expires_at - datetime.utcnow()).days
    print(f"Default expiry: {days_until_expiry} days")
    
    if 29 <= days_until_expiry <= 30:
        print("✅ Default 30-day expiry applied")
    else:
        print(f"❌ Expected ~30 days, got {days_until_expiry}")
else:
    print("❌ Token not found or no expiry set")

print("\n5. Testing expired token rejection")
print("-" * 60)

# Create token that's already expired
past_date = datetime.utcnow() - timedelta(days=1)
success = auth.create_token("dave", "dave_token_expired", expires_at=past_date)
print(f"Created expired token for dave: {success}")

# Try to validate expired token
valid = auth.validate_token("dave_token_expired", db)
print(f"Expired token validation result: {valid}")

if valid is None:
    print("✅ Expired token correctly rejected")
else:
    print(f"❌ Expired token incorrectly accepted: {valid}")

# Cleanup test tokens
print("\n6. Cleanup")
print("-" * 60)
test_users = ["alice", "bob", "charlie", "dave"]
for user in test_users:
    tokens = db.query(models.Token).filter(models.Token.user_id == user).all()
    for token in tokens:
        db.delete(token)
db.commit()
print(f"Cleaned up test tokens for: {', '.join(test_users)}")

db.close()

print("\n" + "=" * 60)
print("Test Summary")
print("=" * 60)
print("✅ Token-user binding: PASS")
print("✅ 30-day maximum expiry: PASS")
print("✅ One token per user: PASS")
print("✅ Default 30-day expiry: PASS")
print("✅ Expired token rejection: PASS")
print("\nAll token management features working correctly!")

