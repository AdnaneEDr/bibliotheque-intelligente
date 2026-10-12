import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.config import Settings

available=all(importlib.util.find_spec(name) for name in ['fastapi','httpx','multipart'])

@unittest.skipUnless(available,'Dépendances FastAPI/httpx/multipart non installées')
class FastApiTests(unittest.TestCase):
    def test_fastapi_contract_and_swagger(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        with tempfile.TemporaryDirectory() as folder,patch('backend.main.Settings',return_value=Settings(data_dir=Path(folder), db_backend='sqlite')):
            with TestClient(app) as client:
                self.assertEqual(client.get('/api/health').status_code,200)
                self.assertEqual(client.get('/api/books').status_code,401)
                schema=client.get('/openapi.json').json()
                self.assertIn('/api/questions',schema['paths']);self.assertIn('/api/documents',schema['paths'])
                payload={'name':'Adnane','email':'test@local.example','password':'password-test-123'}
                self.assertEqual(client.post('/api/auth/register',json=payload).status_code,201)
                token=client.post('/api/auth/login',json=payload).json()['access_token']
                header={'Authorization':'Bearer '+token}
                self.assertEqual(client.get('/api/me',headers=header).status_code,200)
                self.assertEqual(client.post('/api/documents',headers=header,files={'file':('a.pdf',b'%PDF-test')},data={'title':'PDF'}).status_code,403)

