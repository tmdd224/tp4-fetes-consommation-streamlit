from pathlib import Path
import unicodedata

import altair as alt
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Fêtes & consommation · Sénégal",
    page_icon=":material/monitoring:",
    layout="wide",
)


def find_data_dir() -> Path:
    candidates = [Path("TP4"), Path(".")]
    for candidate in candidates:
        if (candidate / "ventes_journalieres.csv").is_file():
            return candidate
    raise FileNotFoundError(
        "Fichiers CSV introuvables. Lancez Streamlit depuis le dossier du TP "
        "qui contient le sous-dossier TP4/."
    )


DATA_DIR = find_data_dir()


def normalize_label(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value)).strip().casefold()


@st.cache_data(max_entries=4)
def load_data(data_dir: str):
    base = Path(data_dir)
    categories = pd.read_csv(base / "categories.csv", encoding="utf-8")
    stores = pd.read_csv(base / "magasins.csv", encoding="utf-8")
    events = pd.read_csv(
        base / "calendrier_evenements.csv",
        parse_dates=["date_debut", "date_fin"],
        encoding="utf-8",
    )
    sales = pd.read_csv(
        base / "ventes_journalieres.csv",
        parse_dates=["date"],
        encoding="utf-8",
        usecols=["date", "magasin_id", "categorie", "quantite"],
    )

    category_lookup = {normalize_label(value): value for value in categories["categorie"]}
    sales["categorie"] = sales["categorie"].map(
        lambda value: category_lookup.get(normalize_label(value))
    )
    unknown = int(sales["categorie"].isna().sum())
    if unknown:
        raise ValueError(
            f"{unknown} lignes de ventes ont une catégorie absente de categories.csv."
        )

    sales = sales.drop_duplicates(
        ["date", "magasin_id", "categorie"], keep="first"
    ).copy()
    sales["quantite"] = pd.to_numeric(sales["quantite"], errors="coerce")
    sales.loc[sales["quantite"] < 0, "quantite"] = 0
    return sales, events, stores, categories


try:
    sales, events, stores, categories = load_data(str(DATA_DIR.resolve()))
except (OSError, ValueError, pd.errors.ParserError) as error:
    st.error(f"Impossible de charger les données : {error}", icon=":material/error:")
    st.stop()

st.title("Fêtes & consommation au Sénégal")
st.caption(
    "Explorer les ventes quotidiennes autour des fêtes, alignées sur J0. "
    "Données simulées à des fins pédagogiques."
)

left, middle, right = st.columns([1, 1, 1])
event_names = sorted(events["evenement"].dropna().unique().tolist())
selected_event = left.selectbox("Fête / événement", event_names, index=event_names.index("Tabaski") if "Tabaski" in event_names else 0)
city_options = ["National"] + sorted(stores["ville"].dropna().unique().tolist())
selected_city = middle.selectbox("Ville", city_options, index=0)
category_options = sorted(categories["categorie"].dropna().unique().tolist())
default_category = "betail_mouton" if "betail_mouton" in category_options else category_options[0]
selected_category = right.selectbox(
    "Catégorie", category_options, index=category_options.index(default_category)
)

year_min = int(sales["date"].dt.year.min())
year_max = int(sales["date"].dt.year.max())
available_years = sorted(
    events.loc[events["evenement"].eq(selected_event), "annee"]
    .astype(int)
    .unique()
    .tolist()
)
available_years = [year for year in available_years if year_min <= year <= year_max]
if not available_years:
    st.warning("Aucune occurrence de cet événement ne se trouve dans la période de ventes.")
    st.stop()

year_range = st.slider(
    "Années à comparer",
    min_value=min(available_years),
    max_value=max(available_years),
    value=(min(available_years), max(available_years)),
    step=1,
)
window_days = st.slider("Fenêtre autour de J0 (jours)", min_value=7, max_value=60, value=30)

city_store_ids = (
    stores["magasin_id"].tolist()
    if selected_city == "National"
    else stores.loc[stores["ville"].eq(selected_city), "magasin_id"].tolist()
)
occurrences = events.loc[
    events["evenement"].eq(selected_event)
    & events["annee"].between(year_range[0], year_range[1])
    & events["annee"].isin(available_years),
    ["annee", "date_debut"],
].drop_duplicates().sort_values("annee")

if occurrences.empty:
    st.warning("Aucune occurrence ne correspond à la sélection.")
    st.stop()

selected_sales = sales.loc[
    sales["magasin_id"].isin(city_store_ids)
    & sales["categorie"].eq(selected_category)
    & sales["quantite"].notna()
].copy()

curves = []
for occurrence in occurrences.itertuples(index=False):
    start = occurrence.date_debut - pd.Timedelta(days=window_days)
    end = occurrence.date_debut + pd.Timedelta(days=window_days)
    daily = selected_sales.loc[
        selected_sales["date"].between(start, end),
        ["date", "magasin_id", "quantite"],
    ].copy()
    daily["jour_relatif"] = (daily["date"] - occurrence.date_debut).dt.days
    per_day = daily.groupby("jour_relatif").agg(
        quantite=("quantite", "sum"),
        magasins_observes=("magasin_id", "nunique"),
    )
    per_day = per_day.reindex(range(-window_days, window_days + 1))
    per_day["annee"] = int(occurrence.annee)
    curves.append(per_day.reset_index(names="jour_relatif"))

if not curves:
    st.warning("Aucune vente disponible pour ces filtres.")
    st.stop()

curve_data = pd.concat(curves, ignore_index=True)
curve_data["annee"] = curve_data["annee"].astype(str)
active_store_count = len(city_store_ids)
event_dates = occurrences.assign(date=occurrences["date_debut"].dt.strftime("%d/%m/%Y"))

first_metric, second_metric, third_metric = st.columns(3)
first_metric.metric("Années affichées", len(occurrences))
second_metric.metric("Points de vente", active_store_count)
third_metric.metric("Dates d’événement", f"{event_dates['date'].min()} – {event_dates['date'].max()}")

year_lines = (
    alt.Chart(curve_data.dropna(subset=["quantite"]))
    .mark_line(point=False, opacity=0.42)
    .encode(
        x=alt.X("jour_relatif:Q", title="Jours par rapport à la fête (J0)", scale=alt.Scale(domain=[-window_days, window_days])),
        y=alt.Y("quantite:Q", title=f"Quantité vendue ({categories.set_index('categorie').loc[selected_category, 'unite']})"),
        color=alt.Color("annee:N", title="Année"),
        detail="annee:N",
        tooltip=[
            alt.Tooltip("annee:N", title="Année"),
            alt.Tooltip("jour_relatif:Q", title="Jour relatif"),
            alt.Tooltip("quantite:Q", title="Quantité", format=",.1f"),
        ],
    )
)
mean_line = (
    alt.Chart(curve_data)
    .mark_line(color="#122B39", strokeWidth=3)
    .encode(
        x="jour_relatif:Q",
        y="mean(quantite):Q",
        tooltip=[
            alt.Tooltip("jour_relatif:Q", title="Jour relatif"),
            alt.Tooltip("mean(quantite):Q", title="Moyenne", format=",.1f"),
        ],
    )
)
j0_rule = (
    alt.Chart(pd.DataFrame({"jour_relatif": [0]}))
    .mark_rule(color="#D97706", strokeDash=[5, 4], strokeWidth=2)
    .encode(x="jour_relatif:Q")
)
chart = (year_lines + mean_line + j0_rule).properties(
    height=420,
    title=f"{selected_category} · {selected_city} · {selected_event}",
).interactive()
st.altair_chart(
    chart,
    width="stretch",
    alt=f"Ventes autour de {selected_event}, par année, pour {selected_category} à {selected_city}",
)

with st.expander("Dates, couverture et méthode"):
    st.write(
        "Chaque courbe annuelle additionne les quantités rapportées dans la ville "
        "sélectionnée; la ligne foncée indique la moyenne entre années. J0 est la "
        "date de l’événement dans le calendrier fourni."
    )
    st.write(
        "Les dates absentes ne sont pas converties artificiellement en ventes nulles. "
        "Le nombre de points de vente ayant une observation est disponible par jour."
    )
    st.dataframe(
        event_dates[["annee", "date"]].rename(
            columns={"annee": "Année", "date": "Date J0"}
        ),
        hide_index=True,
        alt="Dates des occurrences de l’événement dans les années sélectionnées",
    )
    coverage = curve_data.groupby("jour_relatif", as_index=False).agg(
        magasins_observes_moyens=("magasins_observes", "mean")
    )
    st.line_chart(
        coverage,
        x="jour_relatif",
        y="magasins_observes_moyens",
        x_label="Jours par rapport à J0",
        y_label="Magasins observés en moyenne",
        alt="Couverture quotidienne des points de vente dans la fenêtre de fête",
    )

st.caption(
    "Source : fichiers CSV du TP4. Les ventes et résultats sont fictifs et ne "
    "permettent pas de conclure sur le comportement réel d’une communauté."
)
