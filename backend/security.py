import hashlib
import hmac
import secrets
from datetime import datetime, timezone, timedelta

def now():
    return datetime.now(timezone.utc).isoformat()

def expiry(hours):
    return (datetime.now(timezone.utc)+timedelta(hours=hours)).isoformat()

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600_000).hex()
    return f'pbkdf2_sha256$600000${salt}${digest}'

def verify_password(password, encoded):
    try:
        scheme, rounds, salt, expected = encoded.split('$')
        if scheme != 'pbkdf2_sha256':
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

