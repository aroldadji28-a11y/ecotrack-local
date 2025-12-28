#!/usr/bin/env python
"""
Script de vérification de la configuration des URLs
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecotrack_env.settings')
django.setup()

from django.urls import get_resolver
from django.conf import settings

print("=" * 60)
print("VÉRIFICATION DE LA CONFIGURATION DES URLs")
print("=" * 60)

# Vérifier ROOT_URLCONF
print(f"\n1. ROOT_URLCONF: {settings.ROOT_URLCONF}")

# Obtenir le resolver
resolver = get_resolver()

print("\n2. Patterns d'URLs trouvés:")
print("-" * 60)

def print_urls(urlpatterns, prefix=''):
    for pattern in urlpatterns:
        if hasattr(pattern, 'url_patterns'):
            # C'est un include
            print(f"{prefix}{pattern.pattern} -> {pattern.urlconf_name}")
            print_urls(pattern.url_patterns, prefix + '  ')
        else:
            # C'est un pattern simple
            print(f"{prefix}{pattern.pattern} -> {pattern.callback.__name__ if hasattr(pattern, 'callback') else 'N/A'}")

print_urls(resolver.url_patterns)

print("\n" + "=" * 60)
print("Vérification terminée!")
print("=" * 60)

