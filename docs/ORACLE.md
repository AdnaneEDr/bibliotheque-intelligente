# Configuration Oracle du poste

L'installation trouvée est `C:\oracle19c`, Oracle 19.3. La configuration TNS indique un hôte `localhost`, un port `1521` et un service `orcl`. Ces informations proviennent des fichiers de configuration ; la disponibilité réelle du service n'a pas pu être vérifiée.

La tentative locale SQLPlus `/ as sysdba` effectuée dans l'environnement de travail a échoué avec `ORA-12560`. La consultation du gestionnaire de services Windows est interdite à cet environnement. Il ne faut pas conclure de ces résultats que la base est absente ou arrêtée sur le poste normal.

Le projet est configuré pour **Oracle**, sans repli automatique sur SQLite. Le mot de passe est volontairement vide tant que le compte dédié n'est pas créé. Aucun mot de passe d'un compte existant n'a été recherché ou modifié.

## Mise en place sans ancien mot de passe

Depuis PowerShell sur le poste, avec les droits Oracle locaux appropriés :

```powershell
.\scripts\setup_oracle.ps1
.\scripts\install.ps1
.\.venv\Scripts\python.exe scripts\check_oracle.py
```

Le script utilise l'authentification Windows NTS pour la préparation administrative. Il peut démarrer le service `OracleServiceorcl` et le listener si ceux-ci sont arrêtés. Il sélectionne automatiquement la seule PDB ouverte en lecture/écriture dans une CDB ; s'il y a plusieurs candidates ou aucune, il s'arrête pour éviter de choisir arbitrairement. Dans une base non-CDB, il reste dans la base courante.

Le compte applicatif `BIBLIOTHEQUE` reçoit un mot de passe aléatoire, les droits de connexion/création de ses objets et un quota de 500 Mo dans le tablespace utilisateur par défaut. Le script refuse de modifier un compte déjà présent. Le secret est conservé dans `.env` local, exclu de l'archive et de Git. En cas d'échec après création, un script SQL temporaire peut contenir le secret pour récupération locale ; ne pas le partager. Le dossier `work/` est également exclu de l'archive et de Git.

Si l'authentification locale est refusée hors de cet environnement, un administrateur Oracle devra créer le compte dédié ou autoriser le compte Windows approprié. Aucun ancien mot de passe n'est requis lorsque l'authentification administrative Windows est disponible. Les scripts ne contournent pas les contrôles d'accès Oracle.

Références : [création de comptes Oracle 19c](https://docs.oracle.com/en/database/oracle/oracle-database/19/dbseg/creating-user-accounts.html), [connexion python-oracledb](https://python-oracledb.readthedocs.io/en/latest/user_guide/connection_handling.html).
