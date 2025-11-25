# Objectif global
**Toujours répondre en français, ne pas créer de doc suplémentaire sauf demande explicite**

Maintenir et enrichir l'extracteur de tableaux PDF décrit dans `PRD.md`. Le dépôt existe déjà : on travaille par incréments centrés sur la chaîne GMFT (prétraitement PDF → détection → exports).

---

## 🧭 Workflow avant toute action

1. **Docs socle à relire systématiquement** :
   - `docs/PRD.md` (vision produit GMFT, périmètre extraction/export).
   - `docs/PROMPT.md` (ce document) pour la méthode de travail et les invariants.
2. **Identifier la feature concernée** :
   - Lire `docs/features/<feature>.md` pour connaître l'état de la feature GMFT, les endpoints touchés et les tests existants.
3. **S'il y a des dépendances**, ouvrir les fiches features associées pour comprendre les invariants avant toute modification.
4. **Une fois cette lecture terminée**, seulement alors ouvrir les fichiers de code ciblés et appliquer la démarche TDD décrite ci-dessous.

L'assistant ne scanne pas le code en masse : il suit l'ordre docs → fichiers ciblés → implémentation contrôlée.

## 🔁 Workflow de développement

Pour **chaque intervention** :
1. **Comprendre** → relire les fiches state des features GMFT (ingestion, détection, exports...).
2. **Adapter les tests** → Avant de modifier le code on écrit/modifie les tests que le code devra validé ensuite. Se renseigner sur `docs/TEST_REGISTRY.md` avant.
3. **Implémenter** → appliquer la modification demandée (backend, front, CLI, hooks).
4. **Vérifier** → exécuter les tests/commandes référencés dans la fiche ou dans `docs/TEST_REGISTRY.md`.
5. **Documenter** → mettre à jour uniquement la fiche feature concernée si l'interface, l'API ou les scripts changent, attention a ne pas sur-représenter les modifications récentes.

Entre chaque étape, demander à l'utilisateur confirmation.

---

## 📊 Documentation

**Ne pas modifier la PRD** sans consigne. Elle fixe la vision et l'architecture ; seules les fiches de features capturent l'exécution quotidienne.


## 🔒 Rappels essentiels

- Pas d'ajout de documentation inutile.
- Toujours partir des fiches state et des runbooks.
- Répondre à la question posée, sans extrapoler.
