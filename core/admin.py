from django.contrib import admin
from .models import Depense


@admin.register(Depense)
class DepenseAdmin(admin.ModelAdmin):
    list_display = ('type_depense', 'quartier', 'prix', 'lieu', 'date', 'anomalie')
    list_filter = ('type_depense', 'quartier', 'date')
    search_fields = ('lieu', 'commentaire', 'quartier')
    readonly_fields = ('date_creation', 'date_modification')
    fieldsets = (
        ('Informations principales', {
            'fields': ('type_depense', 'quartier', 'prix', 'lieu', 'date')
        }),
        ('Détails supplémentaires', {
            'fields': ('commentaire', 'photo')
        }),
        ('Qualité des données', {
            'fields': ('anomalie',)
        }),
        ('Métadonnées', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
