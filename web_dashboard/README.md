# Dashboard EDHS – démarrage

## Lancer le dashboard

Depuis la **racine du projet** (le dossier qui contient `edhs_core` et `web_dashboard`) :

```bash
# 1. Démarrer l’API (dans un premier terminal)
uvicorn edhs_core.main:app --reload

# 2. Démarrer le dashboard (dans un second terminal)
cd "$(dirname "$0")/.."
python -m streamlit run web_dashboard/streamlit_app.py --server.port=8501 --server.headless=false
```

Ou avec Streamlit en ligne de commande :

```bash
streamlit run web_dashboard/streamlit_app.py --server.port=8501
```

## Si la page reste blanche

1. **Rechargement forcé** : Ctrl+Shift+R (Windows/Linux) ou Cmd+Shift+R (Mac).
2. **Vérifier l’URL** : ouvrir `http://localhost:8501` (et non 127.0.0.1 si vous avez des soucis).
3. **Autre navigateur** : tester Chrome ou Firefox.
4. **Désactiver les extensions** : mode navigation privée pour tester.
5. **Vérifier le terminal Streamlit** : une erreur Python peut s’afficher au démarrage.
