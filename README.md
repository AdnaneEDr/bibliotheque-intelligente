# Bibliothèque universitaire intelligente

Projet de **Adnane Edrissi** — Ingénierie Informatique et Réseaux, filière AI et Data Science, 5ème année, groupe 5IASDT G2 - G22.

L'application comprend une interface Streamlit et une API FastAPI, un dépôt SQL Oracle, et un pipeline documentaire Chroma / Sentence Transformers / Qwen3 via Ollama. **Oracle est désormais le choix par défaut et le choix du projet.** SQLite sert uniquement aux tests isolés. Les intégrations externes doivent être installées et validées sur le poste cible.

## Lancer sous Windows

Préparer Python 3.11 ou 3.12 et une connexion Internet pour télécharger les bibliothèques et les modèles. Dans PowerShell, se placer dans le dossier du projet :

```powershell
.\scripts\setup_oracle.ps1
.\scripts\install.ps1
.\.venv\Scripts\python.exe scripts\check_oracle.py
.\.venv\Scripts\python.exe scripts\bootstrap.py --generate-password
.\.venv\Scripts\python.exe scripts\seed.py
ollama pull qwen3:4b
.\scripts\start.ps1
```

Exécuter `setup_oracle.ps1` dans PowerShell avec les droits nécessaires pour consulter/démarrer les services Oracle et avec un compte Windows autorisé par Oracle à se connecter `/ as sysdba`. Le script découvre une PDB ouverte si la base est multitenant, crée un nouveau compte `BIBLIOTHEQUE` et enregistre un mot de passe généré dans `.env`. Il ne réinitialise jamais un compte existant. Les droits administrateur Windows seuls ne garantissent pas l'appartenance au groupe Oracle DBA.

Le script de création affiche un mot de passe administrateur aléatoire à conserver localement. Le compte par défaut est `adnane@bibliotheque.local`. Aucun mot de passe administrateur fixe n'est fourni. Le script ne remplace jamais un administrateur existant. Le catalogue de démonstration contient des notices fictives signalées comme telles, sans PDF ni réponses IA fabriquées.

Interface : <http://localhost:8501>. Documentation des endpoints : <http://localhost:8000/docs>. Le backend et l'interface sont liés à localhost. `Ctrl+C` dans le terminal de lancement arrête l'interface et le backend créé par le script.

Si Ollama n'est pas déjà lancé, exécuter `ollama serve` dans un autre terminal. Le premier import de PDF télécharge le modèle d'embeddings si nécessaire. Le choix initial est `paraphrase-multilingual-MiniLM-L12-v2`. Les paramètres de découpage et le seuil de distance restent à calibrer avec le corpus réel.

Lancement séparé si nécessaire :

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
# Dans un deuxième terminal :
.\.venv\Scripts\python.exe -m streamlit run frontend/app.py --server.address 127.0.0.1
```

## Utilisation

1. Se connecter comme administrateur. Créer des comptes étudiants via le formulaire public. Attribuer le rôle bibliothécaire depuis Administration.
2. Ajouter des livres et leurs exemplaires dans Gestion du catalogue. Le code d'exemplaire est unique.
3. Importer un PDF textuel universitaire dans Documents, puis attendre l'indexation. Les PDF scannés nécessitent un OCR préalable. La visibilité `private` limite le document à son propriétaire et aux administrateurs.
4. Poser une question dans Assistant IA. Le serveur filtre les documents autorisés avant la recherche vectorielle. Sans passage suffisamment pertinent, l'absence d'information est signalée sans appeler le modèle.
5. Produire un résumé, extraire les notions clés ou comparer deux à cinq documents. Les documents longs sont traités par lots puis synthétisés.
6. Consulter favoris, collections, historique, notifications et recommandations. Le personnel enregistre les emprunts et retours. Une réservation active donne priorité au premier étudiant de la file.

Les sources retournées sont les pages retrouvées ou analysées. Elles facilitent une vérification humaine ; elles ne constituent pas une preuve automatique que toutes les affirmations générées sont exactes. Le prompt limite les réponses au contexte et traite les instructions documentaires comme des données. La résistance effective du modèle aux injections doit être évaluée avec des attaques réelles.

## Oracle 19c

Copier `.env.example` en `.env`, puis définir :

```dotenv
DB_BACKEND=oracle
ORACLE_USER=BIBLIOTHEQUE
ORACLE_PASSWORD=mot_de_passe_local
ORACLE_DSN=localhost:1521/orcl
```

Utiliser le schéma dédié créé par le script, avec les privilèges de session, création de tables/séquences et un quota de 500 Mo. La création d'index sur ses propres tables ne nécessite pas de privilège `CREATE ANY INDEX`. L'utilisateur de l'application n'est pas `SYS` ou `SYSTEM`. Les tables sont initialisées au démarrage. La configuration Oracle trouvée sur ce poste indique `localhost:1521/orcl` ; le script découvre le service de la PDB retenue si nécessaire. Le pilote `python-oracledb` utilise le mode Thin.

Les données SQLite ne sont pas migrées automatiquement vers Oracle. Le dépôt Oracle est implémenté mais n'a pas été testé contre une instance réelle dans cet environnement. Exécuter les scénarios métier et vérifier les transactions sur l'instance cible avant de présenter cette intégration comme validée.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Les tests métier utilisent une vraie base SQLite temporaire et un double du moteur IA. Ils vérifient droits, sessions, isolation des données, emprunts concurrents, réservations, sources, erreurs d'indexation et contrat REST partagé. Le test FastAPI utilise TestClient lorsque ses dépendances sont présentes. Le test HTTP utilise un vrai serveur local lorsque l'environnement autorise les sockets.

Les résultats disponibles et les vérifications restantes sont consignés dans `docs/VALIDATION.md`. Le plan d'évaluation T1 à T13 figure dans `docs/EVALUATION.md`. Ne pas confondre les réponses du double de test avec une évaluation de Qwen3.

## Dépannage sans dépendances

Le cœur métier et un serveur REST de dépannage fonctionnent avec la bibliothèque standard Python :

```powershell
$env:DB_BACKEND='sqlite' # Seulement pour le dépannage isolé, pas le projet Oracle
python -m backend.dev_server
```

Ce serveur reste strictement local, ne remplace pas le lancement FastAPI normal, et n'offre ni Swagger, ni import PDF multipart, ni limitation des tentatives de connexion. Il permet de tester les endpoints métier avec un client HTTP. Aucun résultat IA n'est simulé dans l'application réelle : une intégration indisponible produit une erreur explicite ou une absence de contexte.

## Structure

```text
backend/config.py       Configuration et chargement .env
backend/db.py           Dépôt transactionnel SQLite / Oracle
backend/security.py     PBKDF2 et sessions par jetons opaques
backend/service.py      Règles métier et droits d'accès
backend/routes.py       Contrat REST partagé
backend/main.py         Application FastAPI et fichiers PDF
backend/rag.py          Extraction, embeddings, Chroma et Ollama
backend/dev_server.py   Serveur local de dépannage
frontend/app.py         Interface Streamlit
scripts/                Installation, lancement, initialisation
tests/                  Tests métier, HTTP et FastAPI
docs/                   Architecture, validation et évaluation
```

Les fichiers PDF, la base SQL locale et Chroma sont stockés dans `data/`, exclu de Git. Les sessions sont des jetons aléatoires à durée limitée, stockés uniquement sous forme de hash dans la base. Les rôles sont relus depuis la base à chaque demande. Les mots de passe sont hachés avec PBKDF2-SHA256 et un sel indépendant. Le changement de rôle ou la désactivation révoque les sessions.

## Limites du prototype

L'indexation des PDF et la génération sont synchrones. Pour un déploiement avec plusieurs utilisateurs, prévoir une file de tâches, une pagination, des migrations de schéma, des quotas et une sauvegarde coordonnée de SQL, PDF et Chroma. Une indexation interrompue par un arrêt brutal peut rester en état `indexing` : arrêter le backend puis exécuter `python scripts/recover_indexing.py --backend-stopped` avant une relance depuis Documents. Les rappels de retard sont déclenchés par le personnel ; aucun ordonnanceur automatique n'est activé.

La génération, l'ambiguïté des questions, la pertinence et les hallucinations demandent des tests humains sur le corpus final. La configuration de production doit également prévoir TLS, un gestionnaire de secrets et des contrôles de charge. Le projet est livré comme prototype local, avec les limites de validation indiquées.

## Documentation technique consultée

- [FastAPI — authentification par jeton](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [Chroma — client Python](https://docs.trychroma.com/reference/python)
- [python-oracledb — connexion à Oracle](https://python-oracledb.readthedocs.io/en/latest/user_guide/connection_handling.html)

