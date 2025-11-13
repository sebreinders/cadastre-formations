#!/usr/bin/env python3
"""
Script pour générer des mots de passe hashés pour l'authentification Streamlit
Usage: python generate_password.py
"""

import streamlit_authenticator as stauth

print("=" * 60)
print("GÉNÉRATEUR DE MOTS DE PASSE HASHÉS")
print("=" * 60)
print()

# Demander les informations
username = input("Nom d'utilisateur: ")
name = input("Nom complet: ")
password = input("Mot de passe: ")

# Générer le hash
hashed_password = stauth.Hasher([password]).generate()[0]

print()
print("=" * 60)
print("RÉSULTAT - Copiez dans .streamlit/secrets.toml:")
print("=" * 60)
print()
print(f'[users.{username}]')
print(f'name = "{name}"')
print(f'password = "{hashed_password}"')
print()
print("=" * 60)
