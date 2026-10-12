"""Vérifier le compte du projet et initialiser ses tables, sans exposer de secret."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import Settings
from backend.db import Database

settings=Settings()
if settings.db_backend!='oracle':
    raise SystemExit('DB_BACKEND doit être oracle pour ce contrôle.')
try:
    db=Database(settings)
    with db.transaction() as tx:
        row=tx.one("SELECT USER AS account, SYS_CONTEXT('USERENV','SERVICE_NAME') AS service FROM dual")
        count=tx.one("SELECT COUNT(*) AS count FROM user_tables WHERE table_name IN ('USERS','BOOKS','DOCUMENTS','LOANS')")
    print('Connexion Oracle réussie :',row['account'],'service',row['service'])
    print('Tables principales présentes :',count['count'],'sur 4')
except Exception as exc:
    message=str(exc)
    if settings.oracle_password:message=message.replace(settings.oracle_password,'[secret masqué]')
    raise SystemExit('Vérification Oracle échouée : '+message)
