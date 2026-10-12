"""Création explicite du premier administrateur ; jamais via inscription publique."""
import argparse
import getpass
import secrets
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import Settings
from backend.service import Library

parser=argparse.ArgumentParser()
parser.add_argument('--email',default='adnane@bibliotheque.local')
parser.add_argument('--name',default='Adnane Edrissi')
parser.add_argument('--generate-password',action='store_true')
args=parser.parse_args()
library=Library(Settings())
with library.db.transaction() as tx:
    if tx.one("SELECT id FROM users WHERE role='admin'"):
        print('Un administrateur existe déjà. Aucun compte modifié.');sys.exit(0)
password=secrets.token_urlsafe(18) if args.generate_password else getpass.getpass('Mot de passe administrateur (10 caractères minimum) : ')
user=library.register({'email':args.email,'name':args.name,'password':password})
with library.db.transaction() as tx:tx.execute("UPDATE users SET role='admin' WHERE id=:id",{'id':user['id']}).close()
print('Administrateur créé :',args.email)
if args.generate_password:print('Mot de passe généré (à conserver localement) :',password)

