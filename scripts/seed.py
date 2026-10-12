"""Catalogue de démonstration, sans comptes ni résultats IA inventés."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import Settings
from backend.service import Library
library=Library(Settings())
rows=[('Introduction au deep learning','Équipe pédagogique','Intelligence artificielle','Réseaux neuronaux, apprentissage supervisé et architectures profondes.'),('Bases de données relationnelles','Équipe pédagogique','Data Science','Modélisation, SQL, transactions et index.'),('Réseaux informatiques','Équipe pédagogique','Réseaux','Protocoles TCP/IP et sécurité des réseaux.'),('Traitement automatique du langage','Équipe pédagogique','Intelligence artificielle','Embeddings, recherche sémantique et modèles de langage.')]
with library.db.transaction() as tx:
    for title,author,category,description in rows:
        if tx.one('SELECT id FROM books WHERE title=:title',{'title':title}):continue
        bid=tx.insert('books',title=title,author=author,category=category,description=description)
        for i in range(2):tx.insert('copies',book_id=bid,code=f'DEMO-{bid}-{i+1}')
print('Catalogue de démonstration prêt. Ajouter des PDF autorisés depuis Documents.')
