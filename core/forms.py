from django import forms
from .models import Depense
from django.utils import timezone
import re


def normalize_quartier(value: str) -> str:
    """Normalize quartier: strip, collapse spaces, replace underscores/dashes with spaces, title-case."""
    if not value:
        return value
    s = value.strip()
    s = re.sub(r"[\-_]+", " ", s)  # replace - or _ with space
    s = re.sub(r"\s+", " ", s)  # collapse multiple spaces
    return s.title()


class DepenseForm(forms.ModelForm):
    class Meta:
        model = Depense
        fields = ['type_depense', 'quartier', 'prix', 'lieu', 'date', 'commentaire', 'photo']
        widgets = {
            'type_depense': forms.Select(attrs={'class': 'form-select'}),
            # Allow free text input for quartier
            'quartier': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Entrez votre quartier (ex: Centre-ville)'}),
            'prix': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'lieu': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Marché central, étalage n°5'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'commentaire': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Ajoutez des détails supplémentaires...'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
        labels = {
            'type_depense': 'Type de dépense',
            'quartier': 'Quartier',
            'prix': 'Prix (FCFA)',
            'lieu': 'Lieu précis',
            'date': 'Date',
            'commentaire': 'Commentaire',
            'photo': 'Photo justificative',
        }

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date and date > timezone.now().date():
            raise forms.ValidationError("La date ne peut pas être dans le futur.")
        return date

    def clean_prix(self):
        prix = self.cleaned_data.get('prix')
        if prix and prix <= 0:
            raise forms.ValidationError("Le prix doit être supérieur à 0.")
        return prix

    def clean_quartier(self):
        quartier = self.cleaned_data.get('quartier')
        # Normalize user input early to ensure consistent storage
        if quartier:
            return normalize_quartier(quartier)
        return quartier