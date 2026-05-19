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

# Données historiques mises à jour manuellement
# Sources : Observatoire du Cycle UESC + estimations filière France Vélo / 6T
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
    depuis l'API open data ADEME. Cache 24 h pour éviter des appels répétés.

    Filtre : filiere=ASL (Articles de Sport et Loisirs)
             type_dech=CAT_1 (Cycles et EDP non motorisés)
    497 lignes au total — un seul appel suffit (size=10000).
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
        df["traitement"] = df["typ_trt"].map(LABELS_TRT).fillna(df["typ_trt"])
        df["famille_trt"] = df["traitement"].apply(_famille_traitement)
        return df
    except Exception as e:
        st.warning(f"API ADEME indisponible : {e}")
        return pd.DataFrame()


def _famille_traitement(label: str) -> str:
    """Regroupe les types de traitement en 3 familles pour simplifier les graphiques."""
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
    "Estimation des ventes de vélos d'occasion · "
    "Sources : Observatoire du Cycle UESC · Ecologic / ADEME (API REP open data)"
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
    help="Source : Observatoire du Cycle UESC 2025",
)
col2.metric(
    "Estimation marché total 2025",
    "~500–550 k",
    "≈ 23 % des acquisitions",
    help="Pro + C2C particuliers + ESS + flottes",
)
col3.metric(
    "Réparations en atelier 2025",
    "6,3 M",
    "Proxy usage vélo",
    help="Source : Observatoire du Cycle UESC 2025",
)
if rep_ok:
    tonnes_2024 = round(df_rep[df_rep["annee"] == 2024]["masse"].sum())
    col4.metric(
        "Collecte REP cycles (CAT_1) 2024",
        f"{tonnes_2024:,} t".replace(",", " "),
        "Source : API ADEME Syderep",
    )
else:
    col4.metric(
        "Collecte REP cycles 2024",
        "9 025 t",
        "Source : bilan Ecologic PDF",
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
        "Les ventes pro sont confirmées par l'Observatoire du Cycle (UESC). "
        "Le C2C entre particuliers est une estimation (source : 6T / Troc Vélo)."
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
        "Sources : Observatoire du Cycle UESC 2024-2025 · "
        "estimations France Vélo / 6T · L'Heureux Cyclage"
    )


# ── Onglet 2 : Filière REP ───────────────────────────────────────────────────

with tab2:
    st.subheader("Filière REP ASL — Catégorie 1 : Cycles et EDP non motorisés")
    st.caption(
        "Données chargées en direct depuis l'API open data ADEME (Syderep). "
        "Filtre : `filiere=ASL` + `type_dech=CAT_1`. "
        "Éco-organisme : Ecologic."
    )

    if not rep_ok:
        st.error(
            "Les données REP n'ont pas pu être chargées depuis l'API ADEME. "
            "Vérifiez votre connexion et réessayez."
        )
    else:
        annees_rep = sorted(df_rep["annee"].unique())
        df_2024 = df_rep[df_rep["annee"] == 2024]
        df_2023 = df_rep[df_rep["annee"] == 2023]

        tonnes_2024 = df_2024["masse"].sum()
        tonnes_2023 = df_2023["masse"].sum()
        delta_pct = (
            (tonnes_2024 - tonnes_2023) / tonnes_2023 * 100
            if tonnes_2023 else 0
        )
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
                    "tonnes": "Tonnes",
                    "annee": "Année",
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
            "API : `data.ademe.fr/datasets/rep-tonnages-de-dechets-traites-des-filieres-rep` · "
            "Filtre : `filiere:ASL AND type_dech:CAT_1` · "
            "Éco-organisme : Ecologic (FR000017)"
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
        st.metric("Réparations en atelier 2025", "6,3 M", "+7 % vs 2024")
        st.metric("CA réparation 2025", "128 M€")
        st.metric(
            "Ratio réparation / vente neuve", "~3,5×",
            help="Les pros réparent 3,5× plus de vélos qu'ils n'en vendent neufs",
        )
        st.metric("Vélos collectés L'Heureux Cyclage", "74 300 / an")
        st.metric("Taux de réemploi réseau ESS", "71 %")

    with col_p2:
        st.markdown("**Gisement & flux**")
        st.metric("Vélos inutilisés en France", "~9–11 M")
        st.metric("Vélos jetés / détruits par an", "1–1,5 M")
        st.metric("Réparables parmi les déchets", "70 %")
        st.metric("Ventes neuf 2025", "1,83 M", "−6 % vs 2024")
        st.metric(
            "Annonces Le Bon Coin (2019)", "~345 k",
            help="Dont 75 % sur Le Bon Coin, 4 % sur Troc Vélo — chiffre non actualisé",
        )

    st.divider()
    st.subheader("Disponibilité des données par segment")
    st.caption(
        "État des lieux de la maturité des données disponibles "
        "pour chaque canal de l'occasion."
    )

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
        "Le Bon Coin via partenariat ou API tierce."
    )


# ── Onglet 4 : Modèle d'estimation ───────────────────────────────────────────

with tab4:
    st.subheader("Modèle paramétrable d'estimation du marché")
    st.caption(
        "Ajustez les hypothèses dans la barre latérale pour calibrer "
        "l'estimation du marché total de l'occasion."
    )

    with st.sidebar:
        st.header("⚙️ Paramètres du modèle")
        st.markdown("---")

        neuf = st.slider(
            "Ventes neuf (millions d'unités)",
            min_value=1.5, max_value=2.5, value=1.83, step=0.05,
            help="Source : Observatoire du Cycle UESC 2025",
        )
        part_occ = st.slider(
            "Part de l'occasion dans les acquisitions (%)",
            min_value=15, max_value=35, value=23, step=1,
            help="Source : étude 6T 2020, confirmée par Observatoire UESC",
        )
        pro = st.slider(
            "Ventes pro + reconditionnement (k unités)",
            min_value=150, max_value=300, value=200, step=5,
            help="Source : Observatoire du Cycle UESC 2025",
        )
        ess = st.slider(
            "ESS & associations (k unités)",
            min_value=20, max_value=100, value=30, step=5,
            help="Estimation basée sur L'Heureux Cyclage + recycleries sportives",
        )
        flottes = st.slider(
            "Flottes revendues (k unités)",
            min_value=10, max_value=100, value=40, step=5,
            help="Leasing, loueurs, opérateurs de vélos partagés — très peu documenté",
        )
        st.markdown("---")
        st.caption("Les paramètres modifient le modèle central uniquement.")

    # Calcul du modèle
    total_occ = round((neuf * 1_000 * part_occ) / (100 - part_occ))
    c2c = max(0, total_occ - pro - ess - flottes)
    ratio = round(total_occ / (neuf * 1_000), 2)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Marché total estimé",
        f"{total_occ:,} k".replace(",", " "),
        help="Pro + C2C + ESS + flottes",
    )
    k2.metric(
        "dont C2C entre particuliers",
        f"{c2c:,} k".replace(",", " "),
        help="Calculé par soustraction des autres canaux connus",
    )
    k3.metric(
        "Ratio occasion / neuf",
        f"1 pour {ratio:.1f}",
        "Réf. automobile : 1 pour 3,5",
    )
    k4.metric(
        "Part de l'occasion",
        f"{part_occ} %",
        "des acquisitions vélo",
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
        plot_bgcolor="white", showlegend=False, height=340,
    )
    st.plotly_chart(fig_scen, use_container_width=True)

    with st.expander("Tableau des scénarios"):
        st.dataframe(scenarios, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(
        "**Prochaines étapes pour fiabiliser le modèle**\n\n"
        "- Intégrer les ventes de pneumatiques vélo (proxy fort, données UESC ou fabricants)\n"
        "- Consolider les déclarations ESS (L'Heureux Cyclage, recycleries sportives)\n"
        "- Obtenir les données Le Bon Coin via partenariat ou API\n"
        "- Documenter les cessions de flottes (leasing VAE, vélos partagés)\n"
        "- Les données API ADEME (onglet REP) sont rafraîchies automatiquement chaque 24 h"
    )


# ─── Footer ──────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    "Sources : Observatoire du Cycle UESC 2025 · "
    "Bilan Filière REP ASL Données 2024 (ADEME / Ecologic) via API open data Syderep · "
    "Étude 6T impact socio-économique du vélo · L'Heureux Cyclage · "
    "Troc Vélo · Upway · Rapport impact économique vélo ADEME 2020. "
    "POC coordonné par France Vélo."
)
