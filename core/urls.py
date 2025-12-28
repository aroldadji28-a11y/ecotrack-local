from django.urls import path
from . import views

urlpatterns = [
    # Page d'accueil
    path('', views.accueil, name='accueil'),
    
    # Formulaire de saisie
    path('saisie/', views.saisie, name='saisie'),
    
    # Dashboard de visualisation
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Comparaisons interactives
    path('comparaison/', views.comparaison, name='comparaison'),
    
    # Anomalies
    path('anomalies/', views.anomalies, name='anomalies'),
    
    # Liste des dépenses
    path('depenses/', views.liste_depenses, name='liste_depenses'),
    # Exports
    path('export/csv/', views.export_csv, name='export_csv'),
    path('export/anomalies/csv/', views.export_anomalies_csv, name='export_anomalies_csv'),
    path('export/comparaison/csv/', views.export_comparaison_csv, name='export_comparaison_csv'),
]