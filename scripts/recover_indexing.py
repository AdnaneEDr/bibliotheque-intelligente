"""Relance après arrêt brutal : utiliser uniquement lorsque le backend est arrêté."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import Settings
from backend.service import Library

parser=argparse.ArgumentParser(description='Récupérer les indexations interrompues, backend arrêté.')
parser.add_argument('--backend-stopped',action='store_true',required=True)
parser.parse_args()
library=Library(Settings())
with library.db.transaction() as tx:
    cursor=tx.execute("UPDATE documents SET status='failed', error=:message WHERE status='indexing'",{'message':'Indexation interrompue ; relancer depuis Documents'})
    print('Documents récupérés :',cursor.rowcount)
    cursor.close()
