# Create your models here.
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


class Depense(models.Model):
    TYPE_DEPENSE_CHOICES = [
        ('alimentation', 'Alimentation'),
        ('logement', 'Logement'),
        ('transport', 'Transport'),
        ('loisirs', 'Loisirs'),
        ('autre', 'Autre'),
    ]
    
    QUARTIER_CHOICES = [
        ('campus', 'Campus'),
        ('centre_ville', 'Centre-ville'),
        ('quartier_1', 'Quartier 1'),
        ('quartier_2', 'Quartier 2'),
        ('quartier_3', 'Quartier 3'),
        ('autre', 'Autre'),
    ]

    type_depense = models.CharField(max_length=50, choices=TYPE_DEPENSE_CHOICES, verbose_name="Type de dépense")
    # Allow free-text input for quartier (remove choices to accept arbitrary names)
    quartier = models.CharField(max_length=100, verbose_name="Quartier")
    prix = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name="Prix (FCFA)")
    lieu = models.CharField(max_length=200, verbose_name="Lieu précis")
    date = models.DateField(default=timezone.now, verbose_name="Date")
    commentaire = models.TextField(blank=True, verbose_name="Commentaire")
    photo = models.ImageField(upload_to='photos/', blank=True, null=True, verbose_name="Photo justificative")
    anomalie = models.TextField(blank=True, verbose_name="Anomalie détectée")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_modification = models.DateTimeField(auto_now=True, verbose_name="Date de modification")

    def __str__(self):
        # get_type_depense_display exists (choices remain), but quartier can be free text now
        type_disp = self.get_type_depense_display() if hasattr(self, 'get_type_depense_display') else self.type_depense
        try:
            quartier_disp = self.get_quartier_display()
        except AttributeError:
            quartier_disp = self.quartier
        return f"{type_disp} - {quartier_disp} - {self.prix} FCFA"

    def save(self, *args, **kwargs):
        """Normalize the `quartier` field on save to maintain consistent values."""
        if self.quartier:
            # Inline normalization: strip, collapse spaces, replace -/_ with spaces, title case
            import re
            s = self.quartier.strip()
            s = re.sub(r"[\-_]+", " ", s)
            s = re.sub(r"\s+", " ", s)
            self.quartier = s.title()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-date']
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"