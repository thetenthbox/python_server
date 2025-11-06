"""
Authentication and token validation
"""

import hashlib
from datetime import datetime, timedelta
from typing import Optional
import models


def hash_token(token: str) -> str:
    """Hash a token using SHA256"""
    return hashlib.sha256(token.encode()).hexdigest()


def validate_token(token: str, db) -> Optional[tuple]:
    """
    Validate token and return (user_id, is_admin) if valid
    Returns None if invalid
    """
    token_hash = hash_token(token)
    
    token_obj = db.query(models.Token).filter(
        models.Token.token_hash == token_hash
    ).first()
    
    if not token_obj:
        return None
    
    # Check if token is active
    if not token_obj.is_active:
        return None
    
    # Check expiration
    if token_obj.expires_at and token_obj.expires_at < datetime.utcnow():
        return None
    
    return (token_obj.user_id, token_obj.is_admin)


def create_token(user_id: str, token: str, expires_at: Optional[datetime] = None, is_admin: bool = False) -> bool:
    """
    Create a new token in the database
    Enforces:
    - One token per user (revokes existing tokens for this user)
    - Maximum 30-day expiry
    - Admin flag for special privileges
    Returns True if successful
    """
    db = next(models.get_db())
    try:
        token_hash = hash_token(token)
        
        # Enforce maximum 30-day expiry
        if expires_at is None:
            expires_at = datetime.utcnow() + timedelta(days=30)
        else:
            max_expiry = datetime.utcnow() + timedelta(days=30)
            if expires_at > max_expiry:
                expires_at = max_expiry
        
        # Revoke any existing tokens for this user (one token per user)
        existing_user_tokens = db.query(models.Token).filter(
            models.Token.user_id == user_id,
            models.Token.is_active == True
        ).all()
        
        for old_token in existing_user_tokens:
            old_token.is_active = False
        
        # Check if this specific token hash already exists
        existing_hash = db.query(models.Token).filter(
            models.Token.token_hash == token_hash
        ).first()
        
        if existing_hash:
            return False
        
        new_token = models.Token(
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at,
            is_active=True,
            is_admin=is_admin
        )
        
        db.add(new_token)
        db.commit()
        return True
    except Exception as e:
        print(f"Error creating token: {e}")
        return False
    finally:
        db.close()


def revoke_token(token: str) -> bool:
    """
    Revoke a token
    Returns True if successful
    """
    db = next(models.get_db())
    try:
        token_hash = hash_token(token)
        
        token_obj = db.query(models.Token).filter(
            models.Token.token_hash == token_hash
        ).first()
        
        if not token_obj:
            return False
        
        token_obj.is_active = False
        db.commit()
        return True
    except Exception as e:
        print(f"Error revoking token: {e}")
        return False
    finally:
        db.close()

