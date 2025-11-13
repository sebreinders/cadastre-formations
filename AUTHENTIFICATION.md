# 🔐 Guide d'authentification - Application Cadastre Formations TIC

Ce guide explique comment configurer l'authentification par login/password pour votre application.

---

## 📋 Vue d'ensemble

Votre application est maintenant protégée par une authentification. Les utilisateurs doivent se connecter avec un nom d'utilisateur et un mot de passe avant d'accéder aux données.

**Fonctionnalités:**
- ✅ Login/Password sécurisé
- ✅ Mots de passe hashés (bcrypt)
- ✅ Session persistante avec cookies
- ✅ Bouton de déconnexion
- ✅ Gestion multi-utilisateurs

---

## 🚀 Configuration initiale (Développement local)

### Étape 1: Installer les dépendances

```bash
cd /Users/sebastienreinders/cadastre
pip install -r requirements.txt
```

### Étape 2: Générer un mot de passe hashé

```bash
python generate_password.py
```

**Exemple d'interaction:**
```
============================================================
GÉNÉRATEUR DE MOTS DE PASSE HASHÉS
============================================================

Nom d'utilisateur: admin
Nom complet: Administrateur Principal
Mot de passe: VotreMotDePasseSecret123

============================================================
RÉSULTAT - Copiez dans .streamlit/secrets.toml:
============================================================

[users.admin]
name = "Administrateur Principal"
password = "$2b$12$KIX8.H9vF5z0pQ7Z..."

============================================================
```

**⚠️ Gardez cette sortie, vous en aurez besoin!**

### Étape 3: Créer le fichier de secrets

```bash
# Créer le fichier secrets.toml
touch .streamlit/secrets.toml
```

Ouvrez `.streamlit/secrets.toml` dans VSCode et ajoutez:

```toml
# Clé secrète pour les cookies (générez une chaîne aléatoire unique)
cookie_key = "ma_cle_secrete_super_unique_123456789"

# Vos utilisateurs (copiez depuis generate_password.py)
[users.admin]
name = "Administrateur Principal"
password = "$2b$12$KIX8.H9vF5z0pQ7Z..."

[users.demo]
name = "Utilisateur Demo"
password = "$2b$12$autre_hash_genere..."
```

**💡 Conseil:** Utilisez un générateur de mot de passe pour `cookie_key`

### Étape 4: Tester localement

```bash
streamlit run app_streamlit.py
```

Vous devriez voir:
1. Une page de connexion
2. Formulaire avec username/password
3. Message "Application protégée"

Connectez-vous avec vos identifiants!

✅ **Si ça fonctionne, passez à la configuration en production →**

---

## ☁️ Configuration en production (Streamlit Cloud)

### Étape 1: Préparer Git

Assurez-vous que `.streamlit/secrets.toml` est dans `.gitignore`:

```bash
# Vérifier
cat .gitignore | grep secrets.toml

# Si pas présent, ajouter
echo ".streamlit/secrets.toml" >> .gitignore
```

### Étape 2: Commiter et pusher le code

```bash
git add .
git commit -m "Ajout: authentification par login/password"
git push origin main
```

### Étape 3: Configurer les secrets sur Streamlit Cloud

1. **Aller sur https://share.streamlit.io**
2. **Sélectionner votre app** (ou la déployer si pas encore fait)
3. Cliquer sur **"⋮"** (menu) → **"Settings"**
4. Aller dans l'onglet **"Secrets"**
5. **Coller le contenu de votre `.streamlit/secrets.toml`**:

```toml
cookie_key = "ma_cle_secrete_super_unique_123456789"

[users.admin]
name = "Administrateur Principal"
password = "$2b$12$hash_genere_avec_script..."

[users.demo]
name = "Utilisateur Demo"
password = "$2b$12$autre_hash..."
```

6. Cliquer sur **"Save"**

### Étape 4: Redémarrer l'app

L'app redémarre automatiquement après la sauvegarde des secrets.

Attendez 1-2 minutes, puis testez votre URL:
```
https://votre-username-cadastre-formations-tic.streamlit.app
```

✅ **Vous devriez voir la page de connexion!**

---

## 👥 Gestion des utilisateurs

### Ajouter un nouvel utilisateur

1. **Générer le hash du mot de passe:**
```bash
python generate_password.py
```

2. **Ajouter dans `.streamlit/secrets.toml` (local):**
```toml
[users.nouveau_user]
name = "Nouveau Utilisateur"
password = "$2b$12$hash_genere..."
```

3. **Mettre à jour sur Streamlit Cloud:**
   - Aller dans Settings → Secrets
   - Ajouter la nouvelle section
   - Sauvegarder

### Supprimer un utilisateur

1. Retirer la section `[users.username]` de secrets.toml
2. Mettre à jour sur Streamlit Cloud

### Changer un mot de passe

1. Générer un nouveau hash avec `generate_password.py`
2. Remplacer l'ancien hash par le nouveau
3. Mettre à jour sur Streamlit Cloud

---

## 🔒 Sécurité - Bonnes pratiques

### ✅ À FAIRE:

- **Utilisez des mots de passe forts** (12+ caractères, mélange de caractères)
- **Changez `cookie_key`** pour une valeur unique
- **Ne partagez JAMAIS** le fichier `secrets.toml`
- **Utilisez des emails** comme usernames pour plus de clarté
- **Documentez** qui a accès et avec quel compte

### ❌ À NE PAS FAIRE:

- ❌ Commiter `secrets.toml` dans Git
- ❌ Utiliser des mots de passe simples ("admin", "123456")
- ❌ Réutiliser le même mot de passe partout
- ❌ Partager les identifiants par email non chiffré

---

## 🛠️ Personnalisation avancée

### Changer la durée de session

Dans `app_streamlit.py`, modifiez:
```python
'expiry_days': 30  # 30 jours par défaut
```

### Personnaliser le message de login

Dans `app_streamlit.py`, cherchez:
```python
st.info('**Application protégée** - Contactez l\'administrateur pour obtenir un accès')
```

### Ajouter des rôles utilisateurs

Pour différencier admin/utilisateur normal, ajoutez dans secrets.toml:
```toml
[users.admin]
name = "Admin"
password = "hash..."
role = "admin"

[users.user1]
name = "Utilisateur"
password = "hash..."
role = "user"
```

Puis dans le code:
```python
user_role = st.secrets["users"][username].get("role", "user")

if user_role == "admin":
    st.sidebar.info("🔑 Accès Administrateur")
    # Fonctionnalités admin uniquement
```

---

## 🆘 Dépannage

### Problème: "Username/password incorrect"

**Solutions:**
1. Vérifiez que le username est exact (sensible à la casse)
2. Vérifiez que le mot de passe est correct
3. Régénérez le hash avec `generate_password.py`
4. Vérifiez que secrets.toml est bien configuré

### Problème: "st.secrets has no attribute 'users'"

**Cause:** Secrets mal configurés

**Solution:**
1. Localement: vérifiez `.streamlit/secrets.toml`
2. Sur Streamlit Cloud: vérifiez Settings → Secrets
3. Format doit être exact (voir exemples ci-dessus)

### Problème: L'app ne démarre pas après ajout auth

**Cause:** Erreur d'import ou configuration

**Solution:**
```bash
# Tester localement d'abord
pip install streamlit-authenticator
streamlit run app_streamlit.py

# Vérifier les logs sur Streamlit Cloud
Settings → View logs
```

### Problème: Session expire trop vite

**Solution:** Augmenter `expiry_days` dans le code

### Problème: Impossible de se déconnecter

**Solution:** 
1. Vider les cookies du navigateur
2. Ou utiliser navigation privée
3. Vérifier que le bouton logout est bien affiché

---

## 📊 Monitoring

### Voir qui se connecte

Streamlit Cloud Analytics montre:
- Nombre de connexions
- Temps de session
- Erreurs d'authentification

**Accès:** Settings → Analytics

### Logs d'authentification

```bash
# Voir les logs en temps réel
Settings → View logs

# Rechercher les connexions
Chercher: "authentication_status"
```

---

## 🎯 Exemples de configuration

### Configuration simple (1 utilisateur)

```toml
cookie_key = "cle_unique_123"

[users.admin]
name = "Admin"
password = "$2b$12$hash..."
```

### Configuration multi-utilisateurs

```toml
cookie_key = "cle_unique_456"

[users.admin]
name = "Administrateur"
password = "$2b$12$hash1..."

[users.analyst1]
name = "Analyste 1"
password = "$2b$12$hash2..."

[users.analyst2]
name = "Analyste 2"
password = "$2b$12$hash3..."

[users.viewer]
name = "Lecture seule"
password = "$2b$12$hash4..."
```

### Configuration par email

```toml
cookie_key = "cle_unique_789"

[users."admin@company.be"]
name = "John Doe"
password = "$2b$12$hash1..."

[users."user@company.be"]
name = "Jane Smith"
password = "$2b$12$hash2..."
```

---

## 📝 Checklist de déploiement

Avant de mettre en production:

- [ ] Mots de passe générés avec `generate_password.py`
- [ ] `cookie_key` unique et sécurisé
- [ ] `.streamlit/secrets.toml` créé localement
- [ ] Testé en local avec `streamlit run app_streamlit.py`
- [ ] `.streamlit/secrets.toml` dans `.gitignore`
- [ ] Code pushé sur GitHub
- [ ] Secrets configurés sur Streamlit Cloud
- [ ] App testée en production
- [ ] Documentation des comptes utilisateurs
- [ ] Instructions partagées avec les utilisateurs

---

## 🔄 Mise à jour du code d'authentification

Si vous voulez modifier le système d'authentification:

1. **Modifier `app_streamlit.py`**
2. **Tester localement**
3. **Commit et push:**
```bash
git add app_streamlit.py
git commit -m "Update: amélioration authentification"
git push origin main
```

L'app Streamlit Cloud se met à jour automatiquement!

---

## 💬 Support

**Questions fréquentes:**

**Q: Combien d'utilisateurs peut-on avoir?**
R: Illimité! Ajoutez autant de sections `[users.username]` que nécessaire.

**Q: Peut-on avoir différents niveaux d'accès?**
R: Oui! Ajoutez un champ `role` dans secrets.toml et gérez-le dans le code.

**Q: Est-ce sécurisé?**
R: Oui! Les mots de passe sont hashés avec bcrypt (standard industriel).

**Q: Peut-on utiliser OAuth (Google, Microsoft)?**
R: Pas nativement, mais des extensions existent pour ça.

**Q: Comment gérer beaucoup d'utilisateurs?**
R: Pour 50+ utilisateurs, envisagez une base de données externe.

---

## 🎉 C'est terminé!

Votre application est maintenant protégée par authentification!

**Prochaines étapes possibles:**
- Ajouter des rôles utilisateurs
- Logger les connexions
- Implémenter "mot de passe oublié"
- Ajouter une base de données pour les users
- Mettre en place 2FA (authentification à deux facteurs)

**Besoin d'aide? Contactez le développeur!**
