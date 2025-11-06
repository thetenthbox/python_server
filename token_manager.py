#!/usr/bin/env python3
"""
Token Management Utility
Use this script to create and manage authentication tokens
"""

import sys
import argparse
from datetime import datetime, timedelta
import models
import auth


def create_token_cmd(args):
    """Create a new token"""
    models.init_db()
    
    expires_at = None
    if args.days:
        # Enforce maximum 30 days
        days = min(args.days, 30)
        expires_at = datetime.utcnow() + timedelta(days=days)
        if args.days > 30:
            print(f"⚠  Maximum expiry is 30 days. Setting expiry to 30 days instead of {args.days}.")
    else:
        # Default to 30 days if not specified
        expires_at = datetime.utcnow() + timedelta(days=30)
    
    success = auth.create_token(args.user_id, args.token, expires_at, is_admin=args.admin)
    
    if success:
        print(f"✓ Token created successfully for user: {args.user_id}")
        print(f"  Admin: {'Yes' if args.admin else 'No'}")
        print(f"  Expires at: {expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Token will automatically revoke any existing tokens for this user")
    else:
        print(f"✗ Failed to create token (may already exist)")
        sys.exit(1)


def revoke_token_cmd(args):
    """Revoke a token"""
    models.init_db()
    
    success = auth.revoke_token(args.token)
    
    if success:
        print(f"✓ Token revoked successfully")
    else:
        print(f"✗ Failed to revoke token (not found)")
        sys.exit(1)


def list_tokens_cmd(args):
    """List all active tokens"""
    models.init_db()
    db = next(models.get_db())
    
    tokens = db.query(models.Token).all()
    
    if not tokens:
        print("No tokens found")
        return
    
    print("\nTokens:")
    print("-" * 90)
    print(f"{'User ID':<30} {'Admin':<10} {'Active':<10} {'Expires At':<30}")
    print("-" * 90)
    
    for token in tokens:
        admin = "Yes" if token.is_admin else "No"
        active = "Yes" if token.is_active else "No"
        expires = token.expires_at.strftime("%Y-%m-%d %H:%M:%S") if token.expires_at else "Never"
        print(f"{token.user_id:<30} {admin:<10} {active:<10} {expires:<30}")
    
    db.close()


def main():
    parser = argparse.ArgumentParser(description="Manage authentication tokens")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Create token
    create_parser = subparsers.add_parser("create", help="Create a new token")
    create_parser.add_argument("user_id", help="User ID")
    create_parser.add_argument("token", help="Token string")
    create_parser.add_argument("--days", type=int, help="Expiration in days")
    create_parser.add_argument("--admin", action="store_true", help="Create admin token with elevated privileges")
    create_parser.set_defaults(func=create_token_cmd)
    
    # Revoke token
    revoke_parser = subparsers.add_parser("revoke", help="Revoke a token")
    revoke_parser.add_argument("token", help="Token string to revoke")
    revoke_parser.set_defaults(func=revoke_token_cmd)
    
    # List tokens
    list_parser = subparsers.add_parser("list", help="List all tokens")
    list_parser.set_defaults(func=list_tokens_cmd)
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

