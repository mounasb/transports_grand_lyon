import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import json
import datetime as dt
import folium
from folium.plugins import MarkerCluster
import streamlit.components.v1 as components
from streamlit_option_menu import option_menu
from fuzzywuzzy import fuzz
import time
import pytz
import plotly.express as px


#Paramétrage
st.set_page_config(
     page_title="Transports du Grand Lyon",
     page_icon=":train:",
     layout="wide",
     initial_sidebar_state="expanded")
color_red_st = '#FF4B4B'        # rouge par défaut sur Streamlit
map_height = 800
st.markdown(
        f"""
<style>
    # .reportview-container .main .block-container{{
    #     max-width: 90%;
    #     padding-top: 5rem;
    #     padding-right: 5rem;
    #     padding-left: 5rem;
    #     padding-bottom: 5rem;
    # }}
    img{{
    	max-width:40%;
    	margin-bottom:0px;
    }}
    p{{
        font-size: x-large;
    }}
    li{{
        font-size:x-large;
    }}
    h1{{
        padding-right: 5rem;
        padding-left: 5rem;
        padding-bottom: 5rem;
    }}
    h4{{
        padding-bottom: 2rem;
    }}
</style>
""",
        unsafe_allow_html=True,
    )

# BACK END

# Authentification
import base64
from requests.auth import HTTPBasicAuth
USERNAME = st.secrets["USERNAME"]
PASSWORD = st.secrets["PASSWORD"]


def get_request_json(r):
    """ Retourne un DataFrame"""
    df = pd.json_normalize(r.json(), record_path='values')
    return df


def get_request_geojson(r):
    """ Retourne un DataFrame"""
    df = pd.json_normalize(r.json(), record_path='features')
    return df


def get_df_velov_tr():
    """ Récupère les disponibilités en temps réel des Vélo'v depuis l'API du Grand Lyon
        Retourne un DataFrame """

    link_velov = "https://download.data.grandlyon.com/ws/rdata/jcd_jcdecaux.jcdvelov/all.json?maxfeatures=-1&start=1"
    r_velov = requests.get(link_velov)
    bikes = get_request_json(r_velov)

    # insertion d'un timestamp
    t = [dt.datetime.now(pytz.timezone('Europe/Paris')).replace(microsecond=0) for i in range(len(bikes))]
    s = pd.Series(t, name = 'timestamp')
    bikes.insert(0, 'timestamp', s)

    columns_to_keep = ['timestamp', 'address', 'availability', 'available_bike_stands',
                       'available_bikes', 'bike_stands', 'lat', 'lng', 'name', 'status',]

    bikes = bikes[columns_to_keep]

    # transformer les colonnes de coordonnées en float
    bikes['lat'] = bikes['lat'].astype('float64')
    bikes['lng'] = bikes['lng'].astype('float64')

    return bikes


def get_map_velov_tr(df):
    """  Input = DataFrame velov temps réel
         Génère une carte Folium, l'exporte en html
         Eetourne le nom du fichier (str)"""

    centre = [45.7548790164649, 4.84367508189202]       # Guillotière
    map_velov = folium.Map(location=centre, zoom_start=14)
    map_velov.add_child(folium.TileLayer("cartodbpositron"))
    velov_cluster = MarkerCluster(name="Velo'v cluster").add_to(map_velov)

    # ajout marqueurs
    for i in range(len(df)):
        status = df.loc[i]['status']
        # loc = bikes.loc[i]['point_coord']
        loc = [df.loc[i]['lat'], df.loc[i]['lng']]
        velos_dispo = df.loc[i]['available_bikes']
        places_dispo = df.loc[i]['available_bike_stands']
        availability = df.loc[i]['availability']
        nom = df.loc[i]['name']
        adresse = df.loc[i]['address']
        max_width = 220
        seuil_velo = 3

        if velos_dispo > 1:
            v_dispo = 'vélos disponibles'
        else:
            v_dispo = 'vélo disponible'
        if places_dispo > 1:
            p_dispo = 'places disponibles'
        else:
            p_dispo = 'place disponible'

        if nom:
            pop = folium.Popup(f"<b>{nom}</b><br>• {velos_dispo} {v_dispo}<br>• {places_dispo} {p_dispo}", max_width=max_width)
        else:
            pop = folium.Popup(f"<b>{adresse}</b><br>• {velos_dispo} {v_dispo}<br>• {places_dispo} {p_dispo}", max_width=max_width)

        if status == 'CLOSED':
            icon = folium.Icon(color='gray', icon='glyphicon-remove')
            pop = folium.Popup(f"<b>{df.loc[i]['name']}</b><br>• STATION FERMÉE", max_width=max_width)
        else:
            if not availability:
                pop = folium.Popup(f"<b>{nom}</b><br>Données non disponibles", max_width=max_width)
                icon = folium.Icon(color='gray', icon="question-circle", prefix='fa')
            else:
                velos_dispo = int(df.loc[i]['available_bikes'])
                places_dispo = int(df.loc[i]['available_bike_stands'])
                if velos_dispo == 0:
                    icon = folium.Icon(color='red', icon="glyphicon-ban-circle")
                elif velos_dispo <= seuil_velo:
                    icon = folium.Icon(color="orange", icon="glyphicon-exclamation-sign")
                else:
                    icon = folium.Icon(color='darkblue', icon="bicycle", prefix="fa")

        folium.Marker(
            location=loc,
            popup=pop,
            icon=icon,
            ).add_to(velov_cluster)

    filename = 'data_grand_lyon/map_velov.html'
    map_velov.save(filename)

    return filename


def get_all_traces_color():
    """ Récupère les traces de toutes les lignes TCL depuis 3 API du Grand Lyon,
        construit une carte, exporte un fichier html, et retourne le nom du fichier (str)"""

    # API tracés de tram
    link_tram = "https://download.data.grandlyon.com/wfs/rdata?SERVICE=WFS&VERSION=2.0.0&request=GetFeature&typename=tcl_sytral.tcllignetram_2_0_0&outputFormat=application/json; subtype=geojson&SRSNAME=EPSG:4171"
    r_tram = requests.get(link_tram)
    traces_tram = pd.json_normalize(r_tram.json())
    traces_tram = traces_tram['features'][0]

    # API tracés de bus
    link_bus = 'https://download.data.grandlyon.com/wfs/rdata?SERVICE=WFS&VERSION=2.0.0&request=GetFeature&typename=tcl_sytral.tcllignebus_2_0_0&outputFormat=application/json; subtype=geojson&SRSNAME=EPSG:4171'
    r_bus = requests.get(link_bus)
    traces_bus = pd.json_normalize(r_bus.json())
    t_bus = traces_bus['features'][0]

    # API tracés métro & funiculaires
    link_metro = "https://download.data.grandlyon.com/wfs/rdata?SERVICE=WFS&VERSION=2.0.0&request=GetFeature&typename=tcl_sytral.tcllignemf_2_0_0&outputFormat=application/json; subtype=geojson&SRSNAME=EPSG:4171&startIndex=0"
    r_metro = requests.get(link_metro)
    traces_metro = pd.json_normalize(r_metro.json())
    traces_metro = traces_metro['features'][0]
    t_fun = [t for t in traces_metro if t['properties']['famille_transport']=='FUN']
    t_metro = [t for t in traces_metro if t['properties']['famille_transport']=='MET']

    # construction dictionnaire avec les tracés bus, métro, funiculaires, tram
    lines_dict = {}
    lines_dict['Bus'] = t_bus
    lines_dict['Tramway'] = traces_tram
    lines_dict['Métro'] = t_metro
    lines_dict['Funiculaire'] = t_fun

    # CARTE
    # paramétrage :
    centre = [45.75540611072912, 4.842535168843551]      # Guillotière
    map = folium.Map(location=centre, zoom_start=13, tiles=None)
    map.add_child(folium.TileLayer('Cartodb dark_matter'))
    map.add_child(folium.TileLayer('Cartodb Positron'))

    # 0075bf bleu B
    # bleu turquoise #00C4B3
    # tram #8c368c
    # funiculaire #95c23d

    for transport_type, lines in lines_dict.items():
        fg = folium.FeatureGroup(name=transport_type)

        # tracés des bus plus fins, et par défaut non affichés :
        if transport_type == 'Bus':
            fg = folium.FeatureGroup(name=transport_type, show=False)
            style_function = lambda x: {'color': '#00C4B3', 'weight': 1}
        elif transport_type == 'Tramway':
            style_function = lambda x : {'color' : '#0075bf', 'weight' : 3}
        elif transport_type == 'Funiculaire':
            style_function = lambda x: {'color': '#95c23d', 'weight': 3}
        elif transport_type == 'Métro':
            style_function = lambda x : {'color' : color_red_st, 'weight' : 3}

        map.add_child(fg)
        code_lignes = []

        for line in lines:
            code_ligne = line['properties']['code_ligne']
            if code_ligne not in code_lignes:
                code_lignes.append(code_ligne)
                gjson = folium.features.GeoJson(line['geometry'],
                                                style_function = style_function)
                fg.add_child(gjson)

    folium.LayerControl().add_to(map)

    filename = 'data_grand_lyon/map_all_traces.html'
    map.save(filename)

    return filename


def get_passages_tram():
    """ Récupère les prochains passages de tramway depuis l'API du Grand Lyon
        Retourne un DataFrame"""

    # API prochains passages en temps réel
    link_passages = "https://download.data.grandlyon.com/ws/rdata/tcl_sytral.tclpassagearret/all.json?maxfeatures=-1&start=1"
    r_passages = requests.get(link_passages, auth=HTTPBasicAuth(USERNAME, PASSWORD))
    passages = pd.json_normalize(r_passages.json(), record_path = 'values')

    # insertion timestamp
    request_time = dt.datetime.now(pytz.timezone('Europe/Paris')).replace(microsecond=0)
    timestamp = [request_time for i in range(passages.shape[0])]
    s = pd.Series(timestamp, name = 'timestamp')
    passages.insert(0, 'timestamp', s)

    # correction trams
    def correct_trams(row):
        if ('T1' in row['ligne']) and ('Mermoz' in row['direction']):
            return 'T6'
        elif ('T1' in row['ligne']) and ('Perrache' in row['direction']):
            return 'T2'
        elif ('T1' in row['ligne']) and ('Meyzieu' in row['direction']):
            return 'T3'
        elif ('T4' in row['ligne']) and ('Gare Part-Dieu' in row['direction']):
            return 'T3'
        elif ('T4' in row['ligne']) and ('Meyzieu' in row['direction']):
            return 'T3'
        else:
            return row['ligne']

    passages['ligne'] = passages.apply(correct_trams, axis=1)

    # nettoyage passages
    passages['direction'] = passages['direction'].apply(str.strip)
    passages['ligne'] = passages['ligne'].apply(lambda x : x.replace('A', ''))
    passages = passages[~((passages['direction'] == 'Porte des Alpes') & (passages['ligne'] == 'T2'))]
    passages = passages[~((passages['direction'] == 'Perrache') & (passages['ligne'] == 'T2'))]
    passages = passages[~((passages['direction'] == 'Grange Blanche') & (passages['ligne'] == 'T2'))]

    # filtrage : tram uniquement
    lignes_tram = ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7']
    passages = passages[passages.ligne.isin(lignes_tram)]

    # filtrage colonnes
    passages.drop(['coursetheorique', 'gid', 'idtarretdestination', 'last_update_fme', 'type'], axis=1, inplace=True)
    # transformation en format date
    passages['heurepassage'] = pd.to_datetime(passages['heurepassage'])

    # index à 0
    passages.reset_index(inplace=True, drop=True)

    # API points d'arrêt (= stations)
    link_stations = "https://download.data.grandlyon.com/wfs/rdata?SERVICE=WFS&VERSION=2.0.0&request=GetFeature&typename=tcl_sytral.tclarret&outputFormat=application/json; subtype=geojson&SRSNAME=EPSG:4171&startIndex=0"
    r_stations = requests.get(link_stations)
    points_arret = pd.json_normalize(r_stations.json(), record_path = 'features')

    # filtrage & reformatage
    points_arret['properties.id'] = points_arret['properties.id'].astype('int64')
    points_arret.drop(['type', 'properties.pmr', 'properties.ascenseur', 'properties.desserte', 'properties.gid', 'properties.escalator', 'properties.last_update', 'properties.last_update_fme', 'geometry.type'], axis=1, inplace=True)
    points_arret['properties.nom'] = points_arret['properties.nom'].apply(lambda x : x.replace('St', 'Saint'))
    passages = passages.merge(points_arret, how='left', left_on='id', right_on='properties.id')
    passages = passages[['timestamp', 'ligne', 'id', 'direction', 'properties.nom', 'delaipassage', 'heurepassage', 'geometry.coordinates']]

    def get_concat(row):
        concat = f"{row['ligne']} - {row['direction']} - {str(row['id'])}"
        return concat

    try:
        tmp = passages.apply(get_concat, axis=1)
        passages['concat'] = tmp
    except ValueError:
        print(tmp.shape)

    passages = passages.sort_values(['concat', 'heurepassage']).drop_duplicates(subset=['concat'])
    passages['delaipassage'].replace(to_replace='Proche', value='0 min', inplace = True)

    passages.reset_index(inplace=True, drop=True)

    return passages


def get_json_tram():
    """ Récupère les tracés des tramways depuis l'API du Grand Lyon
        Retourne des données au format JSON"""

    link_tram = "https://download.data.grandlyon.com/wfs/rdata?SERVICE=WFS&VERSION=2.0.0&request=GetFeature&typename=tcl_sytral.tcllignetram_2_0_0&outputFormat=application/json; subtype=geojson&SRSNAME=EPSG:4171"
    r_tram = requests.get(link_tram)
    traces_tram = pd.json_normalize(r_tram.json())['features'][0]

    # harmonisation orthographe terminus
    tram_terminus = ['Debourg', 'Hôtel de Région Montrochet', 'IUT Feyssine', 'Saint-Priest Bel Air',
                     'La Doua-Gaston Berger', 'Hôpital Feyzin Vénissieux', 'Eurexpo', 'Grange Blanche',
                     'Meyzieu les Panettes', 'Gare Part-Dieu', 'Décines-O.L.Vallée',
                     'Vaulx-en-Velin La Soie', 'Hôpitaux Est-Pinel']

    dico_correction = {'H.' : 'Hôtel',
                     'Hôp.' : 'Hôpital',
                     'G.Berger' : 'Gaston Berger',
                     'St' : 'Saint',
                     'Vaulx' : 'Vaulx-en-Velin'}

    for tram in traces_tram:
        origine = tram['properties']['nom_origine']
        destination = tram['properties']['nom_destination']

        for word in origine.split():
            if word in dico_correction:
                tram['properties']['nom_origine'] = tram['properties']['nom_origine'].replace(word, dico_correction[word])

        for word in destination.split():
            if word in dico_correction:
                tram['properties']['nom_destination'] = tram['properties']['nom_destination'].replace(word, dico_correction[word])

        for terminus in tram_terminus:
            if fuzz.partial_ratio(tram['properties']['nom_destination'], terminus) >= 80:
                tram['properties']['nom_destination'] = terminus

    return traces_tram


def get_map_tram(df, traces_tram, ligne, terminus):

    p = df[df['ligne'] == ligne]
    p['fuzz_ratio'] = p['properties.nom'].apply(lambda x : fuzz.partial_ratio(x, terminus))
    p = p[(p['direction'] == terminus) | (p['fuzz_ratio'] >= 77)]
    p.reset_index(inplace=True)

    request_time = p['timestamp'].unique()[0]
    tram_terminus = list(df['direction'].unique())

    # 'centre' géographique de chaque ligne
    centre_lignes = {'T1' : [4.842535168843551, 45.75540611072912][::-1],     # Guillotière
                     'T2' : [4.859213452134834, 45.74009698588613][::-1],     # Jet d'Eau
                     'T3' : [4.910450819111944, 45.758460196002034][::-1],    # Bel Air les Brosses
                     'T4' : [4.859213452134834, 45.74009698588613][::-1],     # Jet d'Eau
                     'T5' : [4.904503423384204, 45.73496753878445][::-1],     # Boutasse C. Rousset
                     'T6' : [45.727601206367986, 4.862018242655342],          # moyenne du tracé
                     'T7' : [45.77648840600608, 4.972809071935217]}           # moyenne du tracé


    # AFFICHAGE TRACES + STATIONS

    # centre automatique sur la ligne choisie
    for tram in centre_lignes:
        if tram == ligne:
            centre = centre_lignes[tram]

    map_tram_tr = folium.Map(location=centre, zoom_start=14)
    map_tram_tr.add_child(folium.TileLayer("cartodbpositron"))

    # ajout traces
    for line in traces_tram:
        ligne_segment = line['properties']['ligne']
        if ligne_segment == ligne:
            gjson = folium.features.GeoJson(line['geometry'],
                                            style_function = lambda x: {'color': color_red_st,
                                                                        'weight': 3})
            map_tram_tr.add_child(gjson)
            break

    # ajout des stations sur la carte
    for i in range(len(p)):
        loc = p.loc[i]['geometry.coordinates'][::-1]
        nom = p.loc[i]['properties.nom']
        delai = p.loc[i]['delaipassage']
        ts = p.loc[i]['timestamp']
        text_actu = f"Dernière actualisation à {request_time.strftime('%X')}"

        tip = folium.Tooltip(f"<b>{nom}</b> <br> En direction de {terminus} <br> Prochain passage : {delai}")

        # noms des terminus
        for term in tram_terminus:
            if fuzz.partial_ratio(nom, term) >= 80:
                icon = folium.DivIcon(html=('<svg height="100" width="300">'
                                        f'<text x="15" y="15" fill="black" font-weight="bold">{nom}</text>'
                                        '</svg>'))
                folium.Marker(
                    location = loc,
                    icon = icon
                    ).add_to(map_tram_tr)

        # ronds pour stations
        icon = folium.plugins.BeautifyIcon(icon_shape='circle-dot',
                                            border_color= color_red_st,
                                            border_width=6)

        folium.Marker(
            location = loc,
            tooltip = tip,
            icon = icon
            ).add_to(map_tram_tr)


    filename = "data_grand_lyon/map_tram_tr.html"
    map_tram_tr.save(filename)

    return filename


def get_df_parcs_relais():
    """ Lit le csv parcs relais, retourne un DataFrame nettoyé"""

    df_parc = pd.read_csv('data_grand_lyon/parcs_relais.csv', index_col=[0])

    # filtrage & reformatage
    df_parc['dateTime'] = df_parc['timestamp'].astype('datetime64[ns]')
    df_parc['jour'] = df_parc['dateTime'].dt.weekday
    dayOfWeek={0:'Lundi', 1:'Mardi', 2:'Mercredi', 3:'Jeudi', 4:'Vendredi', 5:'Samedi', 6:'Dimanche'}
    df_parc['jour'] = df_parc['dateTime'].dt.dayofweek.map(dayOfWeek)
    df_parc['heure'] = df_parc['dateTime'].dt.hour
    df_parc['periode'] = df_parc['heure'].apply(lambda x: 'Matin' if x < 12 else 'Apres_midi')
    df_parc['nom'] = df_parc['nom'].apply(lambda x : x.replace('Parc Relais TCL ', ''))
    df_parc['nom'] = df_parc['nom'].apply(lambda x : x.replace('Hopital', 'Hôp.'))
    parcs_nan = ['Feyssine', 'Gare de Vénissieux', 'Grézieu la Varenne', 'Porte des Alpes',
                'Irigny-Yvours', 'Oullins La Saulaie Nord', 'Porte de Lyon']
    df_parc = df_parc[~df_parc['nom'].isin(parcs_nan)]
    df_parc.reset_index(inplace=True)
    df_parc['taux_remplissage'] = (df_parc['capacite'] - df_parc['nb_tot_place_dispo'])/df_parc['capacite'] * 100

    def parc_fermeture(row):
        if row['heure'] <= 5 and row['nb_tot_place_dispo'] == 0:
            return 0
        elif (row['nom'] == 'Laurent Bonnevay' or row['nom'] == 'Gorge de Loup') and (row['jour'] == 'Dimanche'):
            return 0
        elif row['nom'] == 'Meyzieu les Panettes' and (row['jour'] == 'Samedi' or row['jour'] == 'Dimanche'):
            return 0
        return row['taux_remplissage']

    df_parc['taux_remplissage'] = df_parc.apply(parc_fermeture, axis=1)

    df_parc.drop(columns=['gid', 'horaires', 'id', 'last_update', 'last_update_fme',
                          'p_surv', 'place_handi'], inplace=True)

    return df_parc


def get_graph_pr_tous(df_parc, jour):
    """ Génère le graphe : évolution animée du remplissage
        de tous les parcs relais pour un jour
        Retourne fig """

    df_day_parc = df_parc[(df_parc['jour'] == jour)]
    df_day_parc1 = pd.pivot_table(df_day_parc, index = ['nom', "heure"], aggfunc = "mean")
    df_day_parc1.reset_index(inplace=True)

    fig = px.bar(df_day_parc1, x="nom", y='taux_remplissage', color = "nom", animation_frame="heure",
                labels={"taux_remplissage": "",
                        "nom": ""},
                )
    fig.update_layout(margin=dict(l=70, r=40, t=70, b=200),
                      title_text=f"<b>Évolution du remplissage (%) des parcs relais un {jour.lower()} (cliquez sur play)</b>", title_x=0.5, title_font_size=20,
                      xaxis = dict(tickfont = dict(size=16)),
                      yaxis = dict(tickfont = dict(size=16)),
                      height = 700,
                      showlegend=False)
    fig['layout']['updatemenus'][0]['pad']=dict(r= 20, t= 160)
    fig['layout']['sliders'][0]['pad']=dict(r= 20, t= 150)

    fig.update_yaxes(range=[0, 100])

    return fig


def get_graph_pr(df_parc, parc, jour):
    """"""

    df_day_parc = df_parc[(df_parc['jour'] == jour)]
    df_day_parc = df_day_parc[(df_day_parc['nom'] == parc)]
    df_day_parc1 = pd.pivot_table(df_day_parc, index = "heure", values = "taux_remplissage")
    df_day_parc1.reset_index(inplace=True)

    fig = px.line(df_day_parc1, x="heure", y='taux_remplissage',
                labels={"taux_remplissage": "",
                        "heure": "Heure"},
                        height=550, color_discrete_sequence=[color_red_st])
    fig.update_layout(title_text=f"<b>Évolution du remplissage (%) du parc relais {parc} un {jour.lower()}</b>", title_x=0.5, title_font_size=20,
                      xaxis = dict(tickfont = dict(size=14)),
                      yaxis = dict(tickfont = dict(size=14)))
    fig.update_yaxes(range=[0, 100])
    fig.update_xaxes(range=[0, 23], dtick=1)

    return fig


def get_df_velov():
    """ Lit le csv velov, retourne un DataFrame nettoyé"""

    df_velov = pd.read_csv('data_grand_lyon/velov_concat.csv')

    df_velov['taux_remplissage'] = (df_velov['available_bike_stands']/df_velov['bike_stands'])*100
    df_velov['dateTime'] = df_velov['timestamp'].astype('datetime64[ns]')
    df_velov['jour'] = df_velov['dateTime'].dt.weekday
    dayOfWeek={0:'Lundi', 1:'Mardi', 2:'Mercredi', 3:'Jeudi', 4:'Vendredi', 5:'Samedi', 6:'Dimanche'}
    df_velov['jour'] = df_velov['dateTime'].dt.dayofweek.map(dayOfWeek)
    df_velov['heure'] = df_velov['dateTime'].dt.hour

    df_velov.drop(columns=['Unnamed: 0',"availabilitycode", "number", "available_bikes", "available_bike_stands",
                      "bike_stands", "code_insee", "nmarrond", "fill_rate_percent", "gid", "lat", "lng", "lon"], inplace=True)

    return df_velov


def get_graph_velov_communes(df_velov, jour):

    df_day = df_velov[(df_velov['jour'] == jour)]

    df_day3 = pd.pivot_table(df_day, index = ['commune', "heure"], aggfunc = "mean")
    df_day3.reset_index(inplace=True)

    fig = px.bar(df_day3, x="commune", y='taux_remplissage', color = "commune", animation_frame="heure",
                labels={"taux_remplissage": "",
                        "commune": ""},
                    width=1200, height=800)
    fig.update_layout(title_text=f"<b>Évolution du remplissage (%) des stations Vélo'v, un {jour.lower()}</b> (cliquez sur 'play' sous le graphe)", title_x=0.5, title_font_size=20,
                      xaxis = dict(tickfont = dict(size=14)),
                      yaxis = dict(tickfont = dict(size=14)),
                      showlegend=False)
    fig['layout']['updatemenus'][0]['pad']=dict(r= 20, t= 200)
    fig['layout']['sliders'][0]['pad']=dict(r= 20, t= 180,)

    fig.update_yaxes(range=[0, 100])

    return fig


def get_graph_velov_unecommune(df_velov, jour, commune):

    df_day = df_velov[df_velov['jour'] == jour]
    df_day = df_velov[df_velov['commune'] == commune]

    df_day1 = pd.pivot_table(df_day, index = ['name', "heure"], values='taux_remplissage', aggfunc = "mean")
    df_day1.reset_index(inplace=True)

    fig = px.bar(df_day1, x="name", y='taux_remplissage', animation_frame="heure", color="taux_remplissage",
                color_continuous_scale = px.colors.sequential.Blues, range_color=[0, 100],
                labels={"taux_remplissage": "",
                        "name": ""},
                width=1200, height=700)

    fig.update_layout(margin=dict(l=70, r=70, t=70, b=200),
                      title_text=f"<b>Évolution du remplissage (%) des stations Vélo'v de {commune} un {jour.lower()}</b>",
                      title_x=0.5, title_font_size=20,
                      xaxis = dict(tickfont = dict(size=16)),
                      yaxis = dict(tickfont = dict(size=16)),
                      height = 700,
                      showlegend=False,
                      coloraxis_showscale=False)
    fig['layout']['updatemenus'][0]['pad']=dict(r= 20, t= 150)
    fig['layout']['sliders'][0]['pad']=dict(r= 20, t= 140,)

    fig.update_yaxes(range=[0, 100])

    return fig


def get_graph_velov_unestation(df_velov, jour, commune, station):

    df_day = df_velov[(df_velov['jour'] == jour)]
    df_day = df_day[(df_day['commune'] == commune)]
    df_day = df_day[(df_day['name'] == station)]
    df_day2 = pd.pivot_table(df_day, index = ["heure"], aggfunc = "mean")
    df_day2.reset_index(inplace=True)

    fig = px.line(df_day2, x="heure", y='taux_remplissage',
                    labels={"taux_remplissage": "",
                            "heure": "Heures"},
                    color_discrete_sequence=[color_red_st])
    fig.update_layout(margin=dict(l=70, r=70, t=70, b=200),
                      title_text=f"<b>Évolution du remplissage (%) de la station Vélo'v {station} un {jour.lower()}</b>",
                      title_x=0.5, title_font_size=20,
                      xaxis = dict(tickfont = dict(size=16)),
                      yaxis = dict(tickfont = dict(size=16)),
                      width=1200, height = 700,
                      showlegend=False,)
    fig.update_yaxes(range=[0, 103])
    fig.update_xaxes(range=[0, 23], dtick=1)

    return fig


# FRONT END
with st.sidebar:
    options = ["Accueil", "Vélo'v : analyse", "Vélo'v en temps réel", "Parcs relais", "Horaires des tramways", "À propos"]
    menu_title = "Les transports du Grand Lyon"
    choice = option_menu(menu_title=None, options=options, icons=['house', 'graph-up', 'bicycle', 'building', 'watch', 'info-circle'],)

# Body
if choice == "Accueil":
    #Titre Général
    st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>LES TRANSPORTS DU GRAND LYON</h1>", unsafe_allow_html=True)

    st.image('images/Funiculaire-h.jpg')
    components.html("<p><a style='float: right; font-size:small; font-family: arial; color: #5b5b5b;' href=\"https://commons.wikimedia.org/wiki//File:Funiculaire.jpg\">Photo par Magicludovic, CC BY-SA 3.0</a></p>")

    st.markdown("#### Bienvenue sur ce dashboard interactif sur les moyens de transport dans l’agglomération lyonnaise.")
    st.markdown("Vous trouverez diverses informations sur l’usage des Vélo’v, le réseau de pistes cyclables,\
            le tramway, des suggestions d’itinéraires piétons…")
    st.markdown("Mais tout d’abord quelques chiffres :")
    st.markdown("• Lyon est la 3ème ville de France, près de 1,4 millions de personnes vivent dans son agglomération, \
        et sa superficie s’étend sur plus de 500 km², ce qui explique l’importance et l’étendue de son réseau de transport.")
    st.markdown("• Le réseau de bus et trolleybus comprend 120 lignes, pour une longueur totale d’environ 2500 km.")
    st.markdown("• Le réseau de métro comprend 4 lignes, qui totalisent 40 stations et 32 kms de voies.\
        Plus de 200 millions de voyages sont effectués chaques années, et représentent 44% de la fréquentation du réseau TCL.")
    st.markdown("• Le réseau de tramway comprend 7 lignes, d’une longueur totale de 76,7 km.")
    st.markdown("• Les parcs relais sont au nombre de 22 et offrent près de 7500 places de stationnement dans la périphérie lyonnaise.")
    st.markdown("• Les pistes cyclables représentent actuellement 540 kms sur le territoire.\
                Les “voies lyonnaises” dont les travaux viennent de démarrer, vont ajouter près de 400 km\
                  de voies cyclables aménagées dans toute l'agglomération. \
                 Un réseau très ambitieux, dont la construction doit s'étaler jusqu'en 2030.")
    st.text("")
    st.text("")
    st.markdown("#### La carte ci-dessous montre l'ensemble du réseau de transports en commun.")
    st.markdown("Cliquez sur les carrés en haut à droite de la carte pour sélectionner les moyens de transport affichés.")


    file_traces = open(get_all_traces_color(), 'r', encoding='utf-8')
    components.html(file_traces.read(), height=map_height+10)


if choice == "Vélo'v : analyse":
    #Titre Général
    st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>LES VÉLO'V : ANALYSE DE FRÉQUENTATION</h1>", unsafe_allow_html=True)
    st.text("")

    st.image("images/velov_Lyon_Velo'v_Station.jpg")
    components.html("<p><a style='float: right; font-size:small; font-family: arial; color: #5b5b5b;' href=\"https://commons.wikimedia.org/wiki/File:Lyon_Velo%27v_Station.jpg\">Photo par Elwood j blues, CC BY-SA 3.0</a></p>")

    st.markdown("Avec 428 stations et 5 000 vélos, Vélo’v propose aux habitants des 32 communes\
        de la Métropole de Lyon depuis le 19 maI 2005 un vélo en libre-service, disponible 24h/24 et 7j/7.\
        En janvier 2022, la Métropole dispose de 424 stations ouvertes et 4 fermées.")
    st.markdown("#### Découvrez l'évolution animée du remplissage des stations Vélo’v du 4ème arrondissement de Lyon, tout au long de la semaine (appuyez sur play sous le graphique).")

    if 'velov' not in st.session_state:
        st.session_state['velov'] = get_df_velov()

    df_velov = st.session_state['velov']

    liste_jours = ['Sélectionnez un jour de la semaine', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    jour = st.selectbox('', options=liste_jours)
    st.text("")

    if jour != liste_jours[0]:
        with st.spinner('Chargement du graphique en cours...'):
            commune_choisie = "Lyon 4 ème"
            fig_velov_lyon4 = get_graph_velov_unecommune(df_velov, jour, commune_choisie)
            st.plotly_chart(fig_velov_lyon4, config=dict(displayModeBar=False))

        st.text("")
        st.text("")
        # 'Mairie du 4e'
        st.markdown("## Focus sur la station Vélo'v : *Mairie du 4ème*")
        st.markdown("Nous avons décidé de faire un focus sur la station Vélo’v “Mairie du 4 ème”\
            située sur le plateau de la Croix-Rousse, et de regarder l'évolution de son remplissage un mardi, un samedi et un dimanche.")

        st.markdown("#### Mardi")
        st.markdown("Nous pouvons constater que le mardi, la station se vide entre 8h et 10h.\
            Il s’agit des heures où les personnes partent travailler.\
            Le nombre de vélos baisse fortement à 13h à l’heure du déjeuner.\
            Puis, la station se remplit progressivement à partir de 17h après la journée de travail.")
        fig_velov_mairie_m = get_graph_velov_unestation(df_velov, jour='Mardi', commune=commune_choisie, station='Mairie du 4e')
        st.plotly_chart(fig_velov_mairie_m, config=dict(displayModeBar=False))

        st.markdown("#### Samedi")
        st.markdown("Le samedi, le nombre de vélos baisse fortement entre 8h et 10h en raison du marché ou des personnes partant \
            en centre-ville. La station se remplit ensuite fortement à partir de 15h pour arriver à son plein à 19h \
                lorsque les personne rentrent chez elles ou se rendent dans un bar/restaurant.")
        fig_velov_mairie_s = get_graph_velov_unestation(df_velov, jour='Samedi', commune=commune_choisie, station='Mairie du 4e')
        st.plotly_chart(fig_velov_mairie_s, config=dict(displayModeBar=False))


        st.markdown("#### Dimanche")
        st.markdown("Le dimanche, nous pouvons constater que les vélos sont très peu utilisés et cela entre 9h et 18h.")
        fig_velov_mairie_d = get_graph_velov_unestation(df_velov, jour='Dimanche', commune=commune_choisie, station='Mairie du 4e')
        st.plotly_chart(fig_velov_mairie_d, config=dict(displayModeBar=False))


if choice == "Vélo'v en temps réel":
    st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>LES VÉLO'V : DISPONIBILITÉS EN TEMPS RÉEL</h1>", unsafe_allow_html=True)
    st.info("Pour plus de confort, nous vous invitons à fermer le volet de gauche.")
    st.markdown("##### Avec 425 stations et 5 000 vélos, Vélo’V propose aux habitants de la Métropole de Lyon\
        depuis 2005 un vélo en libre service, disponible 24h/24 et 7j/7.")
    st.markdown("#### Les deux cartes ci-dessous représentent les disponibilités des Vélo'v en temps réel.")
    st.markdown("###### Elles permettent aussi d'apprécier la répartition des stations sur l'ensemble du territoire de \
                l'agglomération.")
    st.text("")


    if 'velov_tr' not in st.session_state:
        st.session_state['velov_tr'] = get_df_velov_tr()

    df_velov_tr = st.session_state['velov_tr']

    request_time = df_velov_tr['timestamp'].unique()[0]
    actu = f"Dernière actualisation à {request_time.strftime('%X')}"
    st.text(actu)

    with st.spinner('Chargement de la carte en cours...'):
        file_velov = open(get_map_velov_tr(df_velov_tr), 'r', encoding='utf-8')
        components.html(file_velov.read(), height=map_height+10)


if choice == "Parcs relais":

    st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>LES PARCS RELAIS</h1>", unsafe_allow_html=True)
    st.text("")
    st.text("")
    st.image('images/parcs_relais_2048px-Parking_relais_TCL_C3_Bonnevay.JPG')
    components.html("<p><a style='float:right; font-size:small; font-family: arial; color: #5b5b5b;' href=\"https://commons.wikimedia.org/wiki/File:Parking_relais_TCL_C3_Bonnevay.JPG\">Xavier Caré / Wikimedia Commons</a></p>")

    st.markdown("Les parcs relais sont des lieux de stationnement qui offrent 7500 places aux clients du réseau TCL.\
        Ils permettent aux personnes vivant en-dehors de Lyon de garer leur véhicule au prix d'un ticket de métro.")
    st.markdown("Ils sont situés à proximité directe du métro, du tramway ou d\'un centre d\'échanges TCL. \
        Les parcs relais en correspondance avec les lignes de métro sont ouverts jusqu\'à 3h du matin \
        tous les vendredis et samedis (au lieu d\'1h du matin).")

    st.markdown("Les parcs relais en chiffres :")
    st.markdown('•  Nombre total de parcs relais : 22', unsafe_allow_html=True)
    st.markdown('•  Nombre total de places : 7 324', unsafe_allow_html=True)
    st.markdown('•  Nombre total de places PMR : 180', unsafe_allow_html=True)
    st.text("")
    st.info("Pour plus de confort, nous vous invitons à fermer le volet de gauche.")
    st.markdown("#### Découvrez ci-dessous l'évolution animée de la fréquentation des parcs relais de la Métropole de Lyon tout au long de la semaine :")

    if 'parcs_relais' not in st.session_state:
        st.session_state['parcs_relais'] = get_df_parcs_relais()
    df_parc = st.session_state['parcs_relais']
    liste_jours = ['Sélectionnez un jour de la semaine', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

    col1, col2 = st.columns(2)
    with col1:
        jour_choisi = st.selectbox('', options=liste_jours)
        st.text("")
        st.text("")

        if jour_choisi != liste_jours[0]:
            fig1 = get_graph_pr_tous(df_parc, jour_choisi)
            st.plotly_chart(fig1, config=dict(displayModeBar=False))
            st.text("")
            st.text("")

            with col2:
                liste_parcs = sorted(list(df_parc['nom'].unique()))
                liste_parcs.insert(0, 'Sélectionnez un parc relais')
                parc_choisi = st.selectbox("", options=liste_parcs)
                st.text("")
                st.text("")
                if parc_choisi != liste_parcs[0]:
                    df_parc_choisi = df_parc[df_parc['nom'] == parc_choisi]
                    taux_unique = df_parc_choisi['taux_remplissage'].unique()
                    if len(taux_unique) <= 1 and taux_unique[0] <= 0:
                        st.error("Données non disponibles")
                    else:
                        fig2 = get_graph_pr(df_parc, parc_choisi, jour_choisi)
                        st.plotly_chart(fig2, config=dict(displayModeBar=False))

    st.markdown("**Les jours de semaine,** ces graphiques montrent une nette augmentation de la fréquentation des parcs\
                à partir de 7h du matin, et une diminution vers 16h. Certains parcs restent parfois totalement saturés une bonne\
                partie de la journée ; c'est le cas notamment des parcs de Cuire, Mermoz, Meyzieu et Oullins.\
                On peut aisément imaginer que les personnes résidant en périphérie et travaillant dans Lyon\
                garent leur voiture dans ces parcs relais\
                et finissent leur trajet en transport en commun. Elles évitent ainsi de participer au congestionnement\
                du trafic dans le centre ville.")
    st.markdown("**Le samedi,** la fréquentation est moins élevée qu'en semaine. Seuls les parcs de Gorge de Loup\
                et Oullins dépassent les 80% de remplissage ; les autres parcs restant majoritairement en-dessous\
                de 40%. Par ailleurs, les horaires de fréquentation diffèrent de la semaine : les pics sont atteints\
                vers 10h puis vers 15h, indiquant que les conducteurs se déplacent pour des activités de loisir.")
    st.markdown("**Quant au dimanche,** 3 parcs sont fermés. Parmi ceux qui restent ouverts, on note une fréquentation très timide ;\
                en effet, le taux de remplissage moyen atteint tout juste les 6%.\
                Ce constat s'explique facilement par la fermeture dominicale des commerces.")
    st.text("")
    st.markdown("Ces données ont été collectées sur une semaine de janvier 2022.\
                Malheureusement, nous n’avons pas pu récupérer les données pour les parcs relais : Feyssine, Gare de Vénissieux, Grézieu la Varenne,\
                Irigny-Yvours, Oullins La Saulaie Nord, Porte des Alpes et Porte de Lyon.")


if choice == "Horaires des tramways":

    # Blabla
    st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>LE TRAMWAY : HORAIRES EN TEMPS RÉEL</h1>", unsafe_allow_html=True)
    st.text("")
    st.text("")
    st.image("images/tram_1620px-Citadis_302_Lyon_T6_Challemel-Lacour_-_Artillerie.jpg")
    components.html("<p><a style='float: right; font-size:small; font-family: arial; color: #5b5b5b;' href=\"https://commons.wikimedia.org/w/index.php?curid=84308627\">Photo par Bmazerolles — Travail personnel, CC BY-SA 4.0</a></p>")

    st.markdown("Inauguré en 2001 avec ses deux premières lignes, le réseau de tramway lyonnais comporte aujourd'hui\
        7 lignes, traverse 8 communes, ainsi que 5 arrondissements lyonnais. Il relie ainsi les grands pôles économiques,\
        commerciaux et universitaires de l'agglomération lyonnaise en transportant chaque jour 300 000 voyageurs,\
        soit 17% du trafic sur le réseau TCL.")
    st.markdown("Le réseau de tramway comptabilise au total 76,7 km de ligne, sur lesquels circulent\
        103 rames qui desservent 104 stations. Depuis sa création il a bénéficié de 100% d'extension (+55km).")
    st.markdown("Prochains projets qui seront mis en service avant 2026 : T6 nord (prolongement jusqu'à la Doua), T8 (Bellecour - Part Dieu\
        T9 (Vaulx en Velin - la Doua) et T10 (Vénissieux - St Fons - Gerland)")

    st.markdown("#### La carte ci-dessous affiche les prochains passages des tramways, en temps réel.")
    st.info("Pour plus de confort, nous vous invitons à fermer le volet de gauche.")

    if 'passages' not in st.session_state:
        st.session_state['passages'] = get_passages_tram()

    passages = st.session_state['passages']
    request_time = passages['timestamp'].unique()[0]

    # import des données géo tram + selectboxes (choix lignes + terminus)
    traces_tram = get_json_tram()
    lignes_tram = sorted(passages['ligne'].unique())
    lignes_tram.insert(0, 'Sélectionnez une ligne de tramway')
    tram_terminus = sorted(list(passages['direction'].unique()))

    col1, col2 = st.columns(2)

    with col1:
        # Selectbox lignes de tram
        ligne = st.selectbox(label='', options=lignes_tram, index=0)
        if ligne != lignes_tram[0]:
            p = passages[passages['ligne'] == ligne]
            tram_terminus = sorted(list(p['direction'].unique()))
            tram_terminus.insert(0, 'Sélectionnez un terminus')

            with col2:
                # Selectbox terminus
                terminus = st.selectbox(label='', options=tram_terminus, index=0)

        text_actu = f"Dernière actualisation à {request_time.strftime('%X')}"
        actualisation = st.button('Actualiser les données')
        if actualisation:
            del st.session_state['passages']
        st.text(text_actu)

    # affichage de la carte
    with st.spinner('Chargement de la carte en cours...'):
        if (ligne != lignes_tram[0]) and (terminus != tram_terminus[0]):
            file_map_tram = open(get_map_tram(passages, traces_tram, ligne, terminus), 'r', encoding='utf-8')
            components.html(file_map_tram.read(), height=map_height+10)


if choice == 'À propos':
    st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>À PROPOS</h1>", unsafe_allow_html=True)
    st.markdown("#### Le contexte")
    st.markdown("Ce dashboard interactif a été réalisé en février 2022 dans le cadre du projet de clôture de\
             notre formation Data Analyst, effectuée en 5 mois à la Wild Code School de Lyon.\
            L’objectif était de travailler sur l’open data mise à disposition par la Métropole de Lyon,\
            et d’analyser les usages des différents moyens de transports dans l’agglomération.")
    st.markdown("Pour concevoir les cartes interactives des Vélo'V et des tramways, nous faisons appel à **différentes API**\
                qui fournissent des **données en temps réel.**\
                Quant aux graphiques, nous avons stocké des données en continu du 12 au 19 janvier 2022\
                afin de pouvoir ensuite établir des **tendances d'utilisation** des Vélo'V et des parcs relais.")
    st.text("")

    st.markdown("#### La technique")
    st.markdown("Pour réaliser ce projet, nous avons utilisé le langage **Python** et ses différentes\
                  bibliothèques dédiées à l’analyse et au traitement des données, \
                  à savoir : **Pandas, Numpy, Plotly, Folium, et GeoPandas.** \
                  Notre choix s'est porté sur **Streamlit** pour la mise en page du dashboard\
                  et son déploiement sous forme d’application web.")
    st.text("")

    st.markdown("#### Remerciements")
    st.markdown("Nous remercions notre formateur Jérémy Perret pour ses précieux conseils durant cette formation, \
        ainsi que la Métropole de Lyon et le Sytral pour l’accès aux données et différents contenus.")

    st.markdown("#### L'équipe")
    annecha, thomas, mouna = st.columns(3)
    with annecha:
        st.image('images/AC_LinkedIn.jpg')
        components.html(f"<p><a style='text-align: center; font-size:large; font-weight: bold; font-family: arial; color: {color_red_st};' href=\"https://www.linkedin.com/in/annecharlottebesse\" target=\"_blank\">Anne-Charlotte Besse</a></p>")
    with thomas:
        st.image('images/Thomas.jpg')
        components.html(f"<p><a style='text-align: center; font-size:large; font-weight: bold; font-family: arial; color: {color_red_st};' href=\"https://www.linkedin.com/in/thomas--grall\" target=\"_blank\">Thomas Grall</a></p>")
    with mouna:
        st.image('images/Mouna.png')
        components.html(f"<p><a style='text-align: center; font-size:large; font-weight: bold; font-family: arial; color: {color_red_st};' href=\"https://www.github.com/mounasb\" target=\"_blank\">Mouna Sebti</a></p>")
