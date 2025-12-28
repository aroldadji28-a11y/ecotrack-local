# EcoTrack Local - Système participatif de suivi des coûts de vie étudiants

Application web Django pour collecter, analyser et visualiser les données sur les coûts de vie des étudiants dans différents quartiers.

## 🎯 Fonctionnalités

### 1. Formulaire Web de Saisie
- Saisie de dépenses avec validation automatique
- Champs : type de dépense, **quartier (texte libre)**, prix, lieu, date, commentaire
- Upload de photos justificatives
- Validation : prix > 0, date non future, champs obligatoires

### 2. Stockage & Préparation des Données
- Base de données SQLite
- Détection automatique des doublons
- Détection des valeurs aberrantes (prix > 3 écarts-types)
- Annotation des anomalies

### 3. Dashboard de Visualisation
- **Graphiques en séries temporelles** : évolution des prix moyens dans le temps
- **Statistiques par quartier** : moyennes, médianes, extrêmes, nombre de dépenses
- **Statistiques par type de dépense** : analyse par catégorie
- **Box plots** : distribution des prix par quartier
- **Tableaux de synthèse** : statistiques détaillées

### 4. Comparaisons Interactives
- **Quartier vs Quartier** : comparaison détaillée entre deux quartiers
- **Quartier vs Ville** : comparaison d'un quartier avec la moyenne globale
- **Campus vs Environnement immédiat** : analyse comparative spécifique

## 🚀 Installation

### Prérequis
- Python 3.8+
- pip

### Étapes d'installation

1. **Cloner ou télécharger le projet**

2. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

3. **Créer les migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

4. **Créer un superutilisateur (optionnel, pour l'admin)**
```bash
python manage.py createsuperuser
```

5. **Lancer le serveur de développement**
```bash
python manage.py runserver
```

6. **Accéder à l'application**
- Accueil : http://127.0.0.1:8000/
- Admin : http://127.0.0.1:8000/admin/

## 📁 Structure du Projet

```
ecotrack_env/
├── core/                    # Application principale
│   ├── models.py           # Modèle Depense
│   ├── views.py            # Vues (accueil, saisie, dashboard, comparaison)
│   ├── forms.py            # Formulaire de saisie
│   ├── urls.py             # URLs de l'application
│   ├── admin.py            # Configuration admin
│   └── templates/          # Templates HTML
│       ├── base.html       # Template de base
│       ├── accueil.html    # Page d'accueil
│       ├── saisie.html     # Formulaire de saisie
│       ├── dashboard.html  # Dashboard de visualisation
│       └── comparaison.html # Page de comparaisons
├── ecotrack_env/           # Configuration Django
│   ├── settings.py         # Paramètres
│   └── urls.py             # URLs principales
├── media/                   # Fichiers uploadés (photos)
├── db.sqlite3              # Base de données
├── requirements.txt        # Dépendances Python
└── manage.py               # Script de gestion Django
```

## 📊 Utilisation

### Saisir une dépense
1. Cliquer sur "Saisir une dépense" dans le menu
2. Remplir le formulaire avec les informations requises
3. Optionnel : uploader une photo justificative
4. Valider le formulaire

### Consulter le Dashboard
1. Accéder au Dashboard depuis le menu
2. Visualiser les graphiques et statistiques
3. Consulter les tableaux de synthèse par quartier et par type

### Effectuer des comparaisons
1. Aller dans "Comparaisons" depuis le menu
2. Choisir le type de comparaison (onglets)
3. Sélectionner les quartiers à comparer
4. Visualiser les résultats avec graphiques et statistiques

## 🔧 Configuration

### Types de dépenses
- Alimentation
- Logement
- Transport
- Loisirs
- Autre

### Quartiers
- Campus
- Centre-ville
- Quartier 1
- Quartier 2
- Quartier 3
- Autre

## 📝 Notes Techniques

- **Framework** : Django 4.2+
- **Base de données** : SQLite (développement)
- **Visualisation** : Matplotlib, Pandas
- **Interface** : Bootstrap 5.3
- **Backend** : Python 3.8+

## 🎓 Contexte du Projet

Projet développé dans le cadre du cours **Analystes Statisticiens (AS3)** de l'**ISSEA** (Institut Sous-régional de Statistique et d'Economie Appliquée) - 2025.

### Objectifs pédagogiques
- Conception d'une application web en Python (Django)
- Modélisation et gestion de base de données
- Validation, nettoyage et contrôle qualité des données
- Visualisation d'informations économiques
- Analyse comparative et argumentation
- Présentation technique et fonctionnelle

## 📄 Licence

Ce projet est développé dans un contexte académique.

## 👥 Auteur

Projet réalisé dans le cadre du cours AS3 - ISSEA 2025

