import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import json
from collections import Counter
import bcrypt

st.set_page_config(page_title="Cadastre des formations TIC — Tableau interactif", layout="wide")

# ==============================================================================
# AUTHENTIFICATION
# ==============================================================================

# Initialiser session_state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'name' not in st.session_state:
    st.session_state.name = None

def check_password(username, password):
    """Vérifie le mot de passe hashé"""
    if "users" not in st.secrets or username not in st.secrets["users"]:
        return False
    
    stored_hash = st.secrets["users"][username]["password"]
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))

def login():
    """Affiche le formulaire de connexion"""
    st.title("Connexion")
    st.markdown("---")
    
    with st.form("login_form"):
        st.info("**Application protégée** - Veuillez vous connecter pour accéder au contenu")
        username = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe", type="password")
        submit = st.form_submit_button("Se connecter")
        
        if submit:
            if check_password(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.name = st.secrets["users"][username]["name"]
                st.rerun()
            else:
                st.error("Nom d'utilisateur ou mot de passe incorrect")

def logout():
    """Déconnexion"""
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.name = None
    st.rerun()

# Vérifier l'authentification
if not st.session_state.authenticated:
    login()
    st.stop()

# Afficher les infos utilisateur dans sidebar
st.sidebar.success(f'Connecté en tant que: **{st.session_state.name}**')
if st.sidebar.button("🚪 Déconnexion"):
    logout()
st.sidebar.markdown("---")

# ==============================================================================
# APPLICATION PRINCIPALE (code existant ci-dessous)
# ==============================================================================

# Configuration des provinces wallonnes avec coordonnées approximatives
PROVINCES_WALLONNES = {
    "Hainaut": {"lat": 50.4, "lon": 3.8, "color": "#1f77b4"},
    "Liège": {"lat": 50.6, "lon": 5.6, "color": "#ff7f0e"},
    "Namur": {"lat": 50.5, "lon": 4.9, "color": "#2ca02c"},
    "Luxembourg": {"lat": 50.0, "lon": 5.5, "color": "#d62728"},
    "Brabant wallon": {"lat": 50.7, "lon": 4.6, "color": "#9467bd"}
}

VILLES_PROVINCES = {
    "Liège": "Liège", "Verviers": "Liège", "Huy": "Liège",
    "Namur": "Namur", "Dinant": "Namur", "Gembloux": "Namur",
    "Charleroi": "Hainaut", "Mons": "Hainaut", "Tournai": "Hainaut", "Mouscron": "Hainaut",
    "Arlon": "Luxembourg", "Bastogne": "Luxembourg", "Virton": "Luxembourg", "Marche-en-Famenne": "Luxembourg",
    "Wavre": "Brabant wallon", "Nivelles": "Brabant wallon", "Jodoigne": "Brabant wallon"
}

@st.cache_data
def load_postal_codes() -> pd.DataFrame:
    """Charge les données des codes postaux belges"""
    try:
        # Essayer différents encodages
        for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
            try:
                postal_df = pd.read_csv('data/postal-codes-belgium.csv', sep=';', encoding=encoding)
                postal_df.columns = [c.strip() for c in postal_df.columns]
                return postal_df
            except UnicodeDecodeError:
                continue
        st.warning("Impossible de charger les codes postaux: problème d'encodage")
        return pd.DataFrame()
    except Exception as e:
        st.warning(f"Impossible de charger les codes postaux: {e}")
        return pd.DataFrame()

@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    """Charge les données CSV avec le bon séparateur et nettoie les colonnes"""
    try:
        # Essayer avec différents séparateurs
        for sep in [';', ',', '\t']:
            try:
                df = pd.read_csv(path, sep=sep, encoding='utf-8')
                if len(df.columns) > 5:  # Si on a plusieurs colonnes, c'est le bon séparateur
                    break
            except:
                continue
        
        # Nettoyage des noms de colonnes
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        
        # Extraction de la province depuis localisation_potentielle
        if 'localisation_potentielle' in df.columns:
            df['province'] = df['localisation_potentielle'].apply(extract_province)
        
        # Normalisation de la durée
        if 'duree' in df.columns:
            df['duree_h'] = df['duree'].apply(parse_duree)
        
        # Catégorisation de la durée
        if 'courte' in df.columns and 'moyenne' in df.columns and 'longue' in df.columns:
            df['categorie_duree'] = df.apply(lambda x: 
                'Courte' if x.get('courte') == 'OUI' 
                else 'Moyenne' if x.get('moyenne') == 'OUI'
                else 'Longue' if x.get('longue') == 'OUI'
                else 'Non spécifié', axis=1)
        
        return df
    except Exception as e:
        st.error(f"Erreur de chargement: {e}")
        raise

def enrich_with_geo_data(df: pd.DataFrame, postal_df: pd.DataFrame) -> pd.DataFrame:
    """Enrichit les données avec les informations géographiques des codes postaux"""
    if postal_df.empty or 'localisation_potentielle' not in df.columns:
        return df
    
    # Normaliser le nom de ville dans les formations
    df['ville_normalized'] = df['localisation_potentielle'].str.strip().str.lower()
    
    # Créer une table de lookup depuis les codes postaux
    postal_lookup = postal_df[['Municipality name (French)', 
                                'Arrondissement name (French)', 
                                'Province name (French)', 
                                '_Geo Point']].copy()
    postal_lookup.columns = ['ville', 'arrondissement', 'province_geo', 'geo_point']
    
    # Normaliser les noms de villes dans le fichier postal
    postal_lookup['ville_normalized'] = postal_lookup['ville'].str.strip().str.lower()
    
    # Prendre la première occurrence de chaque ville (avec ses coordonnées moyennes si multiples)
    postal_grouped = postal_lookup.groupby('ville_normalized').agg({
        'ville': 'first',
        'arrondissement': 'first',
        'province_geo': 'first',
        'geo_point': 'first'
    }).reset_index()
    
    # Faire le merge sur le nom de ville normalisé
    df = df.merge(postal_grouped, on='ville_normalized', how='left')
    
    # Nettoyer la colonne temporaire
    df = df.drop('ville_normalized', axis=1)
    
    # Parser les coordonnées GPS
    def parse_geo_point(geo):
        if pd.isna(geo):
            return None, None
        try:
            parts = str(geo).split(',')
            if len(parts) == 2:
                return float(parts[0].strip()), float(parts[1].strip())
        except:
            pass
        return None, None
    
    df[['latitude', 'longitude']] = df['geo_point'].apply(
        lambda x: pd.Series(parse_geo_point(x))
    )
    
    # Utiliser province_geo si province manquante ou "Non spécifié"
    if 'province' in df.columns:
        df['province'] = df.apply(
            lambda row: row['province_geo'] if (pd.isna(row['province']) or row['province'] == 'Non spécifié') and pd.notna(row['province_geo']) else row['province'],
            axis=1
        )
    else:
        df['province'] = df['province_geo']
    
    return df

def extract_province(localisation):
    """Extrait la province depuis la localisation"""
    if pd.isna(localisation) or str(localisation).strip() == "":
        return "Non spécifié"
    
    loc = str(localisation).strip()
    # Recherche directe de la province
    for ville, province in VILLES_PROVINCES.items():
        if ville.lower() in loc.lower():
            return province
    
    # Recherche du nom de province dans la localisation
    for province in PROVINCES_WALLONNES.keys():
        if province.lower() in loc.lower():
            return province
    
    return "Non spécifié"

def parse_duree(duree_str):
    """Parse la durée en heures"""
    if pd.isna(duree_str):
        return None
    
    duree = str(duree_str).lower()
    
    # Extraction du nombre
    import re
    numbers = re.findall(r'\d+', duree)
    if not numbers:
        return None
    
    nb = int(numbers[0])
    
    # Conversion en heures
    if 'année' in duree or 'an' in duree:
        return nb * 1000  # Approximation
    elif 'mois' in duree:
        return nb * 120
    elif 'semaine' in duree:
        return nb * 35
    elif 'jour' in duree or 'journée' in duree:
        return nb * 7
    elif 'heure' in duree or 'h' in duree:
        return nb
    
    return nb

# Chargement des données
st.sidebar.title("Paramètres")
uploaded = st.sidebar.file_uploader("Importer un CSV", type=["csv"], accept_multiple_files=False)
default_path = "data/formations_clean.csv"
path = uploaded if uploaded is not None else default_path

try:
    data = load_data(path)
    # Charger les codes postaux et enrichir les données
    postal_data = load_postal_codes()
    if not postal_data.empty:
        data = enrich_with_geo_data(data, postal_data)
except Exception as e:
    st.error(f"Impossible de charger le fichier: {e}")
    st.stop()

# Fonction pour trouver les colonnes
def find_col(df, names):
    for n in names:
        if n in df.columns:
            return n
    return None

# Mapping des colonnes
colmap = {
    "intitule": find_col(data, ["intitule","intitulé","titre"]),
    "organisme": find_col(data, ["type_organisme", "organisme","operateur"]),
    "denomination": find_col(data, ["denomination_sociale", "denomination_commerciale"]),
    "domaine": find_col(data, ["domaine","categorie"]),
    "public": find_col(data, ["public","cible"]),
    "modalite": find_col(data, ["modalite","modalité","format"]),
    "localisation": find_col(data, ["localisation_potentielle", "localisation","lieu"]),
    "province": "province",
    "duree": find_col(data, ["duree","durée"]),
    "duree_h": "duree_h",
    "categorie_duree": "categorie_duree",
    "qualifiante": find_col(data, ["qualifiante"]),
    "certifiante": find_col(data, ["certifiante"]),
}

# FILTRES SIDEBAR
with st.sidebar.expander("Filtres", expanded=True):
    df = data.copy()
    
    # Filtre province
    if colmap["province"]:
        provinces = sorted([p for p in df[colmap["province"]].unique() if str(p) != "Non spécifié" and pd.notna(p)])
        provinces_sel = st.multiselect("Province", options=provinces, default=[])
        if provinces_sel:
            df = df[df[colmap["province"]].isin(provinces_sel)]
    
    # Filtre organisme
    if colmap["organisme"]:
        organismes = sorted(df[colmap["organisme"]].dropna().unique().tolist())
        org_sel = st.multiselect("Type d'organisme", options=organismes, default=[])
        if org_sel:
            df = df[df[colmap["organisme"]].isin(org_sel)]
    
    # Filtre catégorie durée
    if colmap["categorie_duree"]:
        cats = sorted(df[colmap["categorie_duree"]].dropna().unique().tolist())
        cat_sel = st.multiselect("Catégorie de durée", options=cats, default=[])
        if cat_sel:
            df = df[df[colmap["categorie_duree"]].isin(cat_sel)]
    
    # Filtre qualifiante/certifiante
    col_cert_qual = st.columns(2)
    with col_cert_qual[0]:
        if colmap["qualifiante"]:
            qual = st.checkbox("Qualifiante uniquement", False)
            if qual:
                df = df[df[colmap["qualifiante"]] == "OUI"]
    
    with col_cert_qual[1]:
        if colmap["certifiante"]:
            cert = st.checkbox("Certifiante uniquement", False)
            if cert:
                df = df[df[colmap["certifiante"]] == "OUI"]
    
    # Recherche texte
    if colmap["intitule"]:
        q = st.text_input("Recherche dans l'intitulé", "")
        if q.strip():
            df = df[df[colmap["intitule"]].fillna("").str.contains(q.strip(), case=False, regex=False)]

# HEADER - MÉTRIQUES PRINCIPALES
st.title("Cadastre des Formations TIC en Wallonie")
st.markdown("---")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Formations", len(df))
with col2:
    st.metric("Organismes", df[colmap["organisme"]].nunique() if colmap["organisme"] else "-")
with col3:
    qual_count = (df[colmap["qualifiante"]] == "OUI").sum() if colmap["qualifiante"] else 0
    st.metric("Qualifiantes", qual_count)
with col4:
    cert_count = (df[colmap["certifiante"]] == "OUI").sum() if colmap["certifiante"] else 0
    st.metric("Certifiantes", cert_count)
with col5:
    st.metric("Provinces", df[colmap["province"]].nunique() if colmap["province"] else "-")

st.markdown("---")

# LAYOUT PRINCIPAL
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Carte des Provinces", "Analyses", "Graphiques Avancés", "Données", "Cards"])

# TAB 1: CARTE GÉOGRAPHIQUE
with tab1:
    st.subheader("Répartition géographique des formations")
    
    # Sélecteur de niveau géographique
    vue_geo = st.radio(
        "Niveau de détail :",
        options=["Province", "Arrondissement", "Ville"],
        horizontal=True,
        key="vue_geographique"
    )
    
    if vue_geo == "Province":
        # VUE PAR PROVINCE (code existant)
        if colmap["province"]:
            province_counts = df[colmap["province"]].value_counts().reset_index()
            province_counts.columns = ['province', 'count']
            province_counts = province_counts[province_counts['province'] != 'Non spécifié']
            
            fig_map = go.Figure()
            
            for _, row in province_counts.iterrows():
                prov = row['province']
                count = row['count']
                if prov in PROVINCES_WALLONNES:
                    coords = PROVINCES_WALLONNES[prov]
                    fig_map.add_trace(go.Scattermapbox(
                        lat=[coords['lat']],
                        lon=[coords['lon']],
                        mode='markers+text',
                        marker=dict(size=count/5 + 20, color=coords['color'], opacity=0.7),
                        text=f"{prov}",
                        textposition="top center",
                        hovertemplate=f"<b>{prov}</b><br>{count} formations<extra></extra>",
                        name=prov
                    ))
            
            fig_map.update_layout(
                mapbox=dict(
                    style="open-street-map",
                    center=dict(lat=50.5, lon=4.8),
                    zoom=7
                ),
                height=600,
                showlegend=True,
                margin={"r":0,"t":0,"l":0,"b":0}
            )
            
            st.plotly_chart(fig_map, use_container_width=True)
            
            col_map_left, col_map_right = st.columns(2)
            
            with col_map_left:
                fig_prov_bar = px.bar(
                    province_counts.sort_values('count', ascending=True),
                    x='count',
                    y='province',
                    orientation='h',
                    title="Nombre de formations par province",
                    color='province',
                    color_discrete_map={p: PROVINCES_WALLONNES[p]['color'] for p in PROVINCES_WALLONNES}
                )
                fig_prov_bar.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig_prov_bar, use_container_width=True)
            
            with col_map_right:
                fig_prov_pie = px.pie(
                    province_counts,
                    values='count',
                    names='province',
                    title="Répartition en % par province",
                    color='province',
                    color_discrete_map={p: PROVINCES_WALLONNES[p]['color'] for p in PROVINCES_WALLONNES}
                )
                fig_prov_pie.update_layout(height=400)
                st.plotly_chart(fig_prov_pie, use_container_width=True)
    
    elif vue_geo == "Arrondissement":
        # VUE PAR ARRONDISSEMENT
        if 'arrondissement' in df.columns:
            arr_data = df[df['arrondissement'].notna()].copy()
            
            if len(arr_data) > 0:
                # Agrégation par arrondissement avec coordonnées moyennes et comptage
                arr_grouped = arr_data.groupby('arrondissement').agg({
                    'latitude': 'mean',
                    'longitude': 'mean',
                    'province': 'first',
                    'localisation_potentielle': 'count'  # Comptage correct
                }).reset_index()
                arr_grouped.rename(columns={'localisation_potentielle': 'count'}, inplace=True)
                
                # Carte avec markers
                fig_arr_map = go.Figure()
                
                for _, row in arr_grouped.iterrows():
                    if pd.notna(row['latitude']) and pd.notna(row['longitude']):
                        province = row['province'] if pd.notna(row['province']) else 'Non spécifié'
                        color = PROVINCES_WALLONNES.get(province, {}).get('color', '#636EFA')
                        
                        fig_arr_map.add_trace(go.Scattermapbox(
                            lat=[row['latitude']],
                            lon=[row['longitude']],
                            mode='markers+text',
                            marker=dict(size=row['count']/3 + 15, color=color, opacity=0.7),
                            text=row['arrondissement'],
                            textposition="top center",
                            textfont=dict(size=9),
                            hovertemplate=f"<b>{row['arrondissement']}</b><br>" +
                                        f"Province: {province}<br>" +
                                        f"{row['count']} formations<extra></extra>",
                            name=row['arrondissement']
                        ))
                
                fig_arr_map.update_layout(
                    mapbox=dict(
                        style="open-street-map",
                        center=dict(lat=50.5, lon=4.8),
                        zoom=7.5
                    ),
                    height=600,
                    showlegend=False,
                    margin={"r":0,"t":0,"l":0,"b":0}
                )
                
                st.plotly_chart(fig_arr_map, use_container_width=True)
                
                # Graphiques complémentaires
                col_arr_left, col_arr_right = st.columns(2)
                
                with col_arr_left:
                    # Top 15 arrondissements
                    top_arr = arr_grouped.nlargest(15, 'count')
                    fig_arr_bar = px.bar(
                        top_arr.sort_values('count', ascending=True),
                        x='count',
                        y='arrondissement',
                        orientation='h',
                        title="Top 15 arrondissements",
                        color='province',
                        color_discrete_map={p: PROVINCES_WALLONNES[p]['color'] for p in PROVINCES_WALLONNES}
                    )
                    fig_arr_bar.update_layout(height=400)
                    st.plotly_chart(fig_arr_bar, use_container_width=True)
                
                with col_arr_right:
                    # Distribution par province dans les arrondissements
                    arr_prov = arr_data.groupby(['province', 'arrondissement']).size().reset_index(name='count')
                    fig_arr_prov = px.bar(
                        arr_prov,
                        x='province',
                        y='count',
                        color='arrondissement',
                        title="Arrondissements par province",
                        barmode='stack'
                    )
                    fig_arr_prov.update_layout(height=400, showlegend=False)
                    st.plotly_chart(fig_arr_prov, use_container_width=True)
            else:
                st.warning("Aucune donnée d'arrondissement disponible pour les formations filtrées.")
        else:
            st.warning("Les données d'arrondissement ne sont pas disponibles. Chargez le fichier des codes postaux.")
    
    else:  # vue_geo == "Ville"
        # VUE PAR VILLE
        if 'ville' in df.columns:
            ville_data = df[df['ville'].notna()].copy()
            
            if len(ville_data) > 0:
                # Agrégation par ville avec coordonnées moyennes
                ville_grouped = ville_data.groupby('ville').agg({
                    'latitude': 'mean',
                    'longitude': 'mean',
                    'province': 'first',
                    'arrondissement': 'first'
                }).reset_index()
                # Compter correctement les formations par ville
                ville_counts = ville_data.groupby('ville').size().reset_index(name='count')
                ville_grouped = ville_grouped.merge(ville_counts, on='ville')
                
                # Filtrer les 50 villes principales pour la lisibilité
                ville_grouped = ville_grouped.nlargest(50, 'count')
                
                # Carte avec markers
                fig_ville_map = go.Figure()
                
                for _, row in ville_grouped.iterrows():
                    if pd.notna(row['latitude']) and pd.notna(row['longitude']):
                        province = row['province'] if pd.notna(row['province']) else 'Non spécifié'
                        color = PROVINCES_WALLONNES.get(province, {}).get('color', '#636EFA')
                        
                        fig_ville_map.add_trace(go.Scattermapbox(
                            lat=[row['latitude']],
                            lon=[row['longitude']],
                            mode='markers',
                            marker=dict(size=row['count']/2 + 8, color=color, opacity=0.7),
                            text=row['ville'],
                            hovertemplate=f"<b>{row['ville']}</b><br>" +
                                        f"Arrondissement: {row['arrondissement']}<br>" +
                                        f"Province: {province}<br>" +
                                        f"{row['count']} formations<extra></extra>",
                            name=row['ville']
                        ))
                
                fig_ville_map.update_layout(
                    mapbox=dict(
                        style="open-street-map",
                        center=dict(lat=50.5, lon=4.8),
                        zoom=8
                    ),
                    height=600,
                    showlegend=False,
                    margin={"r":0,"t":0,"l":0,"b":0}
                )
                
                st.plotly_chart(fig_ville_map, use_container_width=True)
                
                st.info(f"📍 Affichage des 50 principales villes (sur {ville_data['ville'].nunique()} villes au total)")
                
                # Graphiques complémentaires
                col_ville_left, col_ville_right = st.columns(2)
                
                with col_ville_left:
                    # Top 20 villes
                    top_villes = ville_grouped.head(20)
                    fig_ville_bar = px.bar(
                        top_villes.sort_values('count', ascending=True),
                        x='count',
                        y='ville',
                        orientation='h',
                        title="Top 20 villes",
                        color='province',
                        color_discrete_map={p: PROVINCES_WALLONNES[p]['color'] for p in PROVINCES_WALLONNES}
                    )
                    fig_ville_bar.update_layout(height=500)
                    st.plotly_chart(fig_ville_bar, use_container_width=True)
                
                with col_ville_right:
                    # Tableau des principales villes
                    st.markdown("**Principales villes**")
                    tableau_villes = ville_grouped[['ville', 'arrondissement', 'province', 'count']].head(20)
                    tableau_villes.columns = ['Ville', 'Arrondissement', 'Province', 'Formations']
                    st.dataframe(tableau_villes, use_container_width=True, height=465)
            else:
                st.warning("Aucune donnée de ville disponible pour les formations filtrées.")
        else:
            st.warning("Les données de ville ne sont pas disponibles. Chargez le fichier des codes postaux.")

# TAB 2: ANALYSES
with tab2:
    col_left, col_right = st.columns(2)
    
    with col_left:
        # Top organismes
        if colmap["organisme"]:
            top_org = df[colmap["organisme"]].value_counts().head(15).reset_index()
            top_org.columns = ['organisme', 'count']
            fig_org = px.bar(
                top_org,
                x='count',
                y='organisme',
                orientation='h',
                title="Top 15 types d'organismes",
                color='count',
                color_continuous_scale='Blues'
            )
            fig_org.update_layout(height=500)
            st.plotly_chart(fig_org, use_container_width=True)
        
        # Catégories de durée
        if colmap["categorie_duree"]:
            cat_duree = df[colmap["categorie_duree"]].value_counts().reset_index()
            cat_duree.columns = ['categorie', 'count']
            fig_cat = px.pie(
                cat_duree,
                values='count',
                names='categorie',
                title="Répartition par catégorie de durée",
                hole=0.4
            )
            fig_cat.update_layout(height=400)
            st.plotly_chart(fig_cat, use_container_width=True)
    
    with col_right:
        # Qualifiante vs Certifiante
        if colmap["qualifiante"] and colmap["certifiante"]:
            cert_qual_data = {
                'Type': ['Qualifiantes', 'Certifiantes', 'Les deux', 'Aucune'],
                'Count': [
                    ((df[colmap["qualifiante"]] == "OUI") & (df[colmap["certifiante"]] == "NON")).sum(),
                    ((df[colmap["qualifiante"]] == "NON") & (df[colmap["certifiante"]] == "OUI")).sum(),
                    ((df[colmap["qualifiante"]] == "OUI") & (df[colmap["certifiante"]] == "OUI")).sum(),
                    ((df[colmap["qualifiante"]] == "NON") & (df[colmap["certifiante"]] == "NON")).sum()
                ]
            }
            cert_qual_df = pd.DataFrame(cert_qual_data)
            fig_cert = px.bar(
                cert_qual_df,
                x='Type',
                y='Count',
                title="Formations qualifiantes vs certifiantes",
                color='Type',
                color_discrete_sequence=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
            )
            fig_cert.update_layout(height=400)
            st.plotly_chart(fig_cert, use_container_width=True)
        
        # Distribution des durées en heures
        if colmap["duree_h"]:
            durees_clean = df[df[colmap["duree_h"]].notna() & (df[colmap["duree_h"]] > 0)]
            if len(durees_clean) > 0:
                fig_duree = px.histogram(
                    durees_clean,
                    x=colmap["duree_h"],
                    title="Distribution des durées (en heures)",
                    nbins=30,
                    color_discrete_sequence=['#636EFA']
                )
                fig_duree.update_layout(height=400)
                st.plotly_chart(fig_duree, use_container_width=True)

# TAB 3: GRAPHIQUES AVANCÉS
with tab3:
    # Sunburst: Province > Organisme > Catégorie durée
    if colmap["province"] and colmap["organisme"] and colmap["categorie_duree"]:
        st.subheader("Vue hiérarchique: Province → Organisme → Durée")
        
        sunburst_df = df[
            (df[colmap["province"]] != "Non spécifié") &
            (df[colmap["organisme"]].notna()) &
            (df[colmap["categorie_duree"]].notna())
        ][[colmap["province"], colmap["organisme"], colmap["categorie_duree"]]].copy()
        
        if len(sunburst_df) > 0:
            fig_sunburst = px.sunburst(
                sunburst_df,
                path=[colmap["province"], colmap["organisme"], colmap["categorie_duree"]],
                title="Hiérarchie Province → Type d'organisme → Catégorie de durée"
            )
            fig_sunburst.update_layout(height=600)
            st.plotly_chart(fig_sunburst, use_container_width=True)
    
    col_adv1, col_adv2 = st.columns(2)
    
    with col_adv1:
        # Treemap
        if colmap["organisme"] and colmap["categorie_duree"]:
            treemap_df = df.groupby([colmap["organisme"], colmap["categorie_duree"]]).size().reset_index(name='count')
            treemap_df = treemap_df[treemap_df['count'] > 2]  # Filtre les petites valeurs
            
            if len(treemap_df) > 0:
                fig_tree = px.treemap(
                    treemap_df,
                    path=[colmap["organisme"], colmap["categorie_duree"]],
                    values='count',
                    title="Treemap: Organisme → Catégorie de durée"
                )
                fig_tree.update_layout(height=500)
                st.plotly_chart(fig_tree, use_container_width=True)
    
    with col_adv2:
        # Scatter: Durée vs Province
        if colmap["duree_h"] and colmap["province"]:
            scatter_df = df[
                (df[colmap["duree_h"]].notna()) &
                (df[colmap["duree_h"]] > 0) &
                (df[colmap["province"]] != "Non spécifié")
            ].copy()
            
            if len(scatter_df) > 0:
                fig_scatter = px.strip(
                    scatter_df,
                    x=colmap["province"],
                    y=colmap["duree_h"],
                    title="Distribution des durées par province",
                    color=colmap["province"]
                )
                fig_scatter.update_layout(height=500)
                st.plotly_chart(fig_scatter, use_container_width=True)

# TAB 4: DONNÉES
with tab4:
    st.subheader("Tableau des données filtrées")
    
    # Sélection des colonnes à afficher
    display_cols = []
    for k in ["intitule", "organisme", "denomination", "province", "localisation", 
              "categorie_duree", "duree", "qualifiante", "certifiante", "public"]:
        c = colmap.get(k)
        if c and c in df.columns and c not in display_cols:
            display_cols.append(c)
    
    if not display_cols:
        display_cols = df.columns.tolist()
    
    # Affichage du tableau en lecture seule
    st.dataframe(df[display_cols].reset_index(drop=True), use_container_width=True, height=600)
    
    # Téléchargement CSV
    st.markdown("---")
    csv = df[display_cols].to_csv(index=False, sep=';', encoding='utf-8-sig')
    st.download_button(
        label="📥 Télécharger les données filtrées (CSV)",
        data=csv,
        file_name="formations_filtered.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    # Statistiques descriptives
    st.subheader("Statistiques descriptives")
    
    stats_col1, stats_col2, stats_col3 = st.columns(3)
    
    with stats_col1:
        st.markdown("**Générales**")
        st.write(f"Total formations: {len(df)}")
        st.write(f"Provinces: {df[colmap['province']].nunique()}")
        st.write(f"Organismes: {df[colmap['organisme']].nunique()}")
    
    with stats_col2:
        st.markdown("**Certification**")
        if colmap["qualifiante"]:
            st.write(f"Qualifiantes: {(df[colmap['qualifiante']] == 'OUI').sum()}")
        if colmap["certifiante"]:
            st.write(f"Certifiantes: {(df[colmap['certifiante']] == 'OUI').sum()}")
    
    with stats_col3:
        st.markdown("**Durées**")
        if colmap["duree_h"]:
            durees = df[df[colmap["duree_h"]].notna()][colmap["duree_h"]]
            if len(durees) > 0:
                st.write(f"Durée moyenne: {durees.mean():.0f}h")
                st.write(f"Durée médiane: {durees.median():.0f}h")

# TAB 5: CARDS
with tab5:
    st.subheader("Vue Cartes de Visite des Formations")
    
    if len(df) == 0:
        st.warning("Aucune formation à afficher avec les filtres actuels.")
    else:
        # Initialiser l'index de la carte dans session_state
        if 'card_index' not in st.session_state:
            st.session_state.card_index = 0
        
        # S'assurer que l'index est valide
        if st.session_state.card_index >= len(df):
            st.session_state.card_index = 0
        
        # Navigation
        col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])
        
        with col_nav1:
            if st.button("← Précédent", use_container_width=True, disabled=(st.session_state.card_index == 0)):
                st.session_state.card_index = max(0, st.session_state.card_index - 1)
                st.rerun()
        
        with col_nav2:
            st.markdown(f"<h4 style='text-align: center;'>Formation {st.session_state.card_index + 1} sur {len(df)}</h4>", unsafe_allow_html=True)
        
        with col_nav3:
            if st.button("Suivant →", use_container_width=True, disabled=(st.session_state.card_index >= len(df) - 1)):
                st.session_state.card_index = min(len(df) - 1, st.session_state.card_index + 1)
                st.rerun()
        
        st.markdown("---")
        
        # Récupérer la formation actuelle
        current_formation = df.iloc[st.session_state.card_index]
        
        # Afficher la carte
        st.markdown(f"""
        <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #1f77b4;'>
            <h2 style='color: #1f77b4; margin-top: 0;'>{current_formation.get(colmap['intitule'], 'N/A') if colmap['intitule'] else 'Formation'}</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("")
        
        # Informations principales en colonnes
        info_col1, info_col2 = st.columns(2)
        
        with info_col1:
            st.markdown("### Informations générales")
            
            if colmap["organisme"]:
                st.markdown(f"**Type d'organisme:** {current_formation.get(colmap['organisme'], 'Non spécifié')}")
            
            if colmap["denomination"]:
                st.markdown(f"**Dénomination:** {current_formation.get(colmap['denomination'], 'Non spécifié')}")
            
            if colmap["domaine"]:
                st.markdown(f"**Domaine:** {current_formation.get(colmap['domaine'], 'Non spécifié')}")
            
            if colmap["public"]:
                st.markdown(f"**Public cible:** {current_formation.get(colmap['public'], 'Non spécifié')}")
            
            if colmap["modalite"]:
                st.markdown(f"**Modalité:** {current_formation.get(colmap['modalite'], 'Non spécifié')}")
        
        with info_col2:
            st.markdown("### Localisation et durée")
            
            if colmap["province"]:
                province = current_formation.get(colmap['province'], 'Non spécifié')
                if province in PROVINCES_WALLONNES:
                    color = PROVINCES_WALLONNES[province]['color']
                    st.markdown(f"**Province:** <span style='color: {color}; font-weight: bold;'>{province}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"**Province:** {province}")
            
            if colmap["localisation"]:
                st.markdown(f"**Localisation:** {current_formation.get(colmap['localisation'], 'Non spécifié')}")
            
            if colmap["duree"]:
                st.markdown(f"**Durée:** {current_formation.get(colmap['duree'], 'Non spécifié')}")
            
            if colmap["categorie_duree"]:
                st.markdown(f"**Catégorie:** {current_formation.get(colmap['categorie_duree'], 'Non spécifié')}")
        
        st.markdown("---")
        
        # Certification
        cert_col1, cert_col2 = st.columns(2)
        
        with cert_col1:
            if colmap["qualifiante"]:
                is_qual = current_formation.get(colmap['qualifiante'], 'NON') == 'OUI'
                if is_qual:
                    st.success("✓ Formation Qualifiante")
                else:
                    st.info("Formation non qualifiante")
        
        with cert_col2:
            if colmap["certifiante"]:
                is_cert = current_formation.get(colmap['certifiante'], 'NON') == 'OUI'
                if is_cert:
                    st.success("✓ Formation Certifiante")
                else:
                    st.info("Formation non certifiante")
        
        # Sélection rapide par index
        st.markdown("---")
        st.markdown("### Aller à une formation spécifique")
        selected_idx = st.number_input(
            "Numéro de formation",
            min_value=1,
            max_value=len(df),
            value=st.session_state.card_index + 1,
            step=1,
            key="card_selector"
        )
        
        if st.button("Aller à cette formation"):
            st.session_state.card_index = selected_idx - 1
            st.rerun()

st.markdown("---")
st.caption("Cadastre - Beta - des formations TIC en Wallonie | Filtre par province, organisme, durée, ...")
