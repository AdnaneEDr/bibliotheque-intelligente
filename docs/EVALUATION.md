# Évaluation du prototype

Les scénarios ci-dessous correspondent aux étapes 5 et 6 du document. Les résultats réels doivent être consignés après installation des dépendances et exécution sur un corpus autorisé. Une réponse ambiguë ou correcte ne peut pas être validée par un test qui ne fait qu'inspecter le prompt.

| ID | Scénario | Attendu | Résultat réel |
|---|---|---|---|
| T1 | Question couverte par le corpus | Réponse fidèle, document et page vérifiables | À mesurer avec Qwen3 |
| T2 | Question hors corpus | Absence d'information signalée | À mesurer avec Qwen3 |
| T3 | Question ambiguë | Clarification pertinente | À mesurer avec Qwen3 |
| T4 | Résumé court et long | Fidélité, faits et références conservés | À mesurer avec Qwen3 |
| T5 | Comparaison de documents | Points communs et différences sourcés | À mesurer avec Qwen3 |
| T6 | Recherche et recommandations | Pertinence pour la demande et les intérêts | À mesurer avec embeddings réels |
| T7 | Utilisateur non authentifié | 401 pour les accès protégés | Couvert par tests métier et contrat partagé |
| T8 | Action sans autorisation | 403, aucun changement | Couvert par tests métier |
| T9 | Exemplaire indisponible | 409, aucun double emprunt | Couvert par tests métier concurrents |
| T10 | Retour d'un livre réservé | Disponibilité et notification | Couvert par tests métier |
| T11 | PDF invalide ou échec d'indexation | Erreur, état cohérent et relance | États couverts avec double IA ; PDF réel à tester |
| T12 | Prompt injection dans un PDF | Instruction ignorée, autorisations respectées | ACL testées ; résistance du LLM à mesurer |
| T13 | Favoris, collections et historique | Isolation par utilisateur et persistance | Couvert par tests métier SQLite |

Pour chaque réponse IA, relever la question, la réponse attendue, les pages attendues, la réponse obtenue, les sources retournées, le temps et une note humaine de pertinence. La liste de pages retournée correspond aux passages retrouvés ; vérifier que chaque affirmation possède réellement une source.

Indicateurs : temps médian et p95, taux de réponses correctes, proportion de réponses contenant au moins une affirmation non justifiée, pertinence des passages, taux d'erreur HTTP et taux de réussite des contrôles de droits. Ne jamais renseigner des performances supposées comme des mesures.
