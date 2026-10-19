# Tableau de bord Streamlit du TP4

Le tableau de bord affiche les ventes autour de J0, avec filtres par événement,
ville, catégorie, années et taille de la fenêtre d'observation.

## Lancer depuis le dossier `TP4`

À la racine du projet, dans PowerShell :

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit affiche l'adresse locale à ouvrir dans le navigateur. Les données CSV
doivent rester dans le sous-dossier `TP4`.

## Préparer un autre ordinateur

Créer un environnement Python 3.10 ou plus récent, puis installer les
dépendances :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Les quantités négatives sont ramenées à zéro pour visualiser la demande, les
doublons date-magasin-catégorie sont dédupliqués, et les jours non observés
restent des valeurs manquantes plutôt que des ventes nulles. Toutes les données
du TP sont simulées.
