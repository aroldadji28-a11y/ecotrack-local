# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import DepenseForm
from .models import Depense
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Backend non-interactif
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.ticker import FuncFormatter
from io import BytesIO
import base64
from django.db.models import Avg, Min, Max, Count, Q
from django.http import JsonResponse, HttpResponse
from collections import defaultdict

# Configuration matplotlib pour français
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['figure.facecolor'] = 'white'

# Dictionnaires de traduction
QUARTIER_LABELS = {
    'campus': 'Campus',
    'centre_ville': 'Centre-ville',
    'quartier_1': 'Quartier 1',
    'quartier_2': 'Quartier 2',
    'quartier_3': 'Quartier 3',
    'autre': 'Autre',
}

TYPE_DEPENSE_LABELS = {
    'alimentation': 'Alimentation',
    'logement': 'Logement',
    'transport': 'Transport',
    'loisirs': 'Loisirs',
    'autre': 'Autre',
}

def get_quartier_label(value):
    """Retourne le label français d'un quartier"""
    return QUARTIER_LABELS.get(value, value)

def get_type_depense_label(value):
    """Retourne le label français d'un type de dépense"""
    return TYPE_DEPENSE_LABELS.get(value, value)


def accueil(request):
    """Page d'accueil de l'application"""
    total_depenses = Depense.objects.count()
    total_quartiers = Depense.objects.values('quartier').distinct().count()
    total_types = Depense.objects.values('type_depense').distinct().count()
    
    context = {
        'title': 'EcoTrack Local - Suivi des coûts étudiants',
        'total_depenses': total_depenses,
        'total_quartiers': total_quartiers,
        'total_types': total_types,
    }
    return render(request, 'accueil.html', context)


def saisie(request):
    """Formulaire de saisie des dépenses"""
    if request.method == 'POST':
        form = DepenseForm(request.POST, request.FILES)
        if form.is_valid():
            depense = form.save()
            messages.success(request, f'Dépense enregistrée avec succès ! ({depense.type_depense} - {depense.prix} FCFA)')
            return redirect('saisie')
    else:
        form = DepenseForm()
    
    return render(request, 'saisie.html', {'form': form})


def detect_anomalies():
    """Détection automatique des anomalies (doublons et valeurs aberrantes)"""
    deps = Depense.objects.all()
    if not deps.exists():
        return
    
    df = pd.DataFrame(list(deps.values()))
    df['prix'] = df['prix'].astype(float)
    
    # Réinitialiser les anomalies existantes (sauf celles manuellement annotées)
    Depense.objects.filter(anomalie__startswith="[AUTO]").update(anomalie="")
    
    # Détection des doublons basés sur date, lieu, prix (tolérance de 2% pour le prix)
    doublons_detectes = set()
    for i, row1 in df.iterrows():
        for j, row2 in df.iterrows():
            if i < j:  # Éviter les comparaisons doubles
                # Vérifier si même date
                if pd.to_datetime(row1['date']).date() == pd.to_datetime(row2['date']).date():
                    # Vérifier si même lieu (comparaison insensible à la casse)
                    if str(row1['lieu']).strip().lower() == str(row2['lieu']).strip().lower():
                        # Vérifier si prix similaire (tolérance de 2%)
                        prix1 = float(row1['prix'])
                        prix2 = float(row2['prix'])
                        diff_relative = abs(prix1 - prix2) / max(prix1, prix2, 0.01)
                        if diff_relative < 0.02:  # 2% de tolérance
                            doublons_detectes.add(row1['id'])
                            doublons_detectes.add(row2['id'])
    
    for dep_id in doublons_detectes:
        dep = Depense.objects.get(id=dep_id)
        if not dep.anomalie or dep.anomalie.startswith("[AUTO]"):
            dep.anomalie = "[AUTO] Doublon détecté (même date, lieu et prix similaire)"
            dep.save()
    
    # Détection des valeurs aberrantes : prix > 3*écart-type + moyenne par type ET par quartier
    for typ in df['type_depense'].unique():
        sub_df = df[df['type_depense'] == typ]
        if len(sub_df) < 3:  # Besoin d'au moins 3 valeurs pour calculer l'écart-type
            continue
        
        mean = sub_df['prix'].mean()
        std = sub_df['prix'].std()
        
        if std == 0 or pd.isna(std):  # Éviter division par zéro
            continue
        
        # Seuil supérieur : moyenne + 3 écarts-types
        seuil_sup = mean + 3 * std
        # Seuil inférieur : moyenne - 3 écarts-types (pour détecter les prix anormalement bas)
        seuil_inf = max(0, mean - 3 * std)
        
        # Valeurs aberrantes supérieures
        aberrants_sup = sub_df[sub_df['prix'] > seuil_sup]
        for index, row in aberrants_sup.iterrows():
            dep = Depense.objects.get(id=row['id'])
            if not dep.anomalie or dep.anomalie.startswith("[AUTO]"):
                dep.anomalie = f"[AUTO] Valeur aberrante élevée (prix: {row['prix']:.0f} FCFA, moyenne: {mean:.0f} FCFA, écart-type: {std:.0f} FCFA)"
                dep.save()
        
        # Valeurs aberrantes inférieures (si significativement plus bas)
        if seuil_inf > 0:
            aberrants_inf = sub_df[(sub_df['prix'] < seuil_inf) & (sub_df['prix'] > 0)]
            for index, row in aberrants_inf.iterrows():
                dep = Depense.objects.get(id=row['id'])
                if not dep.anomalie or dep.anomalie.startswith("[AUTO]"):
                    dep.anomalie = f"[AUTO] Valeur aberrante basse (prix: {row['prix']:.0f} FCFA, moyenne: {mean:.0f} FCFA, écart-type: {std:.0f} FCFA)"
                    dep.save()
    
    # Détection par quartier également
    for quartier in df['quartier'].unique():
        sub_df = df[df['quartier'] == quartier]
        if len(sub_df) < 3:
            continue
        
        mean = sub_df['prix'].mean()
        std = sub_df['prix'].std()
        
        if std == 0 or pd.isna(std):
            continue
        
        seuil_sup = mean + 3 * std
        aberrants = sub_df[sub_df['prix'] > seuil_sup]
        
        for index, row in aberrants.iterrows():
            dep = Depense.objects.get(id=row['id'])
            # Ne pas écraser une anomalie déjà détectée par type
            if not dep.anomalie or (dep.anomalie.startswith("[AUTO]") and "Valeur aberrante" not in dep.anomalie):
                dep.anomalie = f"[AUTO] Valeur aberrante par quartier (prix: {row['prix']:.0f} FCFA, moyenne quartier: {mean:.0f} FCFA)"
                dep.save()


def dashboard(request):
    """Dashboard de visualisation avec statistiques et graphiques améliorés"""
    detect_anomalies()

    deps = Depense.objects.all()
    if not deps.exists():
        return render(request, 'dashboard.html', {
            'message': 'Aucune dépense enregistrée. Commencez par saisir des données.',
            'stats': None,
            'graphs': {}
        })

    df = pd.DataFrame(list(deps.values()))
    # Robustness: ensure date and prix exist and are numeric
    df['date'] = pd.to_datetime(df['date'])
    df['prix'] = pd.to_numeric(df['prix'], errors='coerce')
    df = df.dropna(subset=['date', 'prix'])

    # Formatter pour axes (espaces pour milliers)
    thousands_formatter = FuncFormatter(lambda x, pos: f"{int(x):,}".replace(',', ' '))

    # Statistiques par quartier (moyenne, min, max, médiane, nombre)
    stats_quartier = []
    for quartier in sorted(df['quartier'].dropna().unique()):
        sub_df = df[df['quartier'] == quartier]
        mediane = sub_df['prix'].median()
        mediane = float(mediane) if not pd.isna(mediane) else 0.0
        stats_quartier.append({
            'quartier': quartier,
            'quartier_label': get_quartier_label(quartier),
            'moyenne': float(sub_df['prix'].mean()) if len(sub_df) > 0 else 0.0,
            'min': float(sub_df['prix'].min()) if len(sub_df) > 0 else 0.0,
            'max': float(sub_df['prix'].max()) if len(sub_df) > 0 else 0.0,
            'mediane': mediane,
            'nombre': int(len(sub_df)),
            'ecart_type': float(sub_df['prix'].std()) if len(sub_df) > 1 else 0.0,
        })

    # Statistiques par type de dépense
    stats_type = []
    for typ in sorted(df['type_depense'].dropna().unique()):
        sub_df = df[df['type_depense'] == typ]
        mediane = sub_df['prix'].median()
        mediane = float(mediane) if not pd.isna(mediane) else 0.0
        stats_type.append({
            'type': typ,
            'type_label': get_type_depense_label(typ),
            'moyenne': float(sub_df['prix'].mean()) if len(sub_df) > 0 else 0.0,
            'min': float(sub_df['prix'].min()) if len(sub_df) > 0 else 0.0,
            'max': float(sub_df['prix'].max()) if len(sub_df) > 0 else 0.0,
            'mediane': mediane,
            'nombre': int(len(sub_df)),
        })

    graphs = {}

    # 1. Série temporelle des prix moyens (avec rolling mean et médiane globale)
    time_series = df.groupby(df['date'].dt.date)['prix'].mean().reset_index()
    time_series['date'] = pd.to_datetime(time_series['date'])
    if len(time_series) > 1:
        time_series['rolling7'] = time_series['prix'].rolling(window=min(7, len(time_series)), center=True).mean()

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(time_series['date'], time_series['prix'], marker='o', linewidth=2.5, markersize=6, color='#1f77b4', label='Prix moyen (jour)')
    if 'rolling7' in time_series:
        ax.plot(time_series['date'], time_series['rolling7'], linewidth=2, color='#ff7f0e', label='Moyenne mobile (7j)')
    mediane_globale = float(df['prix'].median()) if not pd.isna(df['prix'].median()) else 0.0
    ax.axhline(mediane_globale, color='#7b3294', linestyle='--', linewidth=1.5, label=f'Médiane globale {mediane_globale:.0f} FCFA')

    ax.set_title('Évolution des prix moyens dans le temps', fontsize=18, fontweight='bold', pad=20)
    ax.set_xlabel('Date', fontsize=12, fontweight='bold')
    ax.set_ylabel('Prix moyen (FCFA)', fontsize=12, fontweight='bold')
    ax.yaxis.set_major_formatter(thousands_formatter)
    ax.grid(True, alpha=0.25, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=10)
    ax.tick_params(axis='both', which='major', labelsize=10)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=140, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    graphs['serie_temporelle'] = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    # 2. Graphique par quartier (moyennes + médianes annotées)
    quartier_stats = df.groupby('quartier')['prix'].agg(['mean', 'median', 'count']).reset_index()
    quartier_stats = quartier_stats.sort_values('mean', ascending=False).reset_index(drop=True)
    quartier_stats['quartier_label'] = quartier_stats['quartier'].apply(get_quartier_label)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    # Use main brand color for bars; keep viridis for boxplots later
    main_color = '#1f77b4'

    bars1 = ax1.bar(range(len(quartier_stats)), quartier_stats['mean'], color=main_color, alpha=0.95, edgecolor='white', linewidth=1.2)
    ax1.set_xticks(range(len(quartier_stats)))
    ax1.set_xticklabels(quartier_stats['quartier_label'], rotation=45, ha='right')
    ax1.set_title('Prix moyens par quartier', fontweight='bold', fontsize=14, pad=15)
    ax1.set_ylabel('Prix moyen (FCFA)', fontweight='bold', fontsize=12)
    ax1.yaxis.set_major_formatter(thousands_formatter)
    ax1.grid(True, alpha=0.2, axis='y', linestyle='--')
    ax1.tick_params(axis='both', which='major', labelsize=10)
    for bar, val in zip(bars1, quartier_stats['mean']):
        ax1.text(bar.get_x() + bar.get_width()/2., val, f'{val:.0f}', ha='center', va='bottom', fontsize=10)

    # Medians panel using same brand color for consistency
    bars2 = ax2.bar(range(len(quartier_stats)), quartier_stats['median'], color=main_color, alpha=0.95, edgecolor='white', linewidth=1.2)
    ax2.set_xticks(range(len(quartier_stats)))
    ax2.set_xticklabels(quartier_stats['quartier_label'], rotation=45, ha='right')
    ax2.set_title('Prix médians par quartier', fontweight='bold', fontsize=14, pad=15)
    ax2.set_ylabel('Prix médian (FCFA)', fontweight='bold', fontsize=12)
    ax2.yaxis.set_major_formatter(thousands_formatter)
    ax2.grid(True, alpha=0.2, axis='y', linestyle='--')
    ax2.tick_params(axis='both', which='major', labelsize=10)
    for bar, val in zip(bars2, quartier_stats['median']):
        ax2.text(bar.get_x() + bar.get_width()/2., val, f'{val:.0f}', ha='center', va='bottom', fontsize=10)

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=140, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    graphs['par_quartier'] = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    # 3. Graphique par type de dépense
    type_stats = df.groupby('type_depense')['prix'].agg(['mean', 'median']).sort_values('mean', ascending=False)
    type_labels = [get_type_depense_label(t) for t in type_stats.index]

    fig, ax = plt.subplots(figsize=(12, 7))
    # Use brand color for type bars as well
    main_color = '#1f77b4'
    colors = plt.cm.Set3(np.linspace(0, 1, len(type_stats)))
    bars = ax.bar(range(len(type_stats)), type_stats['mean'].values, color=main_color, alpha=0.95, edgecolor='white', linewidth=1.2)
    ax.set_xticks(range(len(type_stats)))
    ax.set_xticklabels(type_labels, rotation=45, ha='right')
    ax.set_title('Prix moyens par type de dépense', fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Type de dépense', fontsize=12, fontweight='bold')
    ax.set_ylabel('Prix moyen (FCFA)', fontsize=12, fontweight='bold')
    ax.yaxis.set_major_formatter(thousands_formatter)
    ax.grid(True, alpha=0.2, axis='y', linestyle='--')
    ax.tick_params(axis='both', which='major', labelsize=10)
    for bar, val in zip(bars, type_stats['mean'].values):
        ax.text(bar.get_x() + bar.get_width()/2., val, f'{val:.0f}', ha='center', va='bottom', fontsize=10)

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=140, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    graphs['par_type'] = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    # 4. Box plot par quartier (avec médiane annotée)
    quartiers_list = df['quartier'].dropna().unique()
    quartiers_labels = [get_quartier_label(q) for q in quartiers_list]
    data_for_box = [df[df['quartier'] == q]['prix'].values for q in quartiers_list]

    fig, ax = plt.subplots(figsize=(14, 7))
    bp = ax.boxplot(data_for_box, labels=quartiers_labels, patch_artist=True, showmeans=True, meanline=True)

    # Color and style
    colors = plt.cm.viridis(np.linspace(0, 1, len(bp['boxes'])))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)
    # Annotate medians
    medians = [np.median(d) if len(d) else 0 for d in data_for_box]
    for i, m in enumerate(medians):
        ax.text(i+1, m, f'{m:.0f}', ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_title('Distribution des prix par quartier (Box Plot)', fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Quartier', fontsize=12, fontweight='bold')
    ax.set_ylabel('Prix (FCFA)', fontsize=12, fontweight='bold')
    ax.yaxis.set_major_formatter(thousands_formatter)
    ax.grid(True, alpha=0.2, axis='y', linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=140, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    graphs['boxplot'] = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    # Statistiques globales
    stats_globales = {
        'total_depenses': len(df),
        'prix_moyen_global': float(df['prix'].mean()) if len(df) > 0 else 0.0,
        'prix_median_global': float(df['prix'].median()) if len(df) > 0 else 0.0,
        'prix_min_global': float(df['prix'].min()) if len(df) > 0 else 0.0,
        'prix_max_global': float(df['prix'].max()) if len(df) > 0 else 0.0,
        'nombre_quartiers': int(df['quartier'].nunique()),
        'nombre_types': int(df['type_depense'].nunique()),
        'anomalies': Depense.objects.exclude(anomalie='').count(),
    }

    return render(request, 'dashboard.html', {
        'stats_quartier': stats_quartier,
        'stats_type': stats_type,
        'stats_globales': stats_globales,
        'graphs': graphs,
    })


def comparaison(request):
    """Page de comparaison interactive"""
    quartiers = Depense.objects.values_list('quartier', flat=True).distinct()
    types_depense = Depense.objects.values_list('type_depense', flat=True).distinct()
    
    # Ensure quartiers are presented sorted and non-empty
    quartiers = [q for q in sorted(quartiers) if q]
    
    context = {
        'quartiers': quartiers,
        'types_depense': types_depense,
    }
    
    # Comparaison Quartier vs Quartier
    if request.GET.get('q1') and request.GET.get('q2'):
        q1 = request.GET['q1']
        q2 = request.GET['q2']
        # Normalize query input to match stored normalized values
        def _norm(v):
            if not v:
                return v
            import re
            v = v.strip()
            v = re.sub(r"[\-_]+", " ", v)
            v = re.sub(r"\s+", " ", v)
            return v.title()
        q1_norm = _norm(q1)
        q2_norm = _norm(q2)
        
        deps_q1 = Depense.objects.filter(quartier=q1_norm)
        deps_q2 = Depense.objects.filter(quartier=q2_norm)
        
        if deps_q1.exists() and deps_q2.exists():
            df_q1 = pd.DataFrame(list(deps_q1.values()))
            df_q2 = pd.DataFrame(list(deps_q2.values()))
            # Ensure price columns are numeric floats for plotting
            df_q1['prix'] = df_q1['prix'].astype(float)
            df_q2['prix'] = df_q2['prix'].astype(float)
            stats_q1 = {
                'quartier': q1,
                'quartier_label': get_quartier_label(q1),
                'moyenne': df_q1['prix'].mean(),
                'mediane': df_q1['prix'].median(),
                'min': df_q1['prix'].min(),
                'max': df_q1['prix'].max(),
                'nombre': len(df_q1),
                'ecart_type': df_q1['prix'].std() if len(df_q1) > 1 else 0,
            }
            
            stats_q2 = {
                'quartier': q2,
                'quartier_label': get_quartier_label(q2),
                'moyenne': df_q2['prix'].mean(),
                'mediane': df_q2['prix'].median(),
                'min': df_q2['prix'].min(),
                'max': df_q2['prix'].max(),
                'nombre': len(df_q2),
                'ecart_type': df_q2['prix'].std() if len(df_q2) > 1 else 0,
            }
            
            # Graphique de comparaison
            fig, axes = plt.subplots(1, 2, figsize=(16, 7))
            
            # Graphique en barres
            categories = ['Moyenne', 'Médiane', 'Min', 'Max']
            valeurs_q1 = [stats_q1['moyenne'], stats_q1['mediane'], stats_q1['min'], stats_q1['max']]
            valeurs_q2 = [stats_q2['moyenne'], stats_q2['mediane'], stats_q2['min'], stats_q2['max']]
            
            x = np.arange(len(categories))
            width = 0.35
            
            q1_label = get_quartier_label(q1)
            q2_label = get_quartier_label(q2)
            
            bars1 = axes[0].bar(x - width/2, valeurs_q1, width, label=q1_label, 
                                alpha=0.8, color='#4facfe', edgecolor='white', linewidth=2)
            bars2 = axes[0].bar(x + width/2, valeurs_q2, width, label=q2_label, 
                                alpha=0.8, color='#f5576c', edgecolor='white', linewidth=2)
            
            # Ajouter les valeurs sur les barres
            for bars in [bars1, bars2]:
                for bar in bars:
                    height = bar.get_height()
                    axes[0].text(bar.get_x() + bar.get_width()/2., height,
                                f'{height:.0f}',
                                ha='center', va='bottom', fontsize=9, fontweight='bold')
            
            axes[0].set_xlabel('Statistiques', fontsize=12, fontweight='bold')
            axes[0].set_ylabel('Prix (FCFA)', fontsize=12, fontweight='bold')
            axes[0].set_title('Comparaison Quartier vs Quartier', fontweight='bold', fontsize=14, pad=15)
            axes[0].set_xticks(x)
            axes[0].set_xticklabels(categories, fontsize=11)
            axes[0].legend(fontsize=11, loc='upper left')
            axes[0].grid(True, alpha=0.3, axis='y', linestyle='--')
            axes[0].spines['top'].set_visible(False)
            axes[0].spines['right'].set_visible(False)
            
            # Box plot comparatif
            data_for_box = [df_q1['prix'].values, df_q2['prix'].values]
            bp = axes[1].boxplot(data_for_box, labels=[q1_label, q2_label], 
                                patch_artist=True, showmeans=True, meanline=True)
            
            # Colorier les box plots
            colors_box = ['#4facfe', '#f5576c']
            for patch, color in zip(bp['boxes'], colors_box):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)
            
            axes[1].set_ylabel('Prix (FCFA)', fontsize=12, fontweight='bold')
            axes[1].set_title('Distribution des prix', fontweight='bold', fontsize=14, pad=15)
            axes[1].grid(True, alpha=0.3, axis='y', linestyle='--')
            axes[1].spines['top'].set_visible(False)
            axes[1].spines['right'].set_visible(False)
            
            plt.tight_layout()
            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
            buf.seek(0)
            graph_comparaison = base64.b64encode(buf.read()).decode('utf-8')
            plt.close()
            
            # Calcul de la différence
            diff_moyenne = abs(stats_q1['moyenne'] - stats_q2['moyenne'])
            plus_cher = q1 if stats_q1['moyenne'] > stats_q2['moyenne'] else q2
            
            context.update({
                'mode': 'quartier_vs_quartier',
                'stats_q1': stats_q1,
                'stats_q2': stats_q2,
                'graph_comparaison': graph_comparaison,
                'diff_moyenne': diff_moyenne,
                'plus_cher': plus_cher,
            })
    
    # Comparaison Quartier vs Ville (moyenne globale)
    elif request.GET.get('mode') == 'quartier_ville' and request.GET.get('quartier'):
        quartier = request.GET['quartier']
        # Normalize quartier input
        import re
        quartier_norm = quartier.strip()
        quartier_norm = re.sub(r"[\-_]+", " ", quartier_norm)
        quartier_norm = re.sub(r"\s+", " ", quartier_norm).title()
        deps_quartier = Depense.objects.filter(quartier=quartier_norm)
        deps_ville = Depense.objects.all()
        
        if deps_quartier.exists() and deps_ville.exists():
            df_quartier = pd.DataFrame(list(deps_quartier.values()))
            df_ville = pd.DataFrame(list(deps_ville.values()))
            
            stats_quartier = {
                'quartier': quartier,
                'quartier_label': get_quartier_label(quartier),
                'moyenne': df_quartier['prix'].mean(),
                'mediane': df_quartier['prix'].median(),
                'min': df_quartier['prix'].min(),
                'max': df_quartier['prix'].max(),
                'nombre': len(df_quartier),
            }
            
            stats_ville = {
                'moyenne': df_ville['prix'].mean(),
                'mediane': df_ville['prix'].median(),
                'min': df_ville['prix'].min(),
                'max': df_ville['prix'].max(),
                'nombre': len(df_ville),
            }
            
            # Graphique
            quartier_label = get_quartier_label(quartier)
            fig, ax = plt.subplots(figsize=(12, 7))
            categories = ['Moyenne', 'Médiane', 'Min', 'Max']
            valeurs_quartier = [stats_quartier['moyenne'], stats_quartier['mediane'], 
                               stats_quartier['min'], stats_quartier['max']]
            valeurs_ville = [stats_ville['moyenne'], stats_ville['mediane'], 
                            stats_ville['min'], stats_ville['max']]
            
            x = np.arange(len(categories))
            width = 0.35
            
            bars1 = ax.bar(x - width/2, valeurs_quartier, width, label=quartier_label, 
                          alpha=0.8, color='#4facfe', edgecolor='white', linewidth=2)
            bars2 = ax.bar(x + width/2, valeurs_ville, width, label='Ville (moyenne)', 
                          alpha=0.8, color='#f5576c', edgecolor='white', linewidth=2)
            
            # Ajouter les valeurs sur les barres
            for bars in [bars1, bars2]:
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                            f'{height:.0f}',
                            ha='center', va='bottom', fontsize=10, fontweight='bold')
            
            ax.set_xlabel('Statistiques', fontsize=12, fontweight='bold')
            ax.set_ylabel('Prix (FCFA)', fontsize=12, fontweight='bold')
            ax.set_title(f'Comparaison {quartier_label} vs Ville', fontweight='bold', fontsize=16, pad=20)
            ax.set_xticks(x)
            ax.set_xticklabels(categories, fontsize=11)
            ax.legend(fontsize=12, loc='upper left')
            ax.grid(True, alpha=0.3, axis='y', linestyle='--')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            plt.tight_layout()
            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
            buf.seek(0)
            graph_comparaison = base64.b64encode(buf.read()).decode('utf-8')
            plt.close()
            
            context.update({
                'mode': 'quartier_vs_ville',
                'stats_quartier': stats_quartier,
                'stats_ville': stats_ville,
                'graph_comparaison': graph_comparaison,
            })
    
    # Comparaison Campus vs Environnement immédiat
    elif request.GET.get('mode') == 'campus_env':
        # Use optional campus param or default to 'Campus'
        campus_param = request.GET.get('campus')
        if campus_param:
            campus_norm = _normalize_input(campus_param)
        else:
            campus_norm = _normalize_input('campus')
        deps_campus = Depense.objects.filter(quartier=campus_norm)
        deps_env = Depense.objects.exclude(quartier=campus_norm)

        if deps_campus.exists() and deps_env.exists():
            df_campus = pd.DataFrame(list(deps_campus.values()))
            df_env = pd.DataFrame(list(deps_env.values()))
            # Convert prix to float for numeric operations
            df_campus['prix'] = df_campus['prix'].astype(float)
            df_env['prix'] = df_env['prix'].astype(float)

            stats_campus = {
                'moyenne': df_campus['prix'].mean(),
                'mediane': df_campus['prix'].median(),
                'min': df_campus['prix'].min(),
                'max': df_campus['prix'].max(),
                'nombre': len(df_campus),
            }

            stats_env = {
                'moyenne': df_env['prix'].mean(),
                'mediane': df_env['prix'].median(),
                'min': df_env['prix'].min(),
                'max': df_env['prix'].max(),
                'nombre': len(df_env),
            }
            
            # Graphique
            fig, ax = plt.subplots(figsize=(12, 7))
            categories = ['Moyenne', 'Médiane', 'Min', 'Max']
            valeurs_campus = [stats_campus['moyenne'], stats_campus['mediane'], 
                             stats_campus['min'], stats_campus['max']]
            valeurs_env = [stats_env['moyenne'], stats_env['mediane'], 
                          stats_env['min'], stats_env['max']]
            
            x = np.arange(len(categories))
            width = 0.35
            
            bars1 = ax.bar(x - width/2, valeurs_campus, width, label='Campus', 
                          alpha=0.8, color='#f39c12', edgecolor='white', linewidth=2)
            bars2 = ax.bar(x + width/2, valeurs_env, width, label='Environnement immédiat', 
                          alpha=0.8, color='#6c757d', edgecolor='white', linewidth=2)
            
            # Ajouter les valeurs sur les barres
            for bars in [bars1, bars2]:
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                            f'{height:.0f}',
                            ha='center', va='bottom', fontsize=10, fontweight='bold')
            
            ax.set_xlabel('Statistiques', fontsize=12, fontweight='bold')
            ax.set_ylabel('Prix (FCFA)', fontsize=12, fontweight='bold')
            ax.set_title('Comparaison Campus vs Environnement immédiat', 
                        fontweight='bold', fontsize=16, pad=20)
            ax.set_xticks(x)
            ax.set_xticklabels(categories, fontsize=11)
            ax.legend(fontsize=12, loc='upper left')
            ax.grid(True, alpha=0.3, axis='y', linestyle='--')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            plt.tight_layout()
            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
            buf.seek(0)
            graph_comparaison = base64.b64encode(buf.read()).decode('utf-8')
            plt.close()
            
            context.update({
                'mode': 'campus_vs_env',
                'stats_campus': stats_campus,
                'stats_env': stats_env,
                'graph_comparaison': graph_comparaison,
            })
    
    return render(request, 'comparaison.html', context)


def anomalies(request):
    """Page de visualisation des anomalies détectées"""
    # Apply optional filters to anomalies view as well
    anomalies_list = _apply_filters(Depense.objects.exclude(anomalie='').order_by('-date_creation'), request.GET)

    # Statistiques sur les anomalies
    total_anomalies = anomalies_list.count()
    auto_anomalies = anomalies_list.filter(anomalie__startswith='[AUTO]').count()
    manuelles_anomalies = total_anomalies - auto_anomalies

    # Anomalies par type
    anomalies_par_type = {}
    for dep in anomalies_list:
        if dep.anomalie.startswith('[AUTO]'):
            if 'Doublon' in dep.anomalie:
                type_anomalie = 'Doublon'
            elif 'Valeur aberrante' in dep.anomalie:
                type_anomalie = 'Valeur aberrante'
            else:
                type_anomalie = 'Autre'
        else:
            type_anomalie = 'Manuelle'

        anomalies_par_type[type_anomalie] = anomalies_par_type.get(type_anomalie, 0) + 1

    context = {
        'anomalies': anomalies_list,
        'total_anomalies': total_anomalies,
        'auto_anomalies': auto_anomalies,
        'manuelles_anomalies': manuelles_anomalies,
        'anomalies_par_type': anomalies_par_type,
    }

    return render(request, 'anomalies.html', context)


def _normalize_input(val: str) -> str:
    if not val:
        return val
    import re
    v = val.strip()
    v = re.sub(r"[\-_]+", " ", v)
    v = re.sub(r"\s+", " ", v)
    return v.title()


def _apply_filters(queryset, params):
    quartier_filter = params.get('quartier', '')
    type_filter = params.get('type', '')
    anomalie_filter = params.get('anomalie', '')
    month = params.get('month', '')  # expected YYYY-MM
    prix_min = params.get('prix_min', '')
    prix_max = params.get('prix_max', '')

    if quartier_filter:
        quartier_filter = _normalize_input(quartier_filter)
        queryset = queryset.filter(quartier=quartier_filter)
    if type_filter:
        queryset = queryset.filter(type_depense=type_filter)
    if anomalie_filter == 'oui':
        queryset = queryset.exclude(anomalie='')
    elif anomalie_filter == 'non':
        queryset = queryset.filter(anomalie='')
    if month:
        # month in format YYYY-MM
        try:
            year, mon = month.split('-')
            queryset = queryset.filter(date__year=int(year), date__month=int(mon))
        except Exception:
            pass
    if prix_min:
        try:
            pm = float(prix_min)
            queryset = queryset.filter(prix__gte=pm)
        except Exception:
            pass
    if prix_max:
        try:
            px = float(prix_max)
            queryset = queryset.filter(prix__lte=px)
        except Exception:
            pass
    return queryset


def liste_depenses(request):
    """Page de liste des dépenses avec filtres"""
    depenses = Depense.objects.all().order_by('-date')

    # Apply filters using helper
    depenses = _apply_filters(depenses, request.GET)

    # Statistiques rapides
    total = depenses.count()
    total_prix = sum(d.prix for d in depenses)
    prix_moyen = total_prix / total if total > 0 else 0

    # Quartiers and types for filters (sorted)
    quartiers = sorted(list(Depense.objects.values_list('quartier', flat=True).distinct()))
    types = Depense.objects.values_list('type_depense', flat=True).distinct()

    context = {
        'depenses': depenses,
        'total': total,
        'total_prix': total_prix,
        'prix_moyen': prix_moyen,
        'quartiers': quartiers,
        'types': types,
        'quartier_filter': request.GET.get('quartier', ''),
        'type_filter': request.GET.get('type', ''),
        'anomalie_filter': request.GET.get('anomalie', ''),
        'month_filter': request.GET.get('month', ''),
        'prix_min': request.GET.get('prix_min', ''),
        'prix_max': request.GET.get('prix_max', ''),
    }

    return render(request, 'liste_depenses.html', context)


def export_csv(request):
    """Export filtered dépenses as CSV"""
    qs = _apply_filters(Depense.objects.all().order_by('-date'), request.GET)
    import csv
    from django.utils import timezone
    filename = f"depenses_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(['date', 'type', 'quartier', 'lieu', 'prix', 'commentaire', 'anomalie'])
    for d in qs:
        writer.writerow([
            d.date.strftime('%Y-%m-%d'),
            d.get_type_depense_display(),
            d.quartier,
            d.lieu,
            float(d.prix),
            d.commentaire or '',
            d.anomalie or '',
        ])
    return response


def export_anomalies_csv(request):
    """Export filtered anomalies as CSV"""
    qs = _apply_filters(Depense.objects.exclude(anomalie='').order_by('-date_creation'), request.GET)
    import csv
    from django.utils import timezone
    filename = f"anomalies_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(['date', 'type', 'quartier', 'lieu', 'prix', 'anomalie', 'commentaire'])
    for d in qs:
        writer.writerow([
            d.date.strftime('%Y-%m-%d'),
            d.get_type_depense_display(),
            d.quartier,
            d.lieu,
            float(d.prix),
            d.anomalie or '',
            d.commentaire or '',
        ])
    return response


def export_comparaison_csv(request):
    """Export the records used in a comparison as CSV with a 'groupe' column"""
    import csv
    from django.utils import timezone
    mode = request.GET.get('mode')
    writer_rows = []

    if mode == 'quartier_ville':
        quartier = _normalize_input(request.GET.get('quartier', ''))
        qs_quartier = Depense.objects.filter(quartier=quartier)
        qs_ville = Depense.objects.all()
        for d in qs_quartier:
            writer_rows.append(('quartier', d))
        for d in qs_ville:
            writer_rows.append(('ville', d))
    elif mode == 'campus_env':
        # accept explicit campus param or default to 'Campus'
        campus_param = request.GET.get('campus')
        if campus_param:
            campus = _normalize_input(campus_param)
        else:
            campus = _normalize_input('campus')
        qs_campus = Depense.objects.filter(quartier=campus)
        qs_env = Depense.objects.exclude(quartier=campus)
        for d in qs_campus:
            writer_rows.append(('campus', d))
        for d in qs_env:
            writer_rows.append(('environnement', d))
    else:
        # default: quartier_vs_quartier
        q1 = _normalize_input(request.GET.get('q1', ''))
        q2 = _normalize_input(request.GET.get('q2', ''))
        qs = Depense.objects.filter(quartier__in=[q1, q2])
        for d in qs:
            grp = 'q1' if d.quartier == q1 else 'q2'
            writer_rows.append((grp, d))

    filename = f"comparaison_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(['groupe', 'date', 'type', 'quartier', 'lieu', 'prix', 'commentaire', 'anomalie'])
    for grp, d in writer_rows:
        writer.writerow([
            grp,
            d.date.strftime('%Y-%m-%d'),
            d.get_type_depense_display(),
            d.quartier,
            d.lieu,
            float(d.prix),
            d.commentaire or '',
            d.anomalie or '',
        ])
    return response
