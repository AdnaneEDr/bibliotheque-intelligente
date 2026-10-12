# Validation du projet le 12 octobre 2026

La connexion Oracle au schéma BIBLIOTHEQUE et au service orclpdb est validée. Les tables sont créées, le corpus a été chargé et l'indexation Chroma a été exécutée avec le modèle multilingue réel.

## Résultats

- 22 tests automatisés réussis, incluant FastAPI/TestClient et HTTP local. Les tests métier isolés utilisent SQLite.
- 12 documents de démonstration, 30 pages indexées, 16 notices au catalogue.
- Pages étudiant vérifiées avec Streamlit AppTest et l'API reliée à Oracle : accueil, catalogue, documents, assistant, analyse, espace personnel, recommandations et notifications.
- Question réelle TCP/UDP exécutée avec Qwen3 via Ollama, réponse et pages sources obtenues.
- Backend et interface relancés et accessibles localement.

## Interface

Accueil avec indicateurs réels et raccourcis, catalogue en fiches filtrables, galerie documentaire, discussion par questions indépendantes avec sources, notifications en fiches, thème bleu foncé et turquoise.

## Limites

Qwen3 s'exécute sur le processeur de ce poste ; le premier test de génération a pris environ trois minutes. Une génération réussie ne constitue pas une évaluation exhaustive de fidélité ou de sécurité. Les scénarios d'évaluation humaine restent décrits dans EVALUATION.md. Les vérifications de l'interface par AppTest ne remplacent pas une revue graphique sur tous les formats d'écran.
