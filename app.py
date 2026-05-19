"""
Observatoire du vélo d'occasion — France
Outil de suivi et d'estimation des ventes de vélos d'occasion

Coordonné par France Vélo
Sources : UESC / Observatoire du Cycle · Ecologic / ADEME (API open data REP)

Lancer avec : streamlit run observatoire_velo_occasion.py
"""

import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─── Configuration de la page ────────────────────────────────────────────────

st.set_page_config(
    page_title="Observatoire vélo d'occasion",
    page_icon="🚲",
    layout="wide",
)

# ─── Constantes ──────────────────────────────────────────────────────────────

API_ADEME_URL = (
    "https://data.ademe.fr/data-fair/api/v1/datasets/"
    "6wbue0xxoy825spjgrht0ao7/lines"
)

# URLs sources
URL_UESC             = "https://www.unionsportcycle.com/observatoire-du-cycle"
URL_ADEME_API        = "https://data.ademe.fr/datasets/rep-tonnages-de-dechets-traites-des-filieres-rep/api-doc"
URL_ADEME_TABLEAU    = "https://filieres-rep.ademe.fr/filieres-REP/filiere-ASL/tableau-de-bord"
URL_ADEME_BILAN      = "https://librairie.ademe.fr/"
URL_HEUREUX_CYCLAGE  = "https://www.heureux-cyclage.org"
URL_TROCVELO         = "https://www.trocvelo.com"
URL_UPWAY            = "https://www.upway.fr"
URL_ECOLOGIC         = "https://www.ecologic-france.com"
URL_6T               = "https://www.6-t.co"
URL_FRANCE_VELO      = "https://www.francevelo.fr"

# Libellés lisibles pour les codes de traitement REP
LABELS_TRT = {
    "RECY_METAL":  "Recyclage métal",
    "RECY_ORG":    "Recyclage organique",
    "RECY_INORG":  "Recyclage inorganique",
    "VALO_ENER":   "Valorisation énergétique",
    "ELIM_CET":    "Élimination (CET)",
    "ELIM_INC":    "Élimination (incinération)",
    "ELIM_INCI":   "Élimination (incinération)",
    "REEMPLOI":    "Réemploi",
    "PREPA_REUT":  "Préparation réutilisation",
    "TRI":         "Tri",
}

COULEURS_TRT = {
    "Recyclage métal":            "#185FA5",
    "Recyclage organique":        "#0F6E56",
    "Recyclage inorganique":      "#9FE1CB",
    "Valorisation énergétique":   "#BA7517",
    "Élimination (CET)":          "#993C1D",
    "Élimination (incinération)": "#D85A30",
    "Réemploi":                   "#3B6D11",
    "Préparation réutilisation":  "#639922",
    "Tri":                        "#888780",
}

# Données historiques — mise à jour manuelle chaque année
# Sources : Observatoire du Cycle UESC · estimations France Vélo / 6T
DATA_HISTORIQUE = pd.DataFrame({
    "annee":              [2019, 2020, 2021, 2022, 2023, 2024, 2025],
    "ventes_pro_k":       [  90,  100,  120,  135,  145,  158,  200],
    "estimation_c2c_k":   [ 280,  290,  320,  340,  320,  310,  330],
    "ventes_neuf_M":      [ 2.7,  2.6,  2.5,  2.3,  2.1, 1.95, 1.83],
    "reparations_atel_M": [ 4.5,  4.8,  5.2,  5.5,  5.7,  5.9,  6.3],
})


# ─── Fonctions API ADEME ─────────────────────────────────────────────────────

@st.cache_data(ttl=86_400, show_spinner=False)
def fetch_rep_cycles() -> pd.DataFrame:
    """
    Récupère toutes les lignes REP ASL Catégorie 1 (Cycles et EDP non motorisés)
    depuis l'API open data ADEME (Syderep). Cache 24 h.

    Filtre : filiere=ASL (Articles de Sport et Loisirs)
             type_dech=CAT_1 (Cycles et EDP non motorisés)
    ~497 lignes — un seul appel suffit.
    Doc API : https://data.ademe.fr/datasets/rep-tonnages-de-dechets-traites-des-filieres-rep/api-doc
    """
    params = {
        "qs":   "filiere:ASL AND type_dech:CAT_1",
        "size": 10_000,
    }
    try:
        r = requests.get(API_ADEME_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(data.get("results", []))
        if df.empty:
            return df
        df["traitement"]  = df["typ_trt"].map(LABELS_TRT).fillna(df["typ_trt"])
        df["famille_trt"] = df["traitement"].apply(_famille_traitement)
        return df
    except Exception as e:
        st.warning(f"API ADEME indisponible : {e}")
        return pd.DataFrame()


def _famille_traitement(label: str) -> str:
    if any(x in label for x in ("Recyclage", "Réemploi", "Préparation")):
        return "Valorisé matière / réemploi"
    if "Valorisation énergétique" in label:
        return "Valorisation énergétique"
    if "Élimination" in label:
        return "Éliminé"
    return "Autre"


# ─── Fonctions d'agrégation ───────────────────────────────────────────────────

def par_annee_traitement(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["annee", "traitement"], as_index=False)["masse"]
        .sum()
        .rename(columns={"masse": "tonnes"})
        .sort_values(["annee", "tonnes"], ascending=[True, False])
    )


def par_annee_famille(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["annee", "famille_trt"], as_index=False)["masse"]
        .sum()
        .rename(columns={"masse": "tonnes"})
    )


def par_departement(df: pd.DataFrame, annee: int | None = None) -> pd.DataFrame:
    if annee:
        df = df[df["annee"] == annee]
    return (
        df.groupby("dep_site_trt", as_index=False)["masse"]
        .sum()
        .rename(columns={"masse": "tonnes", "dep_site_trt": "departement"})
        .sort_values("tonnes", ascending=False)
    )


# ─── En-tête ─────────────────────────────────────────────────────────────────

st.title("🚲 Observatoire du vélo d'occasion — France")
st.caption(
    f"POC coordonné par [France Vélo]({URL_FRANCE_VELO}) · "
    f"Données : [Observatoire du Cycle UESC]({URL_UESC}) · "
    f"[API REP open data ADEME]({URL_ADEME_API})"
)

# ─── Chargement des données REP ───────────────────────────────────────────────

with st.spinner("Chargement des données REP ADEME..."):
    df_rep = fetch_rep_cycles()

rep_ok = not df_rep.empty

# ─── KPI ─────────────────────────────────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Ventes pro + reconditionnement 2025",
    "~200 000",
    "+14 % vs 2024",
    help=f"Source : Observatoire du Cycle UESC 2025 — {URL_UESC}",
)
col2.metric(
    "Estimation marché total 2025",
    "~500–550 k",
    "≈ 23 % des acquisitions",
    help="Pro + C2C particuliers + ESS + flottes. "
         "Pour comparaison : l'automobile est à 78 % (3,5 occasions pour 1 neuf).",
)
col3.metric(
    "Réparations en atelier 2025",
    "6,3 M",
    "Proxy usage vélo",
    help=f"Source : Observatoire du Cycle UESC 2025 — {URL_UESC}",
)
if rep_ok:
    tonnes_2024 = round(df_rep[df_rep["annee"] == 2024]["masse"].sum())
    col4.metric(
        "Collecte REP cycles (CAT_1) 2024",
        f"{tonnes_2024:,} t".replace(",", " "),
        "Source : API ADEME Syderep",
        help=f"Données en direct depuis l'API ADEME — {URL_ADEME_API}",
    )
else:
    col4.metric(
        "Collecte REP cycles 2024",
        "9 025 t",
        help=f"Source : bilan Ecologic PDF — {URL_ADEME_BILAN}",
    )

st.divider()

# ─── Onglets ─────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Données historiques",
    "♻️ Filière REP — API ADEME",
    "🔧 Proxys d'usage",
    "🧮 Modèle d'estimation",
])


# ── Onglet 1 : Historique ─────────────────────────────────────────────────────

with tab1:
    st.subheader("Évolution des ventes de vélos d'occasion")
    st.caption(
        f"Ventes pro : données [Observatoire du Cycle UESC]({URL_UESC}). "
        f"C2C particuliers : estimation [6T]({URL_6T}) / [Troc Vélo]({URL_TROCVELO})."
    )

    fig_hist = go.Figure()
    fig_hist.add_bar(
        x=DATA_HISTORIQUE["annee"],
        y=DATA_HISTORIQUE["ventes_pro_k"],
        name="Ventes pro confirmées (k unités)",
        marker_color="#185FA5",
    )
    fig_hist.add_bar(
        x=DATA_HISTORIQUE["annee"],
        y=DATA_HISTORIQUE["estimation_c2c_k"],
        name="Estimation C2C particuliers (k unités)",
        marker_color="#9FE1CB",
    )
    fig_hist.update_layout(
        barmode="stack",
        xaxis_title="Année",
        yaxis_title="Unités (milliers)",
        legend=dict(orientation="h", y=-0.25),
        plot_bgcolor="white",
        height=380,
    )
    st.plotly_chart(fig_hist, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        fig_neuf = px.line(
            DATA_HISTORIQUE,
            x="annee", y="ventes_neuf_M",
            title="Ventes de vélos neufs (millions d'unités)",
            markers=True,
            color_discrete_sequence=["#BA7517"],
        )
        fig_neuf.update_layout(
            plot_bgcolor="white", height=280,
            xaxis_title="", yaxis_title="Millions d'unités",
        )
        st.plotly_chart(fig_neuf, use_container_width=True)

    with col_b:
        fig_repar = px.line(
            DATA_HISTORIQUE,
            x="annee", y="reparations_atel_M",
            title="Réparations en atelier (millions d'interventions)",
            markers=True,
            color_discrete_sequence=["#0F6E56"],
        )
        fig_repar.update_layout(
            plot_bgcolor="white", height=280,
            xaxis_title="", yaxis_title="Millions d'interventions",
        )
        st.plotly_chart(fig_repar, use_container_width=True)

    with st.expander("Tableau des données brutes"):
        st.dataframe(
            DATA_HISTORIQUE.rename(columns={
                "annee":              "Année",
                "ventes_pro_k":       "Ventes pro (k)",
                "estimation_c2c_k":   "Estimation C2C (k)",
                "ventes_neuf_M":      "Ventes neuf (M)",
                "reparations_atel_M": "Réparations atelier (M)",
            }),
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        f"Sources : [Observatoire du Cycle UESC]({URL_UESC}) 2024-2025 · "
        f"estimations [France Vélo]({URL_FRANCE_VELO}) / [6T]({URL_6T}) · "
        f"[L'Heureux Cyclage]({URL_HEUREUX_CYCLAGE})"
    )


# ── Onglet 2 : Filière REP ───────────────────────────────────────────────────

with tab2:
    st.subheader("Filière REP ASL — Catégorie 1 : Cycles et EDP non motorisés")
    st.markdown(
        f"Données chargées en direct depuis l'[API open data ADEME]({URL_ADEME_API}) (Syderep). "
        f"Filtre : `filiere=ASL` + `type_dech=CAT_1`. "
        f"Éco-organisme agréé : [Ecologic]({URL_ECOLOGIC}). "
        f"[Tableau de bord filière ASL]({URL_ADEME_TABLEAU}) · "
        f"[Bilan annuel PDF]({URL_ADEME_BILAN})"
    )

    if not rep_ok:
        st.error(
            f"Les données REP n'ont pas pu être chargées depuis l'[API ADEME]({URL_ADEME_API}). "
            "Vérifiez votre connexion et réessayez."
        )
    else:
        annees_rep = sorted(df_rep["annee"].unique())
        df_2024    = df_rep[df_rep["annee"] == 2024]
        df_2023    = df_rep[df_rep["annee"] == 2023]

        tonnes_2024   = df_2024["masse"].sum()
        tonnes_2023   = df_2023["masse"].sum()
        delta_pct     = (tonnes_2024 - tonnes_2023) / tonnes_2023 * 100 if tonnes_2023 else 0
        valorise_2024 = df_2024[
            df_2024["famille_trt"] == "Valorisé matière / réemploi"
        ]["masse"].sum()

        k1, k2, k3 = st.columns(3)
        k1.metric(
            "Tonnage total CAT_1 traité (2024)",
            f"{tonnes_2024:,.0f} t".replace(",", " "),
            f"{delta_pct:+.0f} % vs 2023",
        )
        k2.metric(
            "Dont valorisé matière / réemploi (2024)",
            f"{valorise_2024:,.0f} t".replace(",", " "),
            f"{valorise_2024 / tonnes_2024 * 100:.0f} % du total",
        )
        k3.metric(
            "Années disponibles dans l'API",
            f"{min(annees_rep)} – {max(annees_rep)}",
            f"{len(annees_rep)} millésimes",
        )

        st.divider()

        col_r1, col_r2 = st.columns(2)

        with col_r1:
            df_famille = par_annee_famille(df_rep)
            fig_famille = px.bar(
                df_famille,
                x="annee", y="tonnes", color="famille_trt",
                title="Tonnages par famille de traitement",
                labels={
                    "tonnes":      "Tonnes",
                    "annee":       "Année",
                    "famille_trt": "Famille",
                },
                color_discrete_map={
                    "Valorisé matière / réemploi": "#185FA5",
                    "Valorisation énergétique":    "#BA7517",
                    "Éliminé":                     "#993C1D",
                    "Autre":                       "#888780",
                },
            )
            fig_famille.update_layout(
                plot_bgcolor="white", height=340,
                legend=dict(orientation="h", y=-0.35),
            )
            st.plotly_chart(fig_famille, use_container_width=True)

        with col_r2:
            annee_trt = st.selectbox(
                "Détail par type de traitement — année",
                annees_rep,
                index=len(annees_rep) - 1,
            )
            df_trt_sel = par_annee_traitement(df_rep)
            df_trt_sel = df_trt_sel[df_trt_sel["annee"] == annee_trt]
            fig_trt = px.bar(
                df_trt_sel.sort_values("tonnes"),
                x="tonnes", y="traitement",
                orientation="h",
                title=f"Détail par type de traitement ({annee_trt})",
                labels={"tonnes": "Tonnes", "traitement": ""},
                color="traitement",
                color_discrete_map=COULEURS_TRT,
            )
            fig_trt.update_layout(
                plot_bgcolor="white", height=340, showlegend=False,
            )
            st.plotly_chart(fig_trt, use_container_width=True)

        st.divider()
        st.subheader("Répartition départementale")

        annee_dep = st.selectbox(
            "Année",
            annees_rep,
            index=len(annees_rep) - 1,
            key="dep_annee",
        )
        df_dep = par_departement(df_rep, annee=annee_dep)
        st.dataframe(
            df_dep.rename(columns={
                "departement": "Département",
                "tonnes":      "Tonnage (t)",
            }),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Données brutes API (toutes années)"):
            cols = [
                "annee", "dep_site_trt", "typ_trt",
                "traitement", "famille_trt", "nom_usuel", "masse",
            ]
            st.dataframe(
                df_rep[cols].rename(columns={
                    "annee":        "Année",
                    "dep_site_trt": "Département",
                    "typ_trt":      "Code traitement",
                    "traitement":   "Traitement",
                    "famille_trt":  "Famille",
                    "nom_usuel":    "Matière",
                    "masse":        "Tonnes",
                }),
                use_container_width=True,
                hide_index=True,
            )

        st.caption(
            f"[API ADEME Syderep]({URL_ADEME_API}) · "
            f"Filtre : `filiere:ASL AND type_dech:CAT_1` · "
            f"Éco-organisme : [Ecologic]({URL_ECOLOGIC}) (FR000017) · "
            f"[Tableau de bord filière ASL]({URL_ADEME_TABLEAU})"
        )


# ── Onglet 3 : Proxys d'usage ─────────────────────────────────────────────────

with tab3:
    st.subheader("Indicateurs indirects d'usage du vélo")
    st.caption(
        "Ces proxys permettent d'estimer le dynamisme du marché de l'occasion "
        "sans disposer de données directes sur les transactions C2C."
    )

    col_p1, col_p2 = st.columns(2)

    with col_p1:
        st.markdown("**Proxys entretien & réparation**")
        st.metric(
            "Réparations en atelier 2025", "6,3 M", "+7 % vs 2024",
            help=f"Source : Observatoire du Cycle UESC — {URL_UESC}",
        )
        st.metric("CA réparation 2025", "128 M€")
        st.metric(
            "Ratio réparation / vente neuve", "~3,5×",
            help="Les professionnels réparent 3,5× plus de vélos qu'ils n'en vendent neufs.",
        )
        st.metric(
            "Vélos collectés L'Heureux Cyclage", "74 300 / an",
            help=f"Source : L'Heureux Cyclage — {URL_HEUREUX_CYCLAGE}",
        )
        st.metric("Taux de réemploi réseau ESS", "71 %")

    with col_p2:
        st.markdown("**Gisement & flux**")
        st.metric("Vélos inutilisés en France", "~9–11 M")
        st.metric("Vélos jetés / détruits par an", "1–1,5 M")
        st.metric("Réparables parmi les déchets", "70 %")
        st.metric(
            "Ventes neuf 2025", "1,83 M", "−6 % vs 2024",
            help=f"Source : Observatoire du Cycle UESC — {URL_UESC}",
        )
        st.metric(
            "Annonces Le Bon Coin (2019)", "~345 k",
            help="Dont 75 % sur Le Bon Coin, 4 % sur Troc Vélo. Chiffre non actualisé depuis 2019.",
        )

    st.divider()
    st.subheader("Disponibilité des données par segment")

    df_gaps = pd.DataFrame({
        "Segment": [
            "Ventes pro (vélocistes, plateformes)",
            "Reconditionnement (Upway, Loop Sports…)",
            "Flottes revendues (leasing, VAE service, vélos partagés)",
            "ESS & associations (L'Heureux Cyclage, recycleries)",
            "C2C particuliers (Le Bon Coin, Troc Vélo…)",
            "Proxy pneumatiques / freins vélo",
            "Proxy comptages cyclistes (Eco-Compteur)",
        ],
        "Disponibilité (%)": [70, 60, 25, 40, 30, 35, 20],
        "Statut": [
            "Partielle", "Partielle", "Très faible", "Faible",
            "Faible", "Faible", "À construire",
        ],
        "Note": [
            "Observatoire UESC + déclarations vélocistes",
            "Données partielles Upway / Loop Sports",
            "Aucune consolidation nationale à ce jour",
            "Données L'Heureux Cyclage disponibles mais non agrégées",
            "Estimation 6T — non actualisée depuis 2019",
            "Données fabricants non publiées",
            "Comptages disponibles mais non corrélés à l'occasion",
        ],
    })

    fig_gaps = px.bar(
        df_gaps,
        x="Disponibilité (%)", y="Segment",
        orientation="h",
        color="Statut",
        color_discrete_map={
            "Partielle":    "#185FA5",
            "Faible":       "#BA7517",
            "Très faible":  "#993C1D",
            "À construire": "#888780",
        },
        title="Maturité des données disponibles par segment",
        hover_data=["Note"],
    )
    fig_gaps.update_layout(
        plot_bgcolor="white", height=380,
        yaxis_autorange="reversed",
        legend=dict(orientation="h", y=-0.25),
    )
    st.plotly_chart(fig_gaps, use_container_width=True)

    st.info(
        "**Proxys à construire en priorité** : ventes de pneumatiques vélo "
        "(proxy fort d'usage), plaquettes de frein, et suivi des annonces "
        f"Le Bon Coin via partenariat ou API tierce."
    )

    st.caption(
        f"Sources : [Observatoire du Cycle UESC]({URL_UESC}) · "
        f"[L'Heureux Cyclage]({URL_HEUREUX_CYCLAGE}) · "
        f"[Troc Vélo]({URL_TROCVELO}) · "
        f"[Upway]({URL_UPWAY}) · "
        f"[6T bureau de recherche]({URL_6T})"
    )


# ── Onglet 4 : Modèle d'estimation ───────────────────────────────────────────

with tab4:
    st.subheader("Modèle paramétrable d'estimation du marché")

    # ── Note pédagogique sur le ratio ──────────────────────────────────────────
    st.info(
        "**Comment lire le ratio occasion / neuf ?**\n\n"
        "Le paramètre « part de l'occasion dans les acquisitions » représente "
        "la fraction des vélos achetés qui sont des vélos d'occasion "
        "(par rapport au total neuf + occasion). À 23 %, cela signifie que "
        "pour 100 vélos achetés, 23 sont d'occasion et 77 sont neufs — "
        "soit **1 vélo d'occasion pour 3,3 vélos neufs**.\n\n"
        "C'est très différent de l'automobile, où l'occasion est majoritaire : "
        "**1 voiture neuve vendue pour 3,5 voitures d'occasion** qui changent de main "
        "(78 % du marché est de l'occasion). Le marché du vélo d'occasion est donc "
        "encore peu mature : il représente 4 à 5× moins de transactions relatives que l'auto."
    )

    st.caption(
        "Ajustez les hypothèses dans la barre latérale pour calibrer l'estimation."
    )

    with st.sidebar:
        st.header("⚙️ Paramètres du modèle")
        st.markdown("---")

        neuf = st.slider(
            "Ventes neuf (millions d'unités)",
            min_value=1.5, max_value=2.5, value=1.83, step=0.05,
            help=f"Source : Observatoire du Cycle UESC 2025 — {URL_UESC}",
        )
        part_occ = st.slider(
            "Part de l'occasion dans les acquisitions totales (%)",
            min_value=15, max_value=40, value=23, step=1,
            help=(
                "Part des vélos d'occasion dans l'ensemble des achats de vélos "
                "(neuf + occasion). À titre de comparaison, ce taux est de 78 % "
                "dans l'automobile."
            ),
        )
        pro = st.slider(
            "Ventes pro + reconditionnement (k unités)",
            min_value=150, max_value=300, value=200, step=5,
            help=f"Source : Observatoire du Cycle UESC 2025 — {URL_UESC}",
        )
        ess = st.slider(
            "ESS & associations (k unités)",
            min_value=20, max_value=100, value=30, step=5,
            help=f"Estimation basée sur L'Heureux Cyclage — {URL_HEUREUX_CYCLAGE}",
        )
        flottes = st.slider(
            "Flottes revendues (k unités)",
            min_value=10, max_value=100, value=40, step=5,
            help="Leasing, loueurs, opérateurs de vélos partagés — très peu documenté.",
        )
        st.markdown("---")
        st.caption("Les paramètres modifient le modèle central uniquement.")

    # ── Calcul ────────────────────────────────────────────────────────────────
    # total_occ = neuf × (part_occ / (1 - part_occ))
    # Exemple : 23% → pour 1,83M neufs (= 77%), l'occasion (23%) = 1,83M × 23/77 = ~546k
    total_occ    = round((neuf * 1_000 * part_occ) / (100 - part_occ))
    c2c          = max(0, total_occ - pro - ess - flottes)

    # Ratio neufs par vélo d'occasion (> 1 si marché neuf dominant, < 1 si occasion dominant)
    # Automobile : 0.29 neuf par occasion (= 1 neuf pour 3.5 occasions)
    # Vélo actuel : ~3.3 neufs par occasion (= 1 occasion pour 3.3 neufs)
    ratio_neuf_par_occ = round((neuf * 1_000) / total_occ, 1) if total_occ > 0 else 0

    # Pour l'affichage dans le même sens que l'automobile :
    ratio_occ_par_neuf = round(total_occ / (neuf * 1_000), 2) if neuf > 0 else 0

    # ── KPI résultats ─────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)

    k1.metric(
        "Marché total estimé",
        f"{total_occ:,} k".replace(",", " "),
        help="Pro + C2C + ESS + flottes",
    )
    k2.metric(
        "dont C2C entre particuliers",
        f"{c2c:,} k".replace(",", " "),
        help="Calculé par soustraction des canaux pro, ESS et flottes.",
    )
    k3.metric(
        "Neufs vendus pour 1 occasion",
        f"1 occ. pour {ratio_neuf_par_occ} neufs",
        help=(
            f"À {part_occ} % de part occasion, on compte {ratio_neuf_par_occ} vélos neufs "
            f"vendus pour chaque vélo d'occasion. "
            "Automobile (référence) : 1 occasion pour 0,3 neuf."
        ),
    )
    k4.metric(
        "Occasions pour 1 neuf vendu",
        f"1 neuf → {ratio_occ_par_neuf} occ.",
        help=(
            "Dans le même sens que la référence automobile : "
            "'1 voiture neuve pour 3,5 d'occasion'. "
            f"Le vélo est à {ratio_occ_par_neuf} d'occasion pour 1 neuf. "
            "Automobile : 3,5."
        ),
    )

    st.divider()

    col_m1, col_m2 = st.columns([3, 2])

    with col_m1:
        df_segments = pd.DataFrame({
            "Segment": [
                "Ventes pro + reconditionnement",
                "C2C entre particuliers",
                "ESS & associations",
                "Flottes revendues",
            ],
            "Volume (k)": [pro, c2c, ess, flottes],
            "Fiabilité données": ["Bonne", "Estimée", "Partielle", "Très faible"],
        })
        fig_seg = px.bar(
            df_segments,
            x="Segment", y="Volume (k)",
            color="Segment",
            color_discrete_sequence=["#185FA5", "#0F6E56", "#BA7517", "#993C1D"],
            title="Décomposition estimée du marché de l'occasion",
        )
        fig_seg.update_layout(
            plot_bgcolor="white", showlegend=False, height=360,
        )
        st.plotly_chart(fig_seg, use_container_width=True)

    with col_m2:
        st.markdown("**Détail des segments**")
        st.dataframe(df_segments, use_container_width=True, hide_index=True)

        st.markdown("**Comparaison automobile**")
        df_auto = pd.DataFrame({
            "Marché":        ["Automobile", "Vélo (actuel)"],
            "Occ. pour 1 neuf": [3.5, ratio_occ_par_neuf],
        })
        fig_auto = px.bar(
            df_auto,
            x="Marché", y="Occ. pour 1 neuf",
            color="Marché",
            color_discrete_sequence=["#888780", "#185FA5"],
            title="Occasions pour 1 neuf vendu",
            text="Occ. pour 1 neuf",
        )
        fig_auto.update_traces(textposition="outside")
        fig_auto.update_layout(
            plot_bgcolor="white", showlegend=False, height=280,
            yaxis=dict(range=[0, 4.5]),
        )
        st.plotly_chart(fig_auto, use_container_width=True)

    st.divider()
    st.subheader("Comparaison de scénarios")

    scenarios = pd.DataFrame({
        "Scénario":          ["Bas", "Central (modèle actuel)", "Haut"],
        "Ventes neuf (M)":   [1.95, neuf, 1.70],
        "Part occasion (%)": [18,   part_occ, 30],
        "Total estimé (k)":  [
            round((1.95e6 * 18) / (100 - 18) / 1_000),
            total_occ,
            round((1.70e6 * 30) / (100 - 30) / 1_000),
        ],
        "Occ. pour 1 neuf":  [
            round((1.95e6 * 18 / 82) / 1.95e6, 2),
            ratio_occ_par_neuf,
            round((1.70e6 * 30 / 70) / 1.70e6, 2),
        ],
    })

    fig_scen = px.bar(
        scenarios,
        x="Scénario", y="Total estimé (k)",
        color="Scénario",
        color_discrete_sequence=["#9FE1CB", "#185FA5", "#BA7517"],
        title="Scénarios bas / central / haut",
        text="Total estimé (k)",
    )
    fig_scen.update_traces(textposition="outside")
    fig_scen.update_layout(
        plot_bgcolor="white", showlegend=False, height=320,
    )
    st.plotly_chart(fig_scen, use_container_width=True)

    with st.expander("Tableau des scénarios"):
        st.dataframe(scenarios, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(
        "**Prochaines étapes pour fiabiliser le modèle**\n\n"
        f"- Intégrer les ventes de pneumatiques vélo (proxy fort, données [UESC]({URL_UESC}) ou fabricants)\n"
        f"- Consolider les déclarations ESS ([L'Heureux Cyclage]({URL_HEUREUX_CYCLAGE}), recycleries sportives)\n"
        f"- Obtenir les données Le Bon Coin via partenariat ou API — [Troc Vélo]({URL_TROCVELO}) en parallèle\n"
        "- Documenter les cessions de flottes (leasing VAE, opérateurs de vélos partagés)\n"
        f"- Les données [API ADEME]({URL_ADEME_API}) (onglet REP) sont rafraîchies automatiquement chaque 24 h"
    )


# ─── Footer ──────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    f"Sources : [Observatoire du Cycle UESC]({URL_UESC}) 2025 · "
    f"[Bilan Filière REP ASL 2024 — ADEME / Ecologic]({URL_ADEME_BILAN}) "
    f"via [API open data Syderep]({URL_ADEME_API}) · "
    f"Étude [6T]({URL_6T}) impact socio-économique du vélo · "
    f"[L'Heureux Cyclage]({URL_HEUREUX_CYCLAGE}) · "
    f"[Troc Vélo]({URL_TROCVELO}) · "
    f"[Upway]({URL_UPWAY}) · "
    f"Rapport impact économique vélo ADEME 2020. "
    f"POC coordonné par [France Vélo]({URL_FRANCE_VELO})."
)
